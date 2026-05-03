"""
ticket_tools.py
Handles ticket CRUD operations for the Eclatech Hub ticketing system.
Backend: Google Sheets ("Eclatech Tickets")
"""

import os
import time
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread

# ── Configuration ─────────────────────────────────────────────────────────────
TICKETS_SHEET_ID = os.environ.get("TICKETS_SHEET_ID", "1t92DvQxZzgHKjp4-uxaPLdyaqlmcGNLxSd6qx8hANyA")
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Employee list — update these with real names
EMPLOYEES = [
    "Drew",
    "David",
    "Duc",
    "Isaac",
    "Flo",
    "Tam",
]

PROJECTS = ["VR Player", "Eclatech Hub", "Script Writer", "Compilations", "Content Pipeline", "Website", "Other"]
TICKET_TYPES = ["Bug", "Feature Request", "Change Request", "Missing Content"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["New", "Approved", "In Progress", "In Review", "Closed", "Rejected"]

# Column indices (0-based, matching sheet columns A-M)
COL_ID = 0
COL_DATE = 1
COL_SUBMITTED_BY = 2
COL_PROJECT = 3
COL_TYPE = 4
COL_PRIORITY = 5
COL_TITLE = 6
COL_DESCRIPTION = 7
COL_STATUS = 8
COL_APPROVED_BY = 9
COL_ADMIN_NOTES = 10
COL_ASSIGNED_TO = 11
COL_DATE_RESOLVED = 12

HEADERS = [
    "Ticket ID", "Date Submitted", "Submitted By", "Project", "Type",
    "Priority", "Title", "Description", "Status", "Approved By",
    "Admin Notes", "Assigned To", "Date Resolved",
]

# ── Sheet client + worksheet (both cached 30 min) ────────────────────────────
_cached_client = None
_cached_at = 0
_cached_ws = None
_cached_ws_at = 0

# ── Tickets data cache (5 min TTL) ───────────────────────────────────────────
_tickets_cache = None
_tickets_cached_at = 0.0

def _bust_tickets_cache():
    global _tickets_cache
    _tickets_cache = None


def _with_retry(fn, max_retries=3):
    """Call fn(), retrying up to max_retries times on 429 rate-limit errors."""
    delay = 2
    for attempt in range(max_retries):
        try:
            return fn()
        except gspread.exceptions.APIError as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise


def _get_client():
    global _cached_client, _cached_at, _cached_ws, _cached_ws_at
    now = time.time()
    if _cached_client and (now - _cached_at) < 1800:
        return _cached_client
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    _cached_client = gspread.authorize(creds)
    _cached_at = now
    # Invalidate worksheet cache when client refreshes
    _cached_ws = None
    _cached_ws_at = 0
    return _cached_client


def _get_worksheet():
    """Get the Tickets worksheet (cached 30 min). Header init runs only on cache miss."""
    global _cached_ws, _cached_ws_at
    now = time.time()
    if _cached_ws and (now - _cached_ws_at) < 1800:
        return _cached_ws
    gc = _get_client()
    sh = _with_retry(lambda: gc.open_by_key(TICKETS_SHEET_ID))
    ws = sh.sheet1
    # One-time header initialization (only on cache miss, not every read)
    first_row = _with_retry(lambda: ws.row_values(1))
    if not first_row or first_row[0] != "Ticket ID":
        ws.update("A1:M1", [HEADERS])
        ws.format("A1:M1", {"textFormat": {"bold": True}})
        ws.freeze(rows=1)
    _cached_ws = ws
    _cached_ws_at = now
    return _cached_ws


# ── CRUD operations ──────────────────────────────────────────────────────────

def load_tickets():
    """Load all tickets from the sheet. Returns list of dicts."""
    global _tickets_cache, _tickets_cached_at
    now = time.time()
    if _tickets_cache is not None and (now - _tickets_cached_at) < 300:
        return _tickets_cache
    ws = _get_worksheet()
    rows = _with_retry(lambda: ws.get_all_values())
    if len(rows) <= 1:
        return []
    tickets = []
    for i, row in enumerate(rows[1:], start=2):
        row = row + [""] * (13 - len(row))
        tickets.append({
            "row_index": i,
            "id": row[COL_ID],
            "date": row[COL_DATE],
            "submitted_by": row[COL_SUBMITTED_BY],
            "project": row[COL_PROJECT],
            "type": row[COL_TYPE],
            "priority": row[COL_PRIORITY],
            "title": row[COL_TITLE],
            "description": row[COL_DESCRIPTION],
            "status": row[COL_STATUS],
            "approved_by": row[COL_APPROVED_BY],
            "admin_notes": row[COL_ADMIN_NOTES],
            "assigned_to": row[COL_ASSIGNED_TO],
            "date_resolved": row[COL_DATE_RESOLVED],
        })
    _tickets_cache = tickets
    _tickets_cached_at = now
    return tickets


def get_next_ticket_id(tickets=None):
    """Generate the next ticket ID (e.g., TKT-0001)."""
    if tickets is None:
        tickets = load_tickets()
    if not tickets:
        return "TKT-0001"
    max_num = 0
    for t in tickets:
        tid = t["id"]
        if tid.startswith("TKT-"):
            try:
                num = int(tid.split("-")[1])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                pass
    return f"TKT-{max_num + 1:04d}"


def create_ticket(submitted_by, project, ticket_type, priority, title, description,
                   assigned_to=""):
    """Create a new ticket. Returns the ticket ID."""
    ws = _get_worksheet()
    tickets = load_tickets()
    ticket_id = get_next_ticket_id(tickets)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    new_row = [
        ticket_id,
        now,
        submitted_by,
        project,
        ticket_type,
        priority,
        title,
        description,
        "New",
        "",   # approved_by
        "",   # admin_notes
        assigned_to,
        "",   # date_resolved
    ]
    ws.append_row(new_row, value_input_option="USER_ENTERED")
    _bust_tickets_cache()
    return ticket_id


def update_ticket(row_index, status=None, approved_by=None, admin_notes=None,
                   assigned_to=None):
    """Update a ticket's status, approver, admin notes, and/or assignee."""
    ws = _get_worksheet()
    if status is not None:
        ws.update_cell(row_index, COL_STATUS + 1, status)
        if status in ("Closed", "Rejected"):
            ws.update_cell(row_index, COL_DATE_RESOLVED + 1,
                           datetime.now().strftime("%Y-%m-%d %H:%M"))
    if approved_by is not None:
        ws.update_cell(row_index, COL_APPROVED_BY + 1, approved_by)
    if admin_notes is not None:
        ws.update_cell(row_index, COL_ADMIN_NOTES + 1, admin_notes)
    if assigned_to is not None:
        ws.update_cell(row_index, COL_ASSIGNED_TO + 1, assigned_to)
    _bust_tickets_cache()


def resolve_ticket(ticket_id, status="In Review", notes="", approved_by="Claude"):
    """Update a ticket by its ID (e.g. 'TKT-0005'). Used by Claude Code after deploys.
    Default status is 'In Review' — employee must verify and close."""
    tickets = load_tickets()
    match = next((t for t in tickets if t["id"] == ticket_id), None)
    if not match:
        raise ValueError(f"Ticket {ticket_id} not found")
    # Append to existing notes rather than overwriting
    existing = match.get("admin_notes", "")
    combined = f"{existing}\n{notes}".strip() if existing else notes
    update_ticket(match["row_index"], status=status, approved_by=approved_by,
                  admin_notes=combined if notes else None)
    return match


def resolve_tickets(ticket_ids, status="In Review", notes="", approved_by="Claude"):
    """Batch-resolve multiple tickets. Returns list of updated IDs."""
    updated = []
    for tid in ticket_ids:
        try:
            resolve_ticket(tid, status=status, notes=notes, approved_by=approved_by)
            updated.append(tid)
        except Exception as e:
            print(f"  ⚠ {tid}: {e}")
    return updated


def get_open_tickets():
    """Return tickets that are still active (not Closed/Rejected). Used for linking in tabs."""
    return [t for t in load_tickets() if t["status"] not in ("Closed", "Rejected")]


def progress_ticket(ticket_id, new_status="In Progress", notes="", by=""):
    """Move a ticket forward in the workflow. Used by tab linking.
    Returns True if the ticket was updated, False if ticket_id not found."""
    tickets = load_tickets()
    match = next((t for t in tickets if t["id"] == ticket_id), None)
    if not match:
        print(f"[tickets] WARNING: progress_ticket called with unknown id '{ticket_id}'")
        return False
    existing = match.get("admin_notes", "")
    combined = f"{existing}\n{notes}".strip() if existing and notes else (notes or existing)
    update_ticket(match["row_index"], status=new_status,
                  admin_notes=combined if combined != existing else None)
    return True


# ── Notes helper ─────────────────────────────────────────────────────────────

def append_note(existing_notes, author, text):
    """Append a timestamped note. Returns combined string."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"[{ts} {author}] {text}"
    return f"{existing_notes}\n{entry}".strip() if existing_notes else entry


# ── Email notification ───────────────────────────────────────────────────────