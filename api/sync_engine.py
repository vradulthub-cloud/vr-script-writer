"""
Sync engine: Google Sheets → SQLite mirror.

Runs on a schedule (default: every 5 minutes) and pulls changes from
all 6 Google Sheets into the local SQLite database. This eliminates
Sheets API latency from the hot path — all reads go to SQLite.

Sync order:
  1. Users (auth_config — needed first for permission checks)
  2. Tickets
  3. Notifications
  4. Approvals
  5. Scenes (Grail + Scripts + MEGA scan joined)
  6. Bookings

Each sync is independent — a failure in one doesn't block others.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

from api.config import get_settings
from api.database import get_db, update_sync_meta, init_db
from api.sheets_client import (
    open_tickets,
    open_grail,
    open_scripts,
    open_booking,
    get_or_create_worksheet,
    with_retry,
    fetch_all_rows,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual sync functions
# ---------------------------------------------------------------------------

def sync_users() -> int:
    """Sync Users tab → users table."""
    sh = open_tickets()
    ws = get_or_create_worksheet(sh, "Users")
    rows = fetch_all_rows(ws)

    with get_db() as conn:
        conn.execute("DELETE FROM users")
        for row in rows:
            if len(row) < 4 or not row[0]:
                continue
            conn.execute(
                "INSERT INTO users (email, name, role, allowed_tabs) VALUES (?, ?, ?, ?)",
                (row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip() if len(row) > 3 else ""),
            )

    count = len([r for r in rows if r and r[0]])
    update_sync_meta("users", row_count=count)
    _log.info("Synced %d users", count)
    return count


def sync_tickets() -> int:
    """Sync Tickets tab → tickets table."""
    sh = open_tickets()
    ws = get_or_create_worksheet(
        sh,
        "Tickets",
        headers=[
            "Ticket ID", "Title", "Description", "Project", "Type",
            "Priority", "Status", "Submitted By", "Submitted At",
            "Assignee", "Notes", "Resolved At", "Linked Items",
        ],
    )
    rows = fetch_all_rows(ws)

    with get_db() as conn:
        conn.execute("DELETE FROM tickets")
        for row in rows:
            if len(row) < 7 or not row[0]:
                continue
            # Pad row to 13 columns
            padded = row + [""] * (13 - len(row))
            conn.execute(
                """INSERT INTO tickets
                   (ticket_id, title, description, project, type,
                    priority, status, submitted_by, submitted_at,
                    assignee, notes, resolved_at, linked_items)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                padded[:13],
            )

    count = len([r for r in rows if r and r[0]])
    update_sync_meta("tickets", row_count=count)
    _log.info("Synced %d tickets", count)
    return count


