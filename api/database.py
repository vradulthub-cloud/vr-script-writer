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

-- Script generations — one row per /api/scripts/generate call so we can
-- correlate the model's raw output with whatever the editor eventually
-- approved (or rejected). Critical for fine-tuning: training pairs need
-- both (input prompt, raw model output) and (raw model output, edited
-- final). Without this table, we'd only ever see the final saved version
-- and lose the diff.
--
-- Lifecycle:
--   INSERT at /generate start (with prompt input + empty raw_output)
--   UPDATE at /generate stream end (raw_output filled in)
--   UPDATE at /save when gen_id is passed (edited_to + script_id + status)
--   UPDATE at approval decision (approval_id + decided_at + decision_notes)
CREATE TABLE IF NOT EXISTS script_generations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    generated_by TEXT DEFAULT '',          -- email of the user who clicked Generate
    -- Prompt input (mirrors ScriptGenRequest)
    studio TEXT NOT NULL DEFAULT '',
    scene_type TEXT DEFAULT '',
    female TEXT DEFAULT '',
    male TEXT DEFAULT '',
    destination TEXT DEFAULT '',
    director_note TEXT DEFAULT '',
    -- Reproducibility
    model_id TEXT DEFAULT '',              -- e.g. 'vr-scriptwriter:latest' or static-njoi
    seed INTEGER DEFAULT 0,
    temperature REAL DEFAULT 0.0,
    -- Output and lifecycle
    raw_output TEXT DEFAULT '',            -- streamed text, accumulated server-side
    status TEXT DEFAULT 'pending',         -- pending | discarded | edited | approved-asis | rejected
    edited_to TEXT DEFAULT '',             -- final saved plot/sections JSON when status='edited'
    -- Linkage to downstream rows
    script_id INTEGER DEFAULT 0,           -- scripts.id when saved
    approval_id TEXT DEFAULT '',           -- approvals.approval_id when submitted for approval
    decided_at TEXT DEFAULT '',
    decision_notes TEXT DEFAULT ''         -- freeform reason from approver, when rejected
);
CREATE INDEX IF NOT EXISTS idx_gen_studio ON script_generations(studio);
CREATE INDEX IF NOT EXISTS idx_gen_generated_at ON script_generations(generated_at);
CREATE INDEX IF NOT EXISTS idx_gen_status ON script_generations(status);
CREATE INDEX IF NOT EXISTS idx_gen_script_id ON script_generations(script_id);

-- Budget rates per (shoot_date, female_talent). Source: Budgets sheet.
-- Mirrored here so /api/shoots/ doesn't pay a Sheets read on every request.
-- Keys are lowercase to match the in-router cache contract.
CREATE TABLE IF NOT EXISTS budgets (
    shoot_date TEXT NOT NULL,
    female_lower TEXT NOT NULL,
    female_rate TEXT DEFAULT '',
    male_rate TEXT DEFAULT '',
    PRIMARY KEY (shoot_date, female_lower)
);
CREATE INDEX IF NOT EXISTS idx_budgets_date ON budgets(shoot_date);

-- Pre-aggregated scene stats (computed during sync_scenes). One row per
-- studio plus a synthetic 'TOTAL' row. /api/scenes/stats reads this table
-- instead of running three full table scans on every dashboard load.
CREATE TABLE IF NOT EXISTS scene_stats_cache (
    studio TEXT PRIMARY KEY,        -- studio UI name, or 'TOTAL'
    scene_count INTEGER DEFAULT 0,
    complete_count INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);

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

