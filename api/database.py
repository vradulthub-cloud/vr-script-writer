"""
SQLite database layer for the Eclatech Hub.

Provides sub-millisecond reads by mirroring Google Sheets data locally.
The sync_engine module handles the periodic Sheets → SQLite sync.

Tables mirror the 6 Google Sheets + MEGA scan data:
  - tickets       (from Tickets sheet, "Tickets" tab)
  - users         (from Tickets sheet, "Users" tab)
  - notifications (from Tickets sheet, "Notifications" tab)
  - approvals     (from Tickets sheet, "Approvals" tab)
  - scenes        (joined: Grail + Scripts + MEGA scan)
  - bookings      (from Booking sheet)
  - tasks         (background task tracking — local only)
  - sync_meta     (sync timestamps — local only)
"""

from __future__ import annotations

import sqlite3
import json
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator
from uuid import uuid4

from api.config import get_settings

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection pool (per-thread connections for thread safety)
# ---------------------------------------------------------------------------
_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        settings = get_settings()
        db_path = str(settings.sqlite_db_path)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database operations."""
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ---------------------------------------------------------------------------
# Schema initialization
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
-- Tickets (from Tickets sheet → "Tickets" tab)
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    project TEXT DEFAULT '',
    type TEXT DEFAULT '',
    priority TEXT DEFAULT 'Medium',
    status TEXT DEFAULT 'New',
    submitted_by TEXT DEFAULT '',
    submitted_at TEXT DEFAULT '',
    assignee TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    resolved_at TEXT DEFAULT '',
    linked_items TEXT DEFAULT ''
);

-- Users (from Tickets sheet → "Users" tab)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'editor',
    allowed_tabs TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Notifications (from Tickets sheet → "Notifications" tab)
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notif_id TEXT UNIQUE,
    timestamp TEXT DEFAULT '',
    recipient TEXT DEFAULT '',
    type TEXT DEFAULT '',
    title TEXT DEFAULT '',
    message TEXT DEFAULT '',
    read INTEGER DEFAULT 0,
    link TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_notif_recipient ON notifications(recipient);
CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(read);

-- Approvals (from Tickets sheet → "Approvals" tab)
CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    scene_id TEXT DEFAULT '',
    studio TEXT DEFAULT '',
    content_type TEXT DEFAULT '',
    submitted_by TEXT DEFAULT '',
    submitted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'Pending',
    decided_by TEXT DEFAULT '',
    decided_at TEXT DEFAULT '',
    content_json TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    linked_ticket TEXT DEFAULT '',
    target_sheet TEXT DEFAULT '',
    target_range TEXT DEFAULT '',
    superseded_by TEXT DEFAULT ''
);

-- Scenes (joined from Grail + Scripts + MEGA scan)
CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,           -- e.g. "VRH0758"
    studio TEXT NOT NULL,          -- UI name: "VRHush"
    grail_tab TEXT DEFAULT '',     -- Grail tab: "VRH"
    site_code TEXT DEFAULT '',     -- Site code: "vrh"
    title TEXT DEFAULT '',
    performers TEXT DEFAULT '',
    categories TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    release_date TEXT DEFAULT '',
    plot TEXT DEFAULT '',
    theme TEXT DEFAULT '',
    female TEXT DEFAULT '',
    male TEXT DEFAULT '',
    wardrobe_f TEXT DEFAULT '',
    wardrobe_m TEXT DEFAULT '',
    status TEXT DEFAULT '',
    grail_row INTEGER DEFAULT 0,
    scripts_row INTEGER DEFAULT 0,
    -- MEGA asset status
    has_description INTEGER DEFAULT 0,
    has_videos INTEGER DEFAULT 0,
    video_count INTEGER DEFAULT 0,
    has_thumbnail INTEGER DEFAULT 0,
    has_photos INTEGER DEFAULT 0,
    has_storyboard INTEGER DEFAULT 0,
    storyboard_count INTEGER DEFAULT 0,
    mega_path TEXT DEFAULT '',
    thumb_file TEXT DEFAULT '',     -- Thumbnail filename (relative to Video Thumbnail/ folder)
    is_compilation INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_scenes_studio ON scenes(studio);

-- Bookings (from Booking sheet)
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    agency TEXT DEFAULT '',
    agency_link TEXT DEFAULT '',
    rate TEXT DEFAULT '',
    rank TEXT DEFAULT '',        -- Great / Good / Moderate / Poor
    notes TEXT DEFAULT '',       -- Available For / acts from Notes column
    info TEXT DEFAULT '',        -- Derived: "Age: 22 · Last booked: Mar 2026 · ..."
    raw_json TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_bookings_name ON bookings(name);

-- Background tasks (local only — not synced to Sheets)
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,       -- "script_gen", "desc_gen", "mega_scan", etc.
    status TEXT DEFAULT 'pending', -- pending, running, completed, failed
    progress REAL DEFAULT 0,      -- 0.0 to 1.0
    params_json TEXT DEFAULT '{}',
    result_json TEXT DEFAULT '',
    error TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    started_at TEXT DEFAULT '',
    completed_at TEXT DEFAULT '',
    created_by TEXT DEFAULT ''
);

-- Scripts (from Scripts sheet monthly tabs)
CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tab_name TEXT NOT NULL DEFAULT '',
    sheet_row INTEGER NOT NULL DEFAULT 0,
    studio TEXT NOT NULL DEFAULT '',
    shoot_date TEXT DEFAULT '',
    location TEXT DEFAULT '',
    scene_type TEXT DEFAULT '',
    female TEXT DEFAULT '',
    male TEXT DEFAULT '',
    theme TEXT DEFAULT '',
    wardrobe_f TEXT DEFAULT '',
    wardrobe_m TEXT DEFAULT '',
    plot TEXT DEFAULT '',
    title TEXT DEFAULT '',
    props TEXT DEFAULT '',
    script_status TEXT DEFAULT '',
    synced_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_scripts_studio ON scripts(studio);
CREATE INDEX IF NOT EXISTS idx_scripts_tab ON scripts(tab_name);
CREATE INDEX IF NOT EXISTS idx_scripts_female ON scripts(female COLLATE NOCASE);

-- Sync metadata (tracks last sync time per data source)
CREATE TABLE IF NOT EXISTS sync_meta (
    source TEXT PRIMARY KEY,       -- "grail", "scripts", "tickets", etc.
    last_synced_at TEXT NOT NULL,
    row_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ok',
    error TEXT DEFAULT ''
);

-- Model profile cache (scraped from Babepedia, VRPorn, SLR — 7-day TTL)
CREATE TABLE IF NOT EXISTS model_profiles (
    name TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL DEFAULT '{}',
    cached_at TEXT NOT NULL
);
"""


