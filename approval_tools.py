"""
approval_tools.py
Handles content approval workflow for the Eclatech Hub.
Backend: Google Sheets ("Eclatech Tickets" → "Approvals" tab)
"""

import json
import os
import time
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread

# ── Configuration ─────────────────────────────────────────────────────────────
SHEET_ID = os.environ.get("TICKETS_SHEET_ID", "1t92DvQxZzgHKjp4-uxaPLdyaqlmcGNLxSd6qx8hANyA")
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TAB_NAME = "Approvals"
CONTENT_TYPES = ["script", "description", "title_text", "title_card"]
STATUSES = ["Pending", "Approved", "Rejected", "Superseded"]

# Column indices (0-based)
COL_ID = 0
COL_DATE = 1
COL_SUBMITTED_BY = 2
COL_TYPE = 3
COL_SCENE_ID = 4
COL_STUDIO = 5
COL_STATUS = 6
COL_PREVIEW = 7
COL_JSON = 8
COL_APPROVED_BY = 9
COL_DATE_DECIDED = 10
COL_NOTES = 11
COL_LINKED_TICKET = 12
COL_TARGET = 13
COL_VERSION = 14

HEADERS = [
    "Approval ID", "Date Submitted", "Submitted By", "Content Type",
    "Scene ID", "Studio", "Status", "Content Preview", "Content JSON",
    "Approved By", "Date Decided", "Admin Notes", "Linked Ticket",
    "Target Sheet", "Version",
]

# ── Sheet client (reuse ticket_tools pattern) ────────────────────────────────
_cached_client = None
_cached_at = 0


def _get_client():
    global _cached_client, _cached_at
    now = time.time()
    if _cached_client and (now - _cached_at) < 1800:
        return _cached_client
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    _cached_client = gspread.authorize(creds)
    _cached_at = now
    return _cached_client


def _get_worksheet():
    """Get the Approvals worksheet, creating it + headers if needed."""
    gc = _get_client()
    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=TAB_NAME, rows=500, cols=15)
    first_row = ws.row_values(1)
    if not first_row or first_row[0] != "Approval ID":
        ws.update("A1:O1", [HEADERS])
        ws.format("A1:O1", {"textFormat": {"bold": True}})
        ws.freeze(rows=1)
    return ws


# ── Read operations ──────────────────────────────────────────────────────────

def load_approvals(status_filter=None):
    """Load all approval items. Optionally filter by status."""
    ws = _get_worksheet()
    rows = ws.get_all_values()
    if len(rows) <= 1:
        return []
    items = []
    for i, row in enumerate(rows[1:], start=2):
        row = row + [""] * (15 - len(row))
        item = {
            "row_index": i,
            "id": row[COL_ID],
            "date": row[COL_DATE],
            "submitted_by": row[COL_SUBMITTED_BY],
            "content_type": row[COL_TYPE],
            "scene_id": row[COL_SCENE_ID],
            "studio": row[COL_STUDIO],
            "status": row[COL_STATUS],
            "preview": row[COL_PREVIEW],
            "content_json": row[COL_JSON],
            "approved_by": row[COL_APPROVED_BY],
            "date_decided": row[COL_DATE_DECIDED],
            "notes": row[COL_NOTES],
            "linked_ticket": row[COL_LINKED_TICKET],
            "target_sheet": row[COL_TARGET],
            "version": row[COL_VERSION],
        }
        if status_filter and item["status"] != status_filter:
            continue
        items.append(item)
    return items


def get_pending_count():
    """Quick count of Pending items."""
    return len(load_approvals(status_filter="Pending"))


def get_pending_for_scene(scene_id):
    """Get all Pending approvals for a given scene ID."""
    return [a for a in load_approvals(status_filter="Pending")
            if a["scene_id"] == scene_id]


def get_next_id(approvals=None):
    """Generate the next approval ID (APR-0001)."""
    if approvals is None:
        approvals = load_approvals()
    if not approvals:
        return "APR-0001"
    max_num = 0
    for a in approvals:
        aid = a["id"]
        if aid.startswith("APR-"):
            try:
                num = int(aid.split("-")[1])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                pass
    return f"APR-{max_num + 1:04d}"


# ── Write operations ─────────────────────────────────────────────────────────