-- Calendar events (custom events on the Shoot Tracker calendar — shared
-- across the team, not synced to Sheets). Each row is one event on one date.
-- We do NOT scope events per-user; the team sees the same calendar.
CREATE TABLE IF NOT EXISTS calendar_events (
    event_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,        -- YYYY-MM-DD
    title TEXT NOT NULL DEFAULT '',
    kind TEXT DEFAULT '',       -- short tag, e.g. "MEETING"
    color TEXT DEFAULT '',      -- swatch id from EVENT_COLORS, e.g. "lime"
    notes TEXT DEFAULT '',
    created_by TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cal_events_date ON calendar_events(date);

-- Editable AI prompt overrides. The bundled defaults live in api/prompts.py;
-- writing a row here causes get_prompt(key) to return the override instead.
-- Deleting a row reverts to the bundled default. The admin UI surfaces this
-- table directly — every editable prompt has a stable string key (e.g.
-- "title.VRHush", "desc.FPVR") that downstream callers pass to get_prompt.
CREATE TABLE IF NOT EXISTS prompt_overrides (
    prompt_key TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    updated_by TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

-- Compliance signatures — one row per (shoot_id, talent_role, talent_slug).
-- Replaces Drive-folder-presence as the source of truth for "did the talent
-- complete paperwork in the Hub?". Existence of a row with signed_at != ''
-- and signature_image_path != '' means the talent walked through the full
-- in-Hub agreement flow on signed_at; the generated PDF lives at pdf_mega_path.
CREATE TABLE IF NOT EXISTS compliance_signatures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shoot_id TEXT NOT NULL,             -- "{shoot_date}|{female}" (matches Shoot.shoot_id)
    shoot_date TEXT NOT NULL,           -- YYYY-MM-DD
    scene_id TEXT DEFAULT '',           -- Grail scene id, e.g. "VRH0758"
    studio TEXT DEFAULT '',              -- UI name, e.g. "VRHush"
    talent_role TEXT NOT NULL,          -- 'female' | 'male'
    talent_slug TEXT NOT NULL,          -- "SofiaRed" / "MikeMancini"
    talent_display TEXT NOT NULL,       -- "Sofia Red" / "Mike Mancini"

    -- W-9 (page 1 of legacy template)
    legal_name TEXT NOT NULL,
    business_name TEXT DEFAULT '',
    tax_classification TEXT NOT NULL,   -- 'individual' | 'c_corp' | 's_corp' | 'partnership' | 'trust_estate' | 'llc' | 'other'
    llc_class TEXT DEFAULT '',          -- 'C'|'S'|'P' (only when tax_classification='llc')
    other_classification TEXT DEFAULT '',
    exempt_payee_code TEXT DEFAULT '',
    fatca_code TEXT DEFAULT '',
    tin_type TEXT NOT NULL,             -- 'ssn' | 'ein'
    tin TEXT NOT NULL,                  -- raw digits; matches legacy Drive PDF storage

    -- 2257 Performer Names Disclosure (page 6 of legacy template)
    dob TEXT NOT NULL,                  -- YYYY-MM-DD
    place_of_birth TEXT NOT NULL,
    street_address TEXT NOT NULL,
    city_state_zip TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT NOT NULL,
    id1_type TEXT NOT NULL,
    id1_number TEXT NOT NULL,
    id2_type TEXT DEFAULT '',
    id2_number TEXT DEFAULT '',
    stage_names TEXT DEFAULT '',
    professional_names TEXT DEFAULT '',
    nicknames_aliases TEXT DEFAULT '',
    previous_legal_names TEXT DEFAULT '',

    -- Signature + audit
    signature_image_path TEXT NOT NULL,  -- relative path to PNG of drawn signature
    signed_at TEXT NOT NULL,             -- ISO-8601 UTC, e.g. "2026-04-27T18:32:00Z"
    signed_ip TEXT DEFAULT '',
    signed_user_agent TEXT DEFAULT '',
    signed_by_user TEXT DEFAULT '',      -- staff who set up the iPad (RBAC user email)
    contract_version TEXT NOT NULL,      -- e.g. "2026-04-27.eclatech.v1" — sha256 of rendered contract text

    -- Output artifact
    pdf_local_path TEXT DEFAULT '',      -- local backup before MEGA push
    pdf_mega_path TEXT DEFAULT '',       -- "mega:/Grail/{Studio}/{scene_id}/Legal/{Talent}-{date}.pdf"

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    UNIQUE(shoot_id, talent_role, talent_slug)
);
CREATE INDEX IF NOT EXISTS idx_compliance_shoot     ON compliance_signatures(shoot_id);
CREATE INDEX IF NOT EXISTS idx_compliance_scene     ON compliance_signatures(scene_id);
CREATE INDEX IF NOT EXISTS idx_compliance_date      ON compliance_signatures(shoot_date);

-- Compliance signatures history — one row written every time a
-- compliance_signatures row is updated. Lets the hub show "what did
-- the paperwork look like on date X?" and "who edited what when?".
-- Created lazily by a trigger; the row stores the *prior* state plus
-- the change metadata.
CREATE TABLE IF NOT EXISTS compliance_signatures_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Mirror of the signatures schema (the values BEFORE the change)
    signature_id INTEGER NOT NULL,        -- compliance_signatures.id
    shoot_id TEXT NOT NULL,
    shoot_date TEXT NOT NULL,
    scene_id TEXT DEFAULT '',
    studio TEXT DEFAULT '',
    talent_role TEXT NOT NULL,
    talent_slug TEXT NOT NULL,
    talent_display TEXT NOT NULL,
    legal_name TEXT NOT NULL,
    business_name TEXT DEFAULT '',
    tax_classification TEXT NOT NULL,
    llc_class TEXT DEFAULT '',
    other_classification TEXT DEFAULT '',
    exempt_payee_code TEXT DEFAULT '',
    fatca_code TEXT DEFAULT '',
    tin_type TEXT NOT NULL,
    tin TEXT NOT NULL,
    dob TEXT NOT NULL,
    place_of_birth TEXT NOT NULL,
    street_address TEXT NOT NULL,
    city_state_zip TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT NOT NULL,
    id1_type TEXT NOT NULL,
    id1_number TEXT NOT NULL,
    id2_type TEXT DEFAULT '',
    id2_number TEXT DEFAULT '',
    stage_names TEXT DEFAULT '',
    professional_names TEXT DEFAULT '',
    nicknames_aliases TEXT DEFAULT '',
    previous_legal_names TEXT DEFAULT '',
    signature_image_path TEXT NOT NULL,
    signed_at TEXT NOT NULL,
    signed_ip TEXT DEFAULT '',
    signed_user_agent TEXT DEFAULT '',
    signed_by_user TEXT DEFAULT '',
    contract_version TEXT NOT NULL,
    pdf_local_path TEXT DEFAULT '',
    pdf_mega_path TEXT DEFAULT '',
    -- History-specific
    snapshot_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    edited_by TEXT DEFAULT '',            -- staff email of who triggered the edit
    edit_reason TEXT DEFAULT ''           -- optional free-text "why" supplied by editor
);
CREATE INDEX IF NOT EXISTS idx_compliance_hist_sig ON compliance_signatures_history(signature_id);
CREATE INDEX IF NOT EXISTS idx_compliance_hist_at  ON compliance_signatures_history(snapshot_at);

