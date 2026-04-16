"""
notification_tools.py
Per-user notification system for Eclatech Hub.
Backend: "Notifications" tab in the Eclatech Tickets Google Sheet.
Email: HTML emails via Gmail SMTP, fired as daemon threads (non-blocking).
"""

import html as _html
import os
import smtplib
import threading
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.oauth2.service_account import Credentials
import gspread
import auth_config

# ── Configuration ─────────────────────────────────────────────────────────────
NOTIFY_EMAIL = os.environ.get("TICKET_NOTIFY_EMAIL", "")
NOTIFY_PASSWORD = os.environ.get("TICKET_NOTIFY_PASSWORD", "")
APP_URL = "https://desktop-9d407v9.tail3f755a.ts.net"

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
    _failed = 0
    for r in recipients:
        try:
            create_notification(r, notif_type, title, message, link)
        except Exception as _e:
            _failed += 1
            print(f"[notify] WARNING: failed to notify '{r}': {_e}")
    if _failed:
        print(f"[notify] WARNING: {_failed}/{len(recipients)} notifications failed for '{title}'")


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
    for r in recipients:
        send_email_notification(
            r,
            TYPE_TICKET_CREATED,
            f"New ticket: {ticket_id}",
            f"{submitted_by} submitted \"{title}\"",
            link="Tickets",
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
    if new_status in ("Closed", "Rejected", "Approved"):
        for r in recipients:
            send_email_notification(
                r,
                TYPE_TICKET_STATUS,
                f"{ticket_id} → {new_status}",
                f"{changed_by} changed \"{title}\" to {new_status}",
                link="Tickets",
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
    send_email_notification(
        assigned_to,
        TYPE_TICKET_ASSIGNED,
        f"Assigned: {ticket_id}",
        f"{assigned_by} assigned \"{title}\" to you",
        link="Tickets",
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
    for r in recipients:
        send_email_notification(
            r,
            TYPE_APPROVAL_SUBMITTED,
            f"Approval: {scene_id} {content_type}",
            f"{submitted_by} submitted {content_type} for {scene_id}",
            link="Approvals",
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
    send_email_notification(
        submitted_by,
        TYPE_APPROVAL_DECIDED,
        f"{scene_id} {content_type}: {decision}",
        f"{decided_by} {decision.lower()} your {content_type} for {scene_id}",
        link="Approvals",
    )


# ── Email notifications ───────────────────────────────────────────────────────

_TYPE_ICONS = {
    TYPE_TICKET_CREATED:    "🎟",
    TYPE_TICKET_STATUS:     "🔄",
    TYPE_TICKET_ASSIGNED:   "👤",
    TYPE_APPROVAL_SUBMITTED: "📋",
    TYPE_APPROVAL_DECIDED:  "✅",
    TYPE_QC_FEEDBACK:       "🔍",
}

_TYPE_LABELS = {
    TYPE_TICKET_CREATED:    "New Ticket",
    TYPE_TICKET_STATUS:     "Ticket Update",
    TYPE_TICKET_ASSIGNED:   "Ticket Assigned",
    TYPE_APPROVAL_SUBMITTED: "Approval Request",
    TYPE_APPROVAL_DECIDED:  "Approval Decision",
    TYPE_QC_FEEDBACK:       "QC Feedback",
}


def _emails_for_name(name):
    """Return all email addresses registered to a display name.
    Handles multiple emails per name (e.g. Drew has 2)."""
    try:
        users = auth_config.load_users_config()
        return [email for email, info in users.items() if info["name"] == name]
    except Exception as e:
        print(f"[email] WARNING: could not load user config for {name}: {e}")
        return []


def _build_html(recipient_name, notif_type, title, message, link):
    """Build the HTML email body. All dynamic values are HTML-escaped."""
    icon = _TYPE_ICONS.get(notif_type, "🔔")
    e_title = _html.escape(title)
    e_message = _html.escape(message)
    e_recipient = _html.escape(recipient_name)

    if link:
        cta_url = f"{APP_URL}"
        cta_label = f"View in Eclatech Hub &rarr; {_html.escape(link)}"
    else:
        cta_url = APP_URL
        cta_label = "Open Eclatech Hub"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light">
  <meta name="supported-color-schemes" content="light">
  <title>{e_title}</title>
</head>
<body style="margin:0;padding:0;background-color:#0f1117;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#0f1117">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table width="600" cellpadding="0" cellspacing="0" border="0"
               style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td bgcolor="#1a1d27"
                style="background-color:#1a1d27;padding:20px 28px;
                       border-radius:8px 8px 0 0;border-bottom:1px solid #2a2d3a;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="font-size:13px;font-weight:700;color:#7c6af7;
                             letter-spacing:0.08em;font-family:Arial,sans-serif;">
                    &#9889; ECLATECH HUB
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td bgcolor="#1a1d27"
                style="background-color:#1a1d27;padding:28px 28px 24px;">
              <!-- Icon + Title -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="padding-bottom:6px;">
                    <span style="font-size:22px;line-height:1;">{icon}</span>
                  </td>
                </tr>
                <tr>
                  <td style="font-size:17px;font-weight:700;color:#e8eaf0;
                             font-family:Arial,sans-serif;padding-bottom:10px;
                             line-height:1.3;">
                    {e_title}
                  </td>
                </tr>
                <tr>
                  <td style="font-size:14px;color:#8b929e;font-family:Arial,sans-serif;
                             padding-bottom:28px;line-height:1.5;">
                    {e_message}
                  </td>
                </tr>
                <!-- CTA Button -->
                <tr>
                  <td style="padding-bottom:14px;">
                    <table cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td bgcolor="#7c6af7"
                            style="background-color:#7c6af7;border-radius:6px;">
                          <a href="{cta_url}"
                             style="display:inline-block;padding:11px 22px;
                                    font-size:13px;font-weight:600;color:#ffffff;
                                    text-decoration:none;font-family:Arial,sans-serif;">
                            {cta_label}
                          </a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <!-- Plain-text URL fallback -->
                <tr>
                  <td style="font-size:11px;color:#555b66;font-family:Arial,sans-serif;">
                    {cta_url}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td bgcolor="#13151f"
                style="background-color:#13151f;padding:14px 28px;
                       border-radius:0 0 8px 8px;border-top:1px solid #2a2d3a;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="font-size:11px;color:#555b66;font-family:Arial,sans-serif;
                             line-height:1.5;">
                    Eclatech Hub &nbsp;&middot;&nbsp; Sent to: {e_recipient}<br>
                    You're receiving this because an event requires your attention.
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _send_one(addr, recipient_name, notif_type, title, message, link):
    """Send a single HTML email. Raises on failure."""
    icon = _TYPE_ICONS.get(notif_type, "🔔")
    # Subject: strip newlines, cap at 60 chars
    subject_raw = f"{icon} {title}"
    subject = subject_raw.replace("\n", " ").replace("\r", " ")[:60]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = NOTIFY_EMAIL
    msg["To"] = addr

    html_body = _build_html(recipient_name, notif_type, title, message, link)
    # Plain-text fallback
    plain = f"{title}\n\n{message}\n\n{APP_URL}"

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(NOTIFY_EMAIL, NOTIFY_PASSWORD)
        server.send_message(msg)


def send_email_notification(recipient_name, notif_type, title, message, link=""):
    """Send an HTML email notification to a user (non-blocking, daemon thread).
    Looks up all email addresses for the recipient name dynamically from the Users sheet.
    Fails silently but logs to stdout (visible in NSSM logs)."""
    if not NOTIFY_EMAIL or not NOTIFY_PASSWORD:
        return
    emails = _emails_for_name(recipient_name)
    if not emails:
        print(f"[email] WARNING: no email address found for user '{recipient_name}'")
        return

    def _send():
        for addr in emails:
            try:
                _send_one(addr, recipient_name, notif_type, title, message, link)
                print(f"[email] Sent '{title}' to {addr}")
            except Exception as e:
                print(f"[email] ERROR sending to {addr}: {e}")

    threading.Thread(target=_send, daemon=True).start()
