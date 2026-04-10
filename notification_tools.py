"""
notification_tools.py
Per-user notification system for Eclatech Hub.
Backend: "Notifications" tab in the Eclatech Tickets Google Sheet.
"""

import os
import time
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread

# ── Configuration ─────────────────────────────────────────────────────────────
SHEET_ID = "1t92DvQxZzgHKjp4-uxaPLdyaqlmcGNLxSd6qx8hANyA"
TAB_NAME = "Notifications"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "ID", "Timestamp", "Recipient", "Type", "Title",
    "Message", "Read", "Link",
]

# Column indices (0-based)
COL_ID = 0
COL_TIMESTAMP = 1
COL_RECIPIENT = 2
COL_TYPE = 3
COL_TITLE = 4
COL_MESSAGE = 5
COL_READ = 6
COL_LINK = 7

# Notification types
TYPE_TICKET_CREATED = "ticket_created"
TYPE_TICKET_STATUS = "ticket_status"
TYPE_TICKET_ASSIGNED = "ticket_assigned"
TYPE_APPROVAL_SUBMITTED = "approval_submitted"
TYPE_APPROVAL_DECIDED = "approval_decided"
TYPE_QC_FEEDBACK = "qc_feedback"

# ── Sheet client (cached) ────────────────────────────────────────────────────
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
    """Get or create the Notifications tab."""
    gc = _get_client()
    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(TAB_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=TAB_NAME, rows=500, cols=len(HEADERS))
        ws.append_row(HEADERS, value_input_option="USER_ENTERED")
    return ws


# ── Read operations ──────────────────────────────────────────────────────────

def _next_id(notifications):
    """Generate next NTF-XXXX ID."""
    if not notifications:
        return "NTF-0001"
    max_num = 0
    for n in notifications:
        nid = n.get("id", "")
        if nid.startswith("NTF-"):
            try:
                num = int(nid.split("-")[1])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                pass
    return f"NTF-{max_num + 1:04d}"


def load_notifications(recipient=None, limit=50):
    """Load notifications, optionally filtered by recipient name.
    Returns list of dicts, newest first."""
    ws = _get_worksheet()
    rows = ws.get_all_values()
    notifications = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) < 7:
            continue
        n = {
            "id": row[COL_ID].strip(),
            "timestamp": row[COL_TIMESTAMP].strip(),
            "recipient": row[COL_RECIPIENT].strip(),
            "type": row[COL_TYPE].strip(),
            "title": row[COL_TITLE].strip(),
            "message": row[COL_MESSAGE].strip(),
            "read": row[COL_READ].strip().upper() == "TRUE",
            "link": row[COL_LINK].strip() if len(row) > COL_LINK else "",
            "row_index": i,
        }
        if recipient and n["recipient"] != recipient:
            continue
        notifications.append(n)
    # Newest first
    notifications.reverse()
    return notifications[:limit]


def get_unread_count(recipient):
    """Fast unread count for a user."""
    ws = _get_worksheet()
    rows = ws.get_all_values()
    count = 0
    for row in rows[1:]:
        if len(row) < 7:
            continue
        if row[COL_RECIPIENT].strip() == recipient and row[COL_READ].strip().upper() != "TRUE":
            count += 1
    return count


# ── Write operations ─────────────────────────────────────────────────────────

def create_notification(recipient, notif_type, title, message, link=""):
    """Create a notification for a specific user. Returns the notification ID."""
    ws = _get_worksheet()
    all_notifs = load_notifications()
    notif_id = _next_id(all_notifs)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    new_row = [
        notif_id,
        now,
        recipient,
        notif_type,
        title,
        message,
        "FALSE",
        link,
    ]
    ws.append_row(new_row, value_input_option="USER_ENTERED")
    return notif_id


def notify_multiple(recipients, notif_type, title, message, link=""):
    """Send the same notification to multiple users."""
    for r in recipients:
        try:
            create_notification(r, notif_type, title, message, link)
        except Exception:
            pass


def mark_read(row_index):
    """Mark a single notification as read."""
    ws = _get_worksheet()
    ws.update_cell(row_index, COL_READ + 1, "TRUE")


def mark_all_read(recipient):
    """Mark all notifications for a user as read."""
    ws = _get_worksheet()
    rows = ws.get_all_values()
    cells_to_update = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) < 7:
            continue
        if row[COL_RECIPIENT].strip() == recipient and row[COL_READ].strip().upper() != "TRUE":
            cells_to_update.append(gspread.Cell(i, COL_READ + 1, "TRUE"))
    if cells_to_update:
        ws.update_cells(cells_to_update)


def cleanup_old(keep=200):
    """Remove oldest notifications beyond the keep limit."""
    ws = _get_worksheet()
    rows = ws.get_all_values()
    data_rows = rows[1:]
    if len(data_rows) <= keep:
        return
    to_delete = len(data_rows) - keep
    # Delete oldest rows (top of sheet, after header)
    for _ in range(to_delete):
        ws.delete_rows(2)


# ── Convenience: notification generators ─────────────────────────────────────

ADMIN_NAMES = ["Drew", "David", "Isaac"]


def notify_ticket_created(ticket_id, title, submitted_by):
    """Notify admins when a new ticket is created."""
    recipients = [n for n in ADMIN_NAMES if n != submitted_by]
    notify_multiple(
        recipients,
        TYPE_TICKET_CREATED,
        f"New ticket: {ticket_id}",
        f"{submitted_by} submitted \"{title}\"",
        f"Tickets",
    )


def notify_ticket_status(ticket_id, title, new_status, changed_by,
                         submitted_by="", assigned_to=""):
    """Notify relevant people when a ticket status changes."""
    recipients = set()
    if submitted_by and submitted_by != changed_by:
        recipients.add(submitted_by)
    if assigned_to and assigned_to != changed_by:
        recipients.add(assigned_to)
    if not recipients:
        return
    notify_multiple(
        list(recipients),
        TYPE_TICKET_STATUS,
        f"{ticket_id} → {new_status}",
        f"{changed_by} changed \"{title}\" to {new_status}",
        f"Tickets",
    )


def notify_ticket_assigned(ticket_id, title, assigned_to, assigned_by):
    """Notify a user when a ticket is assigned to them."""
    if assigned_to == assigned_by:
        return
    create_notification(
        assigned_to,
        TYPE_TICKET_ASSIGNED,
        f"Assigned: {ticket_id}",
        f"{assigned_by} assigned \"{title}\" to you",
        f"Tickets",
    )


def notify_approval_submitted(approval_id, scene_id, content_type, submitted_by):
    """Notify admins when content is submitted for approval."""
    recipients = [n for n in ADMIN_NAMES if n != submitted_by]
    notify_multiple(
        recipients,
        TYPE_APPROVAL_SUBMITTED,
        f"Approval: {scene_id} {content_type}",
        f"{submitted_by} submitted {content_type} for {scene_id}",
        f"Approvals",
    )


def notify_approval_decided(approval_id, scene_id, content_type, decision,
                            decided_by, submitted_by):
    """Notify submitter when their approval is decided."""
    if submitted_by == decided_by:
        return
    create_notification(
        submitted_by,
        TYPE_APPROVAL_DECIDED,
        f"{scene_id} {content_type}: {decision}",
        f"{decided_by} {decision.lower()} your {content_type} for {scene_id}",
        f"Approvals",
    )