-- Trigger: snapshot the prior state on every UPDATE to compliance_signatures.
-- AFTER UPDATE so excluded fields (PK, created_at) are stable. We deliberately
-- do NOT snapshot on initial INSERT — the row IS the initial state.
CREATE TRIGGER IF NOT EXISTS trg_compliance_history
AFTER UPDATE ON compliance_signatures
FOR EACH ROW
BEGIN
    INSERT INTO compliance_signatures_history (
        signature_id, shoot_id, shoot_date, scene_id, studio,
        talent_role, talent_slug, talent_display,
        legal_name, business_name, tax_classification, llc_class,
        other_classification, exempt_payee_code, fatca_code,
        tin_type, tin, dob, place_of_birth, street_address,
        city_state_zip, phone, email, id1_type, id1_number,
        id2_type, id2_number, stage_names, professional_names,
        nicknames_aliases, previous_legal_names,
        signature_image_path, signed_at, signed_ip, signed_user_agent,
        signed_by_user, contract_version, pdf_local_path, pdf_mega_path
    ) VALUES (
        OLD.id, OLD.shoot_id, OLD.shoot_date, OLD.scene_id, OLD.studio,
        OLD.talent_role, OLD.talent_slug, OLD.talent_display,
        OLD.legal_name, OLD.business_name, OLD.tax_classification, OLD.llc_class,
        OLD.other_classification, OLD.exempt_payee_code, OLD.fatca_code,
        OLD.tin_type, OLD.tin, OLD.dob, OLD.place_of_birth, OLD.street_address,
        OLD.city_state_zip, OLD.phone, OLD.email, OLD.id1_type, OLD.id1_number,
        OLD.id2_type, OLD.id2_number, OLD.stage_names, OLD.professional_names,
        OLD.nicknames_aliases, OLD.previous_legal_names,
        OLD.signature_image_path, OLD.signed_at, OLD.signed_ip, OLD.signed_user_agent,
        OLD.signed_by_user, OLD.contract_version, OLD.pdf_local_path, OLD.pdf_mega_path
    );
END;

