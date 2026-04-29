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
    open_budgets,
    get_or_create_worksheet,
    with_retry,
    fetch_all_rows,
    fetch_as_dicts,
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
    """Sync Tickets tab → tickets table.

    Sheet columns (0-indexed, from ticket_tools.py):
      0  Ticket ID
      1  Date Submitted  → submitted_at
      2  Submitted By
      3  Project
      4  Type
      5  Priority
      6  Title
      7  Description
      8  Status
      9  Approved By     → approved_by (not used in DB, ignored)
      10 Admin Notes     → notes
      11 Assigned To     → assignee
      12 Date Resolved   → resolved_at

    Side effect: detects new tickets and status transitions vs the previous
    DB snapshot and fires notifications. This closes the gap where tickets
    created via ticket_tools.py (Mac → Sheets directly) bypassed the FastAPI
    POST /tickets endpoint and never produced notifications.
    """
    sh = open_tickets()
    # Tab is named "Sheet1" in the actual spreadsheet
    ws = sh.sheet1
    rows = fetch_all_rows(ws)

    with get_db() as conn:
        # Snapshot pre-wipe state so we can diff after re-insert.
        prior_state: dict[str, dict] = {
            r["ticket_id"]: dict(r)
            for r in conn.execute(
                "SELECT ticket_id, status, assignee, submitted_by, title FROM tickets"
            ).fetchall()
        }

        conn.execute("DELETE FROM tickets")
        for row in rows:
            if len(row) < 9 or not row[0]:
                continue
            padded = row + [""] * (13 - len(row))
            conn.execute(
                """INSERT INTO tickets
                   (ticket_id, submitted_at, submitted_by, project, type,
                    priority, title, description, status,
                    notes, assignee, resolved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    padded[0],   # Ticket ID
                    padded[1],   # Date Submitted
                    padded[2],   # Submitted By
                    padded[3],   # Project
                    padded[4],   # Type
                    padded[5],   # Priority
                    padded[6],   # Title
                    padded[7],   # Description
                    padded[8],   # Status
                    padded[10],  # Admin Notes
                    padded[11],  # Assigned To
                    padded[12],  # Date Resolved
                ),
            )

    count = len([r for r in rows if r and r[0]])
    update_sync_meta("tickets", row_count=count)
    _log.info("Synced %d tickets", count)

    # Skip diff-notify on the first-ever sync (empty prior state) — otherwise
    # we'd spam admins with hundreds of "new ticket" notifications.
    if prior_state:
        try:
            _notify_ticket_diffs(prior_state, rows)
        except Exception:
            _log.exception("sync_tickets: notification dispatch failed")

    return count


def _notify_ticket_diffs(prior: dict, current_rows: list) -> None:
    """Fire notifications for newly-appeared tickets and status transitions.

    Called from sync_tickets after the DB has been refreshed. `prior` is the
    pre-sync ticket state keyed by ticket_id; `current_rows` is the raw sheet
    rows we just inserted. We cross-reference them to detect:
      - new ticket_id not present in prior → ticket_created (notify all admins
        except the submitter)
      - status changed from prior → ticket_status (notify submitter)
      - assignee changed and is not empty → ticket_assigned (notify assignee)
    """
    from api.routers.notifications import (
        create_notification,
        notify_multiple,
        get_admin_names,
        TYPE_TICKET_CREATED,
        TYPE_TICKET_STATUS,
        TYPE_TICKET_ASSIGNED,
    )

    # Build current-state map from raw rows (avoid second DB read).
    current: dict[str, dict] = {}
    for row in current_rows:
        if len(row) < 9 or not row[0]:
            continue
        padded = row + [""] * (13 - len(row))
        current[padded[0]] = {
            "ticket_id":    padded[0],
            "submitted_by": padded[2],
            "title":        padded[6],
            "status":       padded[8],
            "assignee":     padded[11],
        }

    admin_names = get_admin_names()

    # Submitter strings vary ("Drew", "andrew", "andrewrowe72@gmail.com",
    # "Claude" — see ticket_tools.py callers). To exclude the submitter from
    # the admin fan-out we match against both name and email of every user.
    with get_db() as conn:
        user_lookup = {
            (dict(r)["email"] or "").lower(): dict(r)["name"]
            for r in conn.execute("SELECT name, email FROM users").fetchall()
        }
        name_lookup = {
            dict(r)["name"].lower(): dict(r)["name"]
            for r in conn.execute("SELECT name FROM users").fetchall()
        }

    def _resolve_submitter_name(submitted_by: str) -> str | None:
        s = (submitted_by or "").strip().lower()
        if not s:
            return None
        if s in user_lookup:
            return user_lookup[s]
        if s in name_lookup:
            return name_lookup[s]
        return None

    new_count = status_count = assign_count = 0

    for tid, cur in current.items():
        prev = prior.get(tid)
        if prev is None:
            # New ticket
            submitter_name = _resolve_submitter_name(cur["submitted_by"])
            recipients = [
                a for a in admin_names
                if not submitter_name or a != submitter_name
            ]
            if recipients:
                # Display the canonical user name when we can resolve it,
                # otherwise fall back to whatever the submitter wrote.
                shown = submitter_name or cur["submitted_by"] or "Someone"
                notify_multiple(
                    recipients,
                    TYPE_TICKET_CREATED,
                    f"New ticket: {tid}",
                    f'{shown} submitted "{cur["title"]}"',
                    "/tickets",
                )
                new_count += 1
        else:
            # Existing ticket — check for status / assignee transitions.
            if cur["status"] and cur["status"] != prev.get("status"):
                # Notify the submitter that their ticket status changed,
                # but only if we can resolve them to a known user.
                submitter_name = _resolve_submitter_name(cur["submitted_by"])
                if submitter_name:
                    create_notification(
                        submitter_name,
                        TYPE_TICKET_STATUS,
                        f"{tid}: {cur['status']}",
                        f'"{cur["title"]}" is now {cur["status"]}',
                        "/tickets",
                    )
                    status_count += 1

            if (
                cur["assignee"]
                and cur["assignee"] != prev.get("assignee")
            ):
                # Notify the new assignee, if they're a known user.
                assignee_name = _resolve_submitter_name(cur["assignee"])
                if assignee_name:
                    create_notification(
                        assignee_name,
                        TYPE_TICKET_ASSIGNED,
                        f"Assigned: {tid}",
                        f'You\'re now on "{cur["title"]}"',
                        "/tickets",
                    )
                    assign_count += 1

    if new_count or status_count or assign_count:
        _log.info(
            "sync_tickets notifications: %d new, %d status, %d assigned",
            new_count, status_count, assign_count,
        )


def sync_notifications() -> int:
    """
    Sync Notifications tab → notifications table.

    Preserves local `read=1` flags when Sheets hasn't caught up yet.
    A user marks-read locally → SQLite updates immediately → the Sheets
    write is fire-and-forget on a thread. If the sync loop runs between
    the SQLite update and the Sheets write, we'd regress read→0 without
    this protection.
    """
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
        # Remember which notifs were locally marked read before we wipe
        locally_read = {
            r[0] for r in conn.execute(
                "SELECT notif_id FROM notifications WHERE read = 1"
            ).fetchall() if r and r[0]
        }
        conn.execute("DELETE FROM notifications")
        for row in rows:
            if len(row) < 6 or not row[0]:
                continue
            padded = row + [""] * (8 - len(row))
            notif_id = padded[0]
            sheets_read = 1 if padded[6].upper() == "TRUE" else 0
            # OR with the local flag — read state is monotonic (unread → read)
            # so once-read-always-read across sync boundaries.
            read_val = 1 if (sheets_read or notif_id in locally_read) else 0
            conn.execute(
                """INSERT INTO notifications
                   (notif_id, timestamp, recipient, type, title, message, read, link)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (notif_id, padded[1], padded[2], padded[3],
                 padded[4], padded[5], read_val, padded[7]),
            )

    count = len([r for r in rows if r and r[0]])
    update_sync_meta("notifications", row_count=count)
    _log.info("Synced %d notifications", count)
    return count