def submit_for_approval(submitted_by, content_type, scene_id, studio,
                        content_preview, content_json, target_sheet,
                        linked_ticket=""):
    """Create a pending approval item. Returns the approval ID.
    Marks any prior Pending items for same scene+type as Superseded."""
    ws = _get_worksheet()
    approvals = load_approvals()

    # Supersede prior pending items for same scene + type
    for a in approvals:
        if (a["status"] == "Pending"
                and a["scene_id"] == scene_id
                and a["content_type"] == content_type):
            ws.update_cell(a["row_index"], COL_STATUS + 1, "Superseded")

    # Calculate version
    prior_versions = [a for a in approvals
                      if a["scene_id"] == scene_id and a["content_type"] == content_type]
    version = len(prior_versions) + 1

    approval_id = get_next_id(approvals)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    new_row = [
        approval_id,
        now,
        submitted_by,
        content_type,
        scene_id,
        studio,
        "Pending",
        content_preview[:200],
        content_json,
        "",   # approved_by
        "",   # date_decided
        "",   # notes
        linked_ticket,
        target_sheet,
        str(version),
    ]
    ws.append_row(new_row, value_input_option="USER_ENTERED")
    return approval_id


def approve_item(row_index, approved_by, notes=""):
    """Mark item as Approved and execute the write to target sheet.
    Returns the approval dict."""
    ws = _get_worksheet()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    ws.update_cell(row_index, COL_STATUS + 1, "Approved")
    ws.update_cell(row_index, COL_APPROVED_BY + 1, approved_by)
    ws.update_cell(row_index, COL_DATE_DECIDED + 1, now)
    if notes:
        ws.update_cell(row_index, COL_NOTES + 1, notes)

    # Reload the row to get full data for execution
    row = ws.row_values(row_index)
    row = row + [""] * (15 - len(row))
    approval = {
        "id": row[COL_ID],
        "content_type": row[COL_TYPE],
        "scene_id": row[COL_SCENE_ID],
        "studio": row[COL_STUDIO],
        "content_json": row[COL_JSON],
        "target_sheet": row[COL_TARGET],
        "linked_ticket": row[COL_LINKED_TICKET],
    }

    # Execute the write
    execute_approval_write(approval)

    # Progress linked ticket if present
    if approval["linked_ticket"]:
        try:
            import ticket_tools
            ticket_tools.progress_ticket(
                approval["linked_ticket"],
                new_status="In Review",
                notes=f"Content approved: {approval['id']} ({approval['content_type']})",
                by=approved_by,
            )
        except Exception:
            pass

    return approval


def reject_item(row_index, rejected_by, notes):
    """Mark item as Rejected with mandatory notes."""
    if not notes.strip():
        raise ValueError("Rejection notes are required")
    ws = _get_worksheet()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ws.update_cell(row_index, COL_STATUS + 1, "Rejected")
    ws.update_cell(row_index, COL_APPROVED_BY + 1, rejected_by)
    ws.update_cell(row_index, COL_DATE_DECIDED + 1, now)
    ws.update_cell(row_index, COL_NOTES + 1, notes)


# ── Target sheet write execution ─────────────────────────────────────────────

def execute_approval_write(approval):
    """Parse target_sheet and write content_json to the appropriate destination.

    Target formats:
      Scripts:{month_tab}:{row}     → write script fields to Scripts sheet
      Grail:{studio_tab}:{cell}     → write title to Grail sheet cell
      Description:{scene_id}        → write to mega_staging (future)
    """
    target = approval["target_sheet"]
    content = json.loads(approval["content_json"])
    parts = target.split(":")

    if parts[0] == "Scripts" and len(parts) >= 3:
        _write_script_approval(parts[1], int(parts[2]), content)
    elif parts[0] == "Grail" and len(parts) >= 3:
        _write_grail_approval(parts[1], parts[2], content)
    elif parts[0] == "Description":
        _write_description_approval(parts[1] if len(parts) > 1 else "", content)
    else:
        raise ValueError(f"Unknown target format: {target}")


def _write_script_approval(month_tab, row_idx, fields):
    """Write approved script fields to the Scripts Google Sheet."""
    from sheets_integration import get_spreadsheet, write_script
    sp = get_spreadsheet()
    ws = sp.worksheet(month_tab)
    write_script(
        ws, row_idx,
        theme=fields.get("theme", ""),
        plot=fields.get("plot", ""),
        wardrobe_female=fields.get("wardrobe_female", ""),
        wardrobe_male=fields.get("wardrobe_male", ""),
        set_design=fields.get("set_design", ""),
        props=fields.get("props", ""),
    )


def _write_grail_approval(studio_tab, cell, content):
    """Write approved title text to the Grail sheet."""
    gc = _get_client()
    GRAIL_SHEET_ID = "1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk"
    sh = gc.open_by_key(GRAIL_SHEET_ID)
    ws = sh.worksheet(studio_tab)
    ws.update_acell(cell, content.get("title", ""))


def _write_description_approval(scene_id, content):
    """Write approved description to mega_staging. Placeholder for now."""
    # Future: write .docx/.txt to mega_staging/{studio}/{scene_id}/Description/
    # and update mega_scan.json with has_description: true
    pass