-- Compliance legal files index — a mirror of every paperwork artifact on
-- MEGA's `{SCENE_ID}/Legal/` folders. Populated by the scrape_mega_legal.py
-- worker (nightly via Task Scheduler). The Database view queries this
-- table instead of doing a live S3 list per page-load — turns a 60-second
-- bucket walk into a sub-millisecond DB lookup.
CREATE TABLE IF NOT EXISTS compliance_legal_files (
    -- Source identity
    studio TEXT NOT NULL,                -- 4-letter code: FPVR / VRH / VRA / NJOI
    scene_id TEXT NOT NULL,              -- e.g. "VRH0762"
    key TEXT NOT NULL,                   -- full bucket key, e.g. "VRH0762/Legal/foo.pdf"
    filename TEXT NOT NULL,              -- last path segment
    size INTEGER NOT NULL DEFAULT 0,     -- bytes
    last_modified TEXT NOT NULL DEFAULT '', -- ISO8601 UTC, from S3 LastModified

    -- Server-side classification (cheap heuristics, refreshed every scan)
    guessed_talent TEXT DEFAULT '',      -- best-effort name from filename
    doc_kind TEXT DEFAULT '',            -- "agreement" / "w9" / "2257" / "id_photo" / ...

    -- Link to a structured record once the bulk importer has ingested it
    imported_signature_id INTEGER DEFAULT NULL, -- compliance_signatures.id

    -- Bookkeeping
    indexed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    PRIMARY KEY (studio, key)
);
CREATE INDEX IF NOT EXISTS idx_legal_files_scene    ON compliance_legal_files(scene_id);
CREATE INDEX IF NOT EXISTS idx_legal_files_filename ON compliance_legal_files(filename);
CREATE INDEX IF NOT EXISTS idx_legal_files_kind     ON compliance_legal_files(doc_kind);
CREATE INDEX IF NOT EXISTS idx_legal_files_talent   ON compliance_legal_files(guessed_talent);
CREATE INDEX IF NOT EXISTS idx_legal_files_imported ON compliance_legal_files(imported_signature_id);

-- Bookkeeping for the scraper itself — when did the last full scan finish,
-- which studios were covered, how many files indexed.
CREATE TABLE IF NOT EXISTS compliance_legal_scan_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- single-row table
    last_scan_at TEXT DEFAULT '',
    last_scan_duration_ms INTEGER DEFAULT 0,
    last_scan_files INTEGER DEFAULT 0,
    last_scan_studios TEXT DEFAULT '',      -- comma-separated codes
    last_scan_errors TEXT DEFAULT ''        -- JSON-encoded list (empty list when clean)
);
INSERT OR IGNORE INTO compliance_legal_scan_meta (id) VALUES (1);

-- Compliance photos — independent of Drive and signatures. Photos can be
-- captured for a shoot at any time (e.g. before talent has signed paperwork)
-- and persist server-side so they reappear on next visit. Each row is one
-- captured slot (e.g. "SofiaRed-id-front"); re-uploading the same slot_id
-- replaces the file.
CREATE TABLE IF NOT EXISTS compliance_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shoot_id TEXT NOT NULL,
    shoot_date TEXT NOT NULL,
    scene_id TEXT DEFAULT '',
    studio TEXT DEFAULT '',
    slot_id TEXT NOT NULL,             -- "SofiaRed-id-front" / "signout-video"
    talent_role TEXT DEFAULT '',       -- 'female' | 'male' | '' (joint, e.g. signout video)
    label TEXT NOT NULL,                -- filename used on disk + MEGA
    mime_type TEXT NOT NULL DEFAULT 'image/jpeg',
    file_size INTEGER DEFAULT 0,
    local_path TEXT NOT NULL,           -- absolute path on the server
    mega_path TEXT DEFAULT '',          -- "mega:/Grail/{Studio}/{scene_id}/Legal/{filename}"
    uploaded_by TEXT DEFAULT '',        -- staff email (RBAC)
    uploaded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(shoot_id, slot_id)
);
CREATE INDEX IF NOT EXISTS idx_photos_shoot ON compliance_photos(shoot_id);
CREATE INDEX IF NOT EXISTS idx_photos_scene ON compliance_photos(scene_id);
CREATE INDEX IF NOT EXISTS idx_photos_date  ON compliance_photos(shoot_date);