def sync_approvals() -> int:
    """
    Sync Approvals tab → approvals table.

    Reads by HEADER NAME, not positional index, because the sheet was
    originally created by the legacy Streamlit approval_tools.py using
    column order [Approval ID, Date Submitted, Submitted By, Content Type,
    Scene ID, Studio, …] while the v2 schema expects [Approval ID, Scene ID,
    Studio, Content Type, Submitted By, Submitted At, …]. A positional read
    mis-mapped 4 fields in the UI (scene_id showed dates, studio showed
    submitter names, etc.). Header-indexed reads make sync order-agnostic.
    """
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

    # Read all rows *with headers* so we can address columns by name.
    # fetch_as_dicts uses gspread's get_all_records() which handles both
    # legacy and v2 column orders transparently.
    records = fetch_as_dicts(ws)

    # Map sheet column names → db column name. Legacy sheet headers differ
    # from v2 headers for a handful of columns; we accept either.
    # Priority: v2 header → legacy header → "".
    def pick(rec: dict, *keys: str) -> str:
        for k in keys:
            v = rec.get(k)
            if v not in (None, ""):
                return str(v)
        return ""

    with get_db() as conn:
        conn.execute("DELETE FROM approvals")
        count = 0
        for rec in records:
            approval_id = pick(rec, "Approval ID")
            if not approval_id:
                continue
            conn.execute(
                """INSERT OR REPLACE INTO approvals
                   (approval_id, scene_id, studio, content_type,
                    submitted_by, submitted_at, status, decided_by,
                    decided_at, content_json, notes, linked_ticket,
                    target_sheet, target_range, superseded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    approval_id,
                    pick(rec, "Scene ID"),
                    pick(rec, "Studio"),
                    pick(rec, "Content Type"),
                    pick(rec, "Submitted By"),
                    # Legacy sheet called this "Date Submitted"
                    pick(rec, "Submitted At", "Date Submitted"),
                    pick(rec, "Status"),
                    # Legacy sheet called this "Approved By"
                    pick(rec, "Decided By", "Approved By"),
                    # Legacy sheet called this "Date Decided"
                    pick(rec, "Decided At", "Date Decided"),
                    pick(rec, "Content JSON"),
                    # Legacy sheet called this "Admin Notes"
                    pick(rec, "Notes", "Admin Notes"),
                    pick(rec, "Linked Ticket"),
                    pick(rec, "Target Sheet"),
                    pick(rec, "Target Range"),
                    pick(rec, "Superseded By"),
                ),
            )
            count += 1

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

    # Grail tab name → scene ID prefix used in MEGA folders and the scenes table.
    # NaughtyJOI's Grail tab is "NNJOI" but MEGA uses "NJOI" as the prefix.
    TAB_TO_PREFIX = {"FPVR": "FPVR", "VRH": "VRH", "VRA": "VRA", "NNJOI": "NJOI"}

    for ui_name, tab_name in settings.grail_tabs.items():
        try:
            ws = grail_sh.worksheet(tab_name)
            rows = fetch_all_rows(ws)
        except Exception as exc:
            _log.warning("Failed to read Grail tab %s: %s", tab_name, exc)
            continue

        prefix = TAB_TO_PREFIX.get(tab_name, tab_name)
        site_code = settings.studio_site_codes.get(ui_name, "")

        for row_idx, row in enumerate(rows, start=2):  # Row 2 = first data row
            if len(row) < 5 or not row[1]:
                continue
            # Grail column B holds the Scene# (just the digits). The full scene
            # ID is <prefix><4-digit zero-padded number> to match MEGA folder
            # names (e.g. "NJOI0003", "FPVR0042") and avoid cross-studio
            # collisions that were wiping out whole studios.
            raw = row[1].strip()
            try:
                scene_num = f"{int(raw):04d}"
            except ValueError:
                _log.debug("Skipping non-numeric scene# %r in %s row %d", raw, tab_name, row_idx)
                continue
            scene_id = f"{prefix}{scene_num}"
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
        # Snapshot the current MEGA-derived flags so we can preserve them
        # when a scene is missing from mega_scan.json. Without this, a
        # partial scan (recent-only, or one that dropped a path) would reset
        # has_description/has_videos/etc to 0 for every older scene, and the
        # Shoot Tracker / Asset Tracker would show blank cells for scenes
        # whose assets exist in MEGA but simply weren't re-scanned this run.
        prior_flags: dict[str, dict] = {}
        try:
            for row in conn.execute(
                """SELECT id, has_description, has_videos, video_count,
                          has_thumbnail, has_photos, has_storyboard,
                          storyboard_count, mega_path, thumb_file
                     FROM scenes"""
            ).fetchall():
                d = dict(row)
                prior_flags[d["id"]] = d
        except Exception as exc:
            _log.warning("Could not snapshot prior scene flags: %s", exc)

        conn.execute("DELETE FROM scenes")
        for scene_id, grail in grail_scenes.items():
            mega = mega_data.get(scene_id, {})
            prior = prior_flags.get(scene_id) if scene_id not in mega_data else None
            is_comp = 1 if any(
                kw in grail.get("title", "").lower()
                for kw in ("vol.", "best", "compilation")
            ) else 0
            # Pull the first thumbnail filename (e.g. "FPVR0282-..._Thumbnail.jpg")
            # so the /scenes/{id}/thumbnail proxy endpoint can find the file
            # in MEGA without re-reading mega_scan.json on every request.
            thumb_files = mega.get("files", {}).get("thumbnail", [])
            thumb_file = ""
            if thumb_files:
                # Paths in the scan are relative: "Video Thumbnail/xxx.jpg"
                first = thumb_files[0]
                thumb_file = first.split("/", 1)[1] if "/" in first else first

            if prior is not None:
                # Scene is in Grail but missing from this scan's mega_data —
                # preserve the last-known flags instead of resetting to 0.
                has_desc_v     = prior.get("has_description") or 0
                has_videos_v   = prior.get("has_videos") or 0
                video_count_v  = prior.get("video_count") or 0
                has_thumb_v    = prior.get("has_thumbnail") or 0
                has_photos_v   = prior.get("has_photos") or 0
                has_story_v    = prior.get("has_storyboard") or 0
                story_count_v  = prior.get("storyboard_count") or 0
                mega_path_v    = prior.get("mega_path") or ""
                thumb_file_v   = prior.get("thumb_file") or ""
            else:
                has_desc_v     = 1 if mega.get("has_description") else 0
                has_videos_v   = 1 if mega.get("has_videos") else 0
                video_count_v  = mega.get("video_count", 0)
                has_thumb_v    = 1 if mega.get("has_thumbnail") else 0
                has_photos_v   = 1 if mega.get("has_photos") else 0
                has_story_v    = 1 if mega.get("has_storyboard") else 0
                story_count_v  = mega.get("storyboard_count", 0)
                mega_path_v    = mega.get("path", "")
                thumb_file_v   = thumb_file

            conn.execute(
                """INSERT INTO scenes
                   (id, studio, grail_tab, site_code, title, performers,
                    categories, tags, grail_row,
                    has_description, has_videos, video_count,
                    has_thumbnail, has_photos, has_storyboard,
                    storyboard_count, mega_path, thumb_file, is_compilation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    has_desc_v,
                    has_videos_v,
                    video_count_v,
                    has_thumb_v,
                    has_photos_v,
                    has_story_v,
                    story_count_v,
                    mega_path_v,
                    thumb_file_v,
                    is_comp,
                ),
            )

    count = len(grail_scenes)
    # Pre-aggregate scene stats so /api/scenes/stats doesn't re-scan the table
    # on every dashboard render. Recomputed here means it always tracks the
    # current sync's snapshot — no chance of drift.
    _refresh_scene_stats_cache()

    update_sync_meta("scenes", row_count=count)
    _log.info("Synced %d scenes (Grail + MEGA)", count)
    return count