def sync_notifications() -> int:
    """Sync Notifications tab → notifications table."""
    sh = open_tickets()
    ws = get_or_create_worksheet(
        sh,
        "Notifications",
        headers=[
            "ID", "Timestamp", "Recipient", "Type",
            "Title", "Message", "Read", "Link",
        ],
    )
    rows = fetch_all_rows(ws)

    with get_db() as conn:
        conn.execute("DELETE FROM notifications")
        for row in rows:
            if len(row) < 6 or not row[0]:
                continue
            padded = row + [""] * (8 - len(row))
            read_val = 1 if padded[6].upper() == "TRUE" else 0
            conn.execute(
                """INSERT INTO notifications
                   (notif_id, timestamp, recipient, type, title, message, read, link)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (padded[0], padded[1], padded[2], padded[3],
                 padded[4], padded[5], read_val, padded[7]),
            )

    count = len([r for r in rows if r and r[0]])
    update_sync_meta("notifications", row_count=count)
    _log.info("Synced %d notifications", count)
    return count


def sync_approvals() -> int:
    """Sync Approvals tab → approvals table."""
    sh = open_tickets()
    ws = get_or_create_worksheet(
        sh,
        "Approvals",
        headers=[
            "Approval ID", "Scene ID", "Studio", "Content Type",
            "Submitted By", "Submitted At", "Status", "Decided By",
            "Decided At", "Content JSON", "Notes", "Linked Ticket",
            "Target Sheet", "Target Range", "Superseded By",
        ],
    )
    rows = fetch_all_rows(ws)

    with get_db() as conn:
        conn.execute("DELETE FROM approvals")
        for row in rows:
            if len(row) < 6 or not row[0]:
                continue
            padded = row + [""] * (15 - len(row))
            conn.execute(
                """INSERT OR REPLACE INTO approvals
                   (approval_id, scene_id, studio, content_type,
                    submitted_by, submitted_at, status, decided_by,
                    decided_at, content_json, notes, linked_ticket,
                    target_sheet, target_range, superseded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                padded[:15],
            )

    count = len([r for r in rows if r and r[0]])
    update_sync_meta("approvals", row_count=count)
    _log.info("Synced %d approvals", count)
    return count


def sync_scenes() -> int:
    """
    Sync Grail + Scripts + MEGA scan → scenes table.

    This is the most complex sync — it joins data from three sources:
      1. Grail sheet (4 studio tabs): scene ID, title, performers, cats, tags
      2. Scripts sheet (monthly tabs): plot, theme, female, male, wardrobe
      3. mega_scan.json (local file): asset status (desc, videos, thumb, photos, etc.)
    """
    settings = get_settings()

    # --- Load Grail data ---
    grail_sh = open_grail()
    grail_scenes: dict[str, dict] = {}

    for ui_name, tab_name in settings.grail_tabs.items():
        try:
            ws = grail_sh.worksheet(tab_name)
            rows = fetch_all_rows(ws)
        except Exception as exc:
            _log.warning("Failed to read Grail tab %s: %s", tab_name, exc)
            continue

        for row_idx, row in enumerate(rows, start=2):  # Row 2 = first data row
            if len(row) < 5 or not row[1]:
                continue
            scene_id = row[1].strip()
            site_code = settings.studio_site_codes.get(ui_name, "")
            grail_scenes[scene_id] = {
                "studio": ui_name,
                "grail_tab": tab_name,
                "site_code": site_code,
                "title": row[3].strip() if len(row) > 3 else "",
                "performers": row[4].strip() if len(row) > 4 else "",
                "categories": row[5].strip() if len(row) > 5 else "",
                "tags": row[6].strip() if len(row) > 6 else "",
                "grail_row": row_idx,
            }

    # --- Load MEGA scan data ---
    mega_path = settings.base_dir / "mega_scan.json"
    mega_data: dict[str, dict] = {}
    if mega_path.exists():
        try:
            with open(mega_path, "r") as f:
                mega_raw = json.load(f)
            # mega_scan.json structure: {"scenes": [{scene_id: "VRH0758", ...}, ...]}
            scenes_list = mega_raw.get("scenes", [])
            if isinstance(scenes_list, list):
                mega_data = {s["scene_id"]: s for s in scenes_list if "scene_id" in s}
            elif isinstance(scenes_list, dict):
                mega_data = scenes_list
        except Exception as exc:
            _log.warning("Failed to read mega_scan.json: %s", exc)

    # --- Merge into scenes table ---
    with get_db() as conn:
        conn.execute("DELETE FROM scenes")
        for scene_id, grail in grail_scenes.items():
            mega = mega_data.get(scene_id, {})
            is_comp = 1 if any(
                kw in grail.get("title", "").lower()
                for kw in ("vol.", "best", "compilation")
            ) else 0
            conn.execute(
                """INSERT INTO scenes
                   (id, studio, grail_tab, site_code, title, performers,
                    categories, tags, grail_row,
                    has_description, has_videos, video_count,
                    has_thumbnail, has_photos, has_storyboard,
                    storyboard_count, mega_path, is_compilation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    scene_id,
                    grail["studio"],
                    grail["grail_tab"],
                    grail["site_code"],
                    grail["title"],
                    grail["performers"],
                    grail["categories"],
                    grail["tags"],
                    grail["grail_row"],
                    1 if mega.get("has_description") else 0,
                    1 if mega.get("has_videos") else 0,
                    mega.get("video_count", 0),
                    1 if mega.get("has_thumbnail") else 0,
                    1 if mega.get("has_photos") else 0,
                    1 if mega.get("has_storyboard") else 0,
                    mega.get("storyboard_count", 0),
                    mega.get("path", ""),
                    is_comp,
                ),
            )

    count = len(grail_scenes)
    update_sync_meta("scenes", row_count=count)
    _log.info("Synced %d scenes (Grail + MEGA)", count)
    return count


def sync_bookings() -> int:
    """Sync Booking sheet → bookings table."""
    sh = open_booking()
    ws = sh.sheet1
    rows = fetch_all_rows(ws)

    with get_db() as conn:
        conn.execute("DELETE FROM bookings")
        for row in rows:
            if len(row) < 2 or not row[0]:
                continue
            conn.execute(
                """INSERT INTO bookings (name, agency, agency_link, rate, notes, raw_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    row[0].strip(),
                    row[1].strip() if len(row) > 1 else "",
                    row[2].strip() if len(row) > 2 else "",
                    row[3].strip() if len(row) > 3 else "",
                    row[4].strip() if len(row) > 4 else "",
                    json.dumps(row),
                ),
            )

    count = len([r for r in rows if r and r[0]])
    update_sync_meta("bookings", row_count=count)
    _log.info("Synced %d bookings", count)
    return count


# ---------------------------------------------------------------------------
# Full sync — runs all individual syncs
# ---------------------------------------------------------------------------

def run_full_sync() -> dict[str, int | str]:
    """
    Run a full sync of all data sources.

    Returns a dict with source names → row counts (or error strings).
    Each sync is independent — a failure in one doesn't block others.
    """
    results: dict[str, int | str] = {}

    syncs = [
        ("users", sync_users),
        ("tickets", sync_tickets),
        ("notifications", sync_notifications),
        ("approvals", sync_approvals),
        ("scenes", sync_scenes),
        ("bookings", sync_bookings),
    ]

    for name, func in syncs:
        try:
            count = func()
            results[name] = count
        except Exception as exc:
            _log.error("Sync failed for %s: %s", name, exc, exc_info=True)
            results[name] = f"ERROR: {exc}"
            update_sync_meta(name, status="error", error=str(exc))

    return results


# ---------------------------------------------------------------------------
# Background sync thread
# ---------------------------------------------------------------------------

_sync_thread: threading.Thread | None = None
_sync_stop_event = threading.Event()


def start_sync_loop() -> None:
    """Start the background sync loop (runs every N seconds)."""
    global _sync_thread

    if _sync_thread and _sync_thread.is_alive():
        _log.warning("Sync loop already running")
        return

    settings = get_settings()
    interval = settings.sheets_sync_interval_seconds

    def _loop():
        _log.info("Sync loop started (interval=%ds)", interval)
        # Initial sync on startup
        init_db()
        run_full_sync()

        while not _sync_stop_event.is_set():
            _sync_stop_event.wait(interval)
            if not _sync_stop_event.is_set():
                try:
                    run_full_sync()
                except Exception as exc:
                    _log.error("Sync loop error: %s", exc, exc_info=True)

        _log.info("Sync loop stopped")

    _sync_stop_event.clear()
    _sync_thread = threading.Thread(target=_loop, daemon=True, name="sheets-sync")
    _sync_thread.start()


def stop_sync_loop() -> None:
    """Stop the background sync loop."""
    _sync_stop_event.set()
    if _sync_thread:
        _sync_thread.join(timeout=5)