def init_db() -> None:
    """Create all tables if they don't exist, then apply incremental migrations."""
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
        # v2 migration: add rank/info columns to bookings if upgrading from older schema
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(bookings)").fetchall()}
        for col, ddl in [("rank", "TEXT DEFAULT ''"), ("info", "TEXT DEFAULT ''")]:
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE bookings ADD COLUMN {col} {ddl}")
                _log.info("Migration: added bookings.%s", col)
        # Migration: add thumb_file to scenes for thumbnail proxy
        scene_cols = {row[1] for row in conn.execute("PRAGMA table_info(scenes)").fetchall()}
        if "thumb_file" not in scene_cols:
            conn.execute("ALTER TABLE scenes ADD COLUMN thumb_file TEXT DEFAULT ''")
            _log.info("Migration: added scenes.thumb_file")
        _log.info("Database initialized at %s", get_settings().sqlite_db_path)


# ---------------------------------------------------------------------------
# Background task helpers
# ---------------------------------------------------------------------------
def create_task(
    task_type: str,
    params: dict[str, Any] | None = None,
    created_by: str = "",
) -> str:
    """Create a new background task record. Returns the task_id."""
    task_id = f"task-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO tasks (task_id, task_type, status, params_json, created_at, created_by)
               VALUES (?, ?, 'pending', ?, ?, ?)""",
            (task_id, task_type, json.dumps(params or {}), now, created_by),
        )
    return task_id


def update_task(
    task_id: str,
    *,
    status: str | None = None,
    progress: float | None = None,
    result: Any = None,
    error: str | None = None,
) -> None:
    """Update a background task's status, progress, or result."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        if status == "running":
            conn.execute(
                "UPDATE tasks SET status=?, started_at=? WHERE task_id=?",
                (status, now, task_id),
            )
        elif status in ("completed", "failed"):
            updates = ["status=?", "completed_at=?"]
            values: list[Any] = [status, now]
            if result is not None:
                updates.append("result_json=?")
                values.append(json.dumps(result))
            if error:
                updates.append("error=?")
                values.append(error)
            values.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE task_id=?",
                values,
            )
        if progress is not None:
            conn.execute(
                "UPDATE tasks SET progress=? WHERE task_id=?",
                (progress, task_id),
            )


def get_task(task_id: str) -> dict[str, Any] | None:
    """Get a task by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        if row:
            return dict(row)
    return None


# ---------------------------------------------------------------------------
# Sync metadata helpers
# ---------------------------------------------------------------------------
def update_sync_meta(
    source: str,
    row_count: int = 0,
    status: str = "ok",
    error: str = "",
) -> None:
    """Update the last sync timestamp for a data source."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO sync_meta (source, last_synced_at, row_count, status, error)
               VALUES (?, ?, ?, ?, ?)""",
            (source, now, row_count, status, error),
        )


def get_sync_meta(source: str) -> dict[str, Any] | None:
    """Get sync metadata for a data source."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM sync_meta WHERE source=?", (source,)
        ).fetchone()
        if row:
            return dict(row)
    return None