def _refresh_scene_stats_cache() -> None:
    """Recompute the scene_stats_cache table from the current scenes table.

    Called from the tail of sync_scenes. Cheap (3 aggregates over ~1000 rows),
    runs once per sync instead of three table scans on every API call.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        total_row = conn.execute("SELECT COUNT(*) AS cnt FROM scenes").fetchone()
        total = dict(total_row)["cnt"]

        complete_total_row = conn.execute(
            """SELECT COUNT(*) AS cnt FROM scenes
                WHERE has_description=1 AND has_videos=1
                  AND has_thumbnail=1 AND has_photos=1 AND has_storyboard=1"""
        ).fetchone()
        complete_total = dict(complete_total_row)["cnt"]

        per_studio = conn.execute(
            """SELECT studio,
                      COUNT(*) AS cnt,
                      SUM(CASE WHEN has_description=1 AND has_videos=1
                               AND has_thumbnail=1 AND has_photos=1
                               AND has_storyboard=1 THEN 1 ELSE 0 END) AS complete_cnt
                 FROM scenes GROUP BY studio"""
        ).fetchall()

        conn.execute("DELETE FROM scene_stats_cache")
        conn.execute(
            "INSERT INTO scene_stats_cache (studio, scene_count, complete_count, updated_at) VALUES (?, ?, ?, ?)",
            ("TOTAL", total, complete_total, now),
        )
        for r in per_studio:
            d = dict(r)
            conn.execute(
                "INSERT INTO scene_stats_cache (studio, scene_count, complete_count, updated_at) VALUES (?, ?, ?, ?)",
                (d["studio"], d["cnt"], d["complete_cnt"] or 0, now),
            )


def sync_scripts() -> int:
    """
    Sync Scripts sheet (monthly tabs) → scripts table.

    Processes current month + last 2 months. Each tab is fully replaced
    on sync to keep data fresh without accumulating stale rows.

    Sheet columns (0-indexed):
      A=0 Date, B=1 Studio, C=2 Location, D=3 Scene, E=4 Female,
      F=5 Male, G=6 Theme, H=7 WardrobeF, I=8 WardrobeM,
      J=9 Plot, K=10 Title, L=11 Props, M=12 Status
    """
    import re
    from calendar import month_name

    sh = open_scripts()
    all_titles = [ws.title for ws in sh.worksheets()]

    # Filter to tabs matching "Month YYYY" pattern
    month_pattern = re.compile(
        r"^(" + "|".join(month_name[1:]) + r")\s+\d{4}$",
        re.IGNORECASE,
    )
    valid_tabs = [t for t in all_titles if month_pattern.match(t)]

    if not valid_tabs:
        _log.warning("sync_scripts: no monthly tabs found in Scripts sheet")
        update_sync_meta("scripts", row_count=0)
        return 0

    # Sort tabs by date (most recent first), take current + last 2
    def _tab_sort_key(tab_name: str):
        parts = tab_name.rsplit(" ", 1)
        try:
            month_idx = list(month_name).index(parts[0].capitalize())
            year = int(parts[1])
            return (year, month_idx)
        except (ValueError, IndexError):
            return (0, 0)

    # Window: 6 months past through 2 months future. The forward window is
    # what the user actually plans into — they create the next-month tab
    # and start dropping shoot rows in well before the month begins. Earlier
    # logic excluded all future tabs and broke planning workflow on the very
    # last day of the prior month.
    now_dt = datetime.now(timezone.utc)
    now_epoch = now_dt.year * 12 + now_dt.month
    def _within_sync_window(tab_name: str) -> bool:
        parts = tab_name.rsplit(" ", 1)
        try:
            month_idx = list(month_name).index(parts[0].capitalize())
            year = int(parts[1])
        except (ValueError, IndexError):
            return False
        delta = (year * 12 + month_idx) - now_epoch
        return -6 <= delta <= 2

    windowed_tabs = [t for t in valid_tabs if _within_sync_window(t)]
    sorted_tabs = sorted(windowed_tabs, key=_tab_sort_key, reverse=True)
    tabs_to_sync = sorted_tabs[:5]  # near future + current + recent past

    now = datetime.now(timezone.utc).isoformat()
    total_count = 0

    for tab_name in tabs_to_sync:
        try:
            ws = sh.worksheet(tab_name)
            rows = fetch_all_rows(ws)
        except Exception as exc:
            _log.warning("sync_scripts: failed to read tab %s: %s", tab_name, exc)
            continue

        with get_db() as conn:
            # Delete existing rows for this tab before re-inserting
            conn.execute("DELETE FROM scripts WHERE tab_name = ?", (tab_name,))

            for row_idx, row in enumerate(rows, start=2):  # Row 2 = first data row
                # Skip rows where studio column (index 1) is empty
                if len(row) < 2 or not row[1].strip():
                    continue

                padded = row + [""] * (13 - len(row))
                conn.execute(
                    """INSERT INTO scripts
                       (tab_name, sheet_row, studio, shoot_date, location,
                        scene_type, female, male, theme, wardrobe_f,
                        wardrobe_m, plot, title, props, script_status, synced_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        tab_name,
                        row_idx,
                        padded[1].strip(),   # Studio
                        padded[0].strip(),   # Date
                        padded[2].strip(),   # Location
                        padded[3].strip(),   # Scene type
                        padded[4].strip(),   # Female
                        padded[5].strip(),   # Male
                        padded[6].strip(),   # Theme
                        padded[7].strip(),   # WardrobeF
                        padded[8].strip(),   # WardrobeM
                        padded[9].strip(),   # Plot
                        padded[10].strip(),  # Title
                        padded[11].strip(),  # Props
                        padded[12].strip(),  # Status
                        now,
                    ),
                )
                total_count += 1

        _log.info("sync_scripts: synced tab %s (%d rows)", tab_name, total_count)

    update_sync_meta("scripts", row_count=total_count)
    _log.info("Synced %d script rows across %d tabs", total_count, len(tabs_to_sync))
    return total_count