-- Per-user notification preferences. One row per (user_email, event_type).
-- Channels are stored as a comma-separated subset of "in_app,email,teams".
-- Missing rows fall back to the defaults defined in api.notification_dispatcher.
CREATE TABLE IF NOT EXISTS user_notification_prefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT NOT NULL,
    event_type TEXT NOT NULL,
    channels TEXT NOT NULL DEFAULT 'in_app',
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(user_email, event_type)
);
CREATE INDEX IF NOT EXISTS idx_unp_email ON user_notification_prefs(user_email);
CREATE INDEX IF NOT EXISTS idx_unp_event ON user_notification_prefs(event_type);

-- Application-wide settings (admin-managed). Used for integration secrets
-- like Teams webhook URLs that we don't want to bake into code or leak to
-- the frontend. One row per setting key.
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_by TEXT DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
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


# ---------------------------------------------------------------------------
# Script-sheet enrichment helper
# ---------------------------------------------------------------------------

# Fields the helper resolves from the latest matching scripts row. Order matters
# only for the merged dict's iteration order, not for SQL.
#
# `title` is included so endpoints can use the writer's title from the Scripts
# Sheet directly (col K) instead of calling Claude on every click — when the
# row has a real title, that's the source of truth.
_SCRIPT_ENRICH_FIELDS = (
    "theme", "plot", "wardrobe_f", "wardrobe_m",
    "location", "props", "male", "scene_type", "title",
)

# Minimum first-name length before fuzzy startswith match is allowed.
# "Mia" → "Mia Khalifa" / "Mia Malkova" is too ambiguous; "Scarlett" → "Scarlett Mae" is fine.
_FUZZY_MIN_FIRST_NAME = 4


def enrich_from_script_row(
    conn: sqlite3.Connection,
    *,
    studio: str,
    female: str,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Merge caller-supplied overrides with the latest matching scripts-table row.

    Resolution order per field: overrides[k] (if truthy) → DB value → "".
    Lookup is scoped by studio and ordered by tab_name DESC (newest monthly tab wins).

    Female matching is two-pass: exact case-insensitive first, then a first-word
    startswith fallback (e.g. "Scarlett" → "Scarlett Mae"). The fallback is gated
    on first-name length to avoid common-short-name collisions, and logs a warning
    when it fires so silent mismatches are auditable.

    Returns a dict containing every field in _SCRIPT_ENRICH_FIELDS — empty strings
    for fields the script row didn't have.
    """
    overrides = overrides or {}
    result: dict[str, str] = {k: (overrides.get(k) or "") for k in _SCRIPT_ENRICH_FIELDS}

    if not studio or not female:
        return result

    cols = ", ".join(_SCRIPT_ENRICH_FIELDS)

    # Prefer rows where plot is non-empty, then by newest tab. The same
    # performer appears in multiple monthly tabs — the most recent tab is
    # often a planning row with blank plot/theme, while the row that ACTUALLY
    # has the script written is one or two tabs back. Without the plot-first
    # ordering the helper happily returns an empty row and the title model
    # gets the same empty prompt it had before.
    order_clause = "ORDER BY (CASE WHEN plot != '' THEN 0 ELSE 1 END), tab_name DESC"

    # Pass 1: exact match.
    row = conn.execute(
        f"SELECT {cols} FROM scripts "
        f"WHERE studio = ? AND LOWER(female) = LOWER(?) "
        f"{order_clause} LIMIT 1",
        (studio, female),
    ).fetchone()

    # Pass 2: first-word startswith fallback.
    if row is None:
        first = female.split()[0] if female.split() else ""
        if len(first) >= _FUZZY_MIN_FIRST_NAME:
            row = conn.execute(
                f"SELECT {cols}, female FROM scripts "
                f"WHERE studio = ? AND LOWER(female) LIKE LOWER(? || ' %') "
                f"{order_clause} LIMIT 1",
                (studio, first),
            ).fetchone()
            if row is not None:
                _log.warning(
                    "enrich_from_script_row: fuzzy match — searched %r, matched %r (studio=%s)",
                    female, row["female"], studio,
                )

    if row is None:
        return result

    s = dict(row)
    for k in _SCRIPT_ENRICH_FIELDS:
        # Caller override always wins; only fill from DB when override was empty.
        if not result[k]:
            result[k] = s.get(k) or ""
    return result