def sync_bookings() -> int:
    """Sync Booking sheet → bookings table.

    The Booking spreadsheet has one tab per agency after three utility tabs
    (📋 Legend, 🔍 Search, 📊 Dashboard).  Each agency tab has:
      Row 1  — agency name in col A
      Row 2  — website / link row (first http URL becomes agency_link)
      Row 3  — column headers: Name, Age, Last Booked Date, Bookings, Location, AVG Rate, Rank, …, Notes, …
      Row 4+ — model data rows
    """
    sh = open_booking()

    # The three non-agency utility tabs always carry these exact names.
    SKIP_TABS = {"📋 Legend", "🔍 Search", "📊 Dashboard"}
    agency_tabs = [ws for ws in sh.worksheets() if ws.title not in SKIP_TABS]

    total_count = 0

    with get_db() as conn:
        conn.execute("DELETE FROM bookings")

        for ws in agency_tabs:
            agency_name = ws.title
            try:
                # include_header=True so we see all rows (agency header + website + col headers + data)
                all_rows = fetch_all_rows(ws, include_header=True)
            except Exception as exc:
                _log.warning("sync_bookings: failed to read tab %s: %s", agency_name, exc)
                continue

            if len(all_rows) < 4:
                continue

            # Row index 1 = website/link row — scan for first http URL
            agency_link = ""
            for cell in (all_rows[1] if len(all_rows) > 1 else []):
                if cell.strip().startswith("http"):
                    agency_link = cell.strip()
                    break

            # Row index 2 = column headers — build header → index map
            header_row = all_rows[2] if len(all_rows) > 2 else []
            col_map = {h.strip().lower(): i for i, h in enumerate(header_row) if h.strip()}

            def _get(row: list, *keys: str) -> str:
                """Return first non-empty value from the given header keys (case-insensitive)."""
                for key in keys:
                    idx = col_map.get(key)
                    if idx is not None and idx < len(row):
                        v = row[idx].strip()
                        if v:
                            return v
                return ""

            # Row index 3+ = model data
            for row in all_rows[3:]:
                if not row or not row[0].strip():
                    continue
                name = row[0].strip()
                if name.lower() in ("name", "model", "performer"):
                    continue

                rate = _get(row, "avg rate", "rate")
                rank = _get(row, "rank")
                notes = _get(row, "notes", "available for")

                # Operational metadata → compact info string
                age           = _get(row, "age")
                last_booked   = _get(row, "last booked date", "last booked")
                bookings_cnt  = _get(row, "bookings")
                location      = _get(row, "location")
                parts = []
                if age:          parts.append(f"Age: {age}")
                if last_booked:  parts.append(f"Last booked: {last_booked}")
                if bookings_cnt: parts.append(f"Bookings: {bookings_cnt}")
                if location:     parts.append(f"Location: {location}")
                info = " · ".join(parts)

                # Store all sheet columns as a header-keyed dict so the API
                # can expose platform stats (SLR/VRP followers, etc.) without re-syncing.
                row_dict = {
                    header_row[i].strip().lower(): row[i].strip()
                    for i in range(min(len(header_row), len(row)))
                    if i < len(header_row) and header_row[i].strip()
                    and i < len(row) and row[i].strip()
                }

                conn.execute(
                    """INSERT INTO bookings (name, agency, agency_link, rate, rank, notes, info, raw_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name, agency_name, agency_link, rate, rank, notes, info, json.dumps(row_dict)),
                )
                total_count += 1

    update_sync_meta("bookings", row_count=total_count)
    _log.info("Synced %d bookings from %d agency tabs", total_count, len(agency_tabs))
    return total_count


def sync_budgets() -> int:
    """Sync Budgets sheet → budgets table.

    The Budgets sheet has one tab per month; each row holds a shoot date,
    female talent, female rate, and male rate. Mirrored locally so the shoots
    endpoint doesn't need to touch the Sheets API on every request.

    Column layout (0-indexed):
      0  Date           — first token = the date itself
      4  Female talent
      6  Female rate    — raw number; formatted "$X,XXX" on read
      10 Male rate      — raw number; formatted "$X,XXX" on read

    Dates are normalized to YYYY-MM-DD and (date, female.lower()) is the
    primary key — same shape as the legacy in-router cache so callers can
    swap the data source without changing their lookup logic.
    """
    months = ("january", "february", "march", "april", "may", "june",
              "july", "august", "september", "october", "november", "december")

    try:
        wb = open_budgets()
    except Exception as exc:
        _log.warning("sync_budgets: failed to open Budgets sheet: %s", exc)
        update_sync_meta("budgets", status="error", error=str(exc))
        return 0

    rows_to_insert: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    for ws in wb.worksheets():
        if not any(m in ws.title.lower() for m in months):
            continue
        try:
            rows = with_retry(ws.get_all_values)
        except Exception as exc:
            _log.warning("sync_budgets: read failed for tab %s: %s", ws.title, exc)
            continue
        if not rows:
            continue

        for row in rows[1:]:
            if len(row) < 5 or not row[0].strip() or not row[4].strip():
                continue
            raw_date = row[0].strip().split(" ")[0].split("T")[0]
            parts = raw_date.replace("/", "-").split("-")
            if len(parts) != 3:
                continue
            if len(parts[0]) == 4:
                date_str = raw_date.replace("/", "-")
            else:
                m_p, d_p, y_p = parts
                y_full = "20" + y_p if len(y_p) == 2 else y_p
                date_str = "{}-{}-{}".format(y_full, m_p.zfill(2), d_p.zfill(2))

            f_talent = row[4].strip()
            f_rate_raw = row[6].strip() if len(row) > 6 else ""
            m_rate_raw = row[10].strip() if len(row) > 10 else ""

            def _fmt(v: str) -> str:
                if not v:
                    return ""
                try:
                    return "${:,}".format(int(float(v)))
                except (ValueError, TypeError):
                    return v

            key = (date_str, f_talent.lower())
            if key in seen:
                # Mirror the legacy "first occurrence wins" behaviour so we
                # don't flap between tabs that duplicate the same shoot.
                continue
            seen.add(key)
            rows_to_insert.append((date_str, f_talent.lower(), _fmt(f_rate_raw), _fmt(m_rate_raw)))

    with get_db() as conn:
        conn.execute("DELETE FROM budgets")
        for date_str, female_lower, f_rate, m_rate in rows_to_insert:
            conn.execute(
                """INSERT OR REPLACE INTO budgets
                   (shoot_date, female_lower, female_rate, male_rate)
                   VALUES (?, ?, ?, ?)""",
                (date_str, female_lower, f_rate, m_rate),
            )

    update_sync_meta("budgets", row_count=len(rows_to_insert))
    _log.info("Synced %d budget rows", len(rows_to_insert))
    return len(rows_to_insert)


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
        ("scripts", sync_scripts),
        ("bookings", sync_bookings),
        ("budgets", sync_budgets),
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
