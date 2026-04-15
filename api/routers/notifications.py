"""
Notifications API router.

Provides endpoints for the in-app notification system:
  GET    /api/notifications/             — list current user's notifications
  GET    /api/notifications/unread-count — unread count for badge
  POST   /api/notifications/mark-read    — mark all as read for current user

Also provides a helper function for other routers to create notifications.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from api.auth import CurrentUser
from api.database import get_db
from api.sheets_client import open_tickets, get_or_create_worksheet, with_retry

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# Notification types (mirrored from original notification_tools.py)
TYPE_TICKET_CREATED = "ticket_created"
TYPE_TICKET_STATUS = "ticket_status"
TYPE_TICKET_ASSIGNED = "ticket_assigned"
TYPE_APPROVAL_SUBMITTED = "approval_submitted"
TYPE_APPROVAL_DECIDED = "approval_decided"

NOTIF_HEADERS = [
    "ID", "Timestamp", "Recipient", "Type", "Title", "Message", "Read", "Link",
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
async def list_notifications(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
):
    """List notifications for the current user, newest first."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT notif_id, timestamp, recipient, type, title, message, read, link
            FROM notifications
            WHERE LOWER(recipient) = LOWER(?)
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (user["name"], limit),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/unread-count")
async def unread_count(user: CurrentUser):
    """Return the number of unread notifications for the current user."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as count FROM notifications WHERE LOWER(recipient) = LOWER(?) AND read = 0",
            (user["name"],),
        ).fetchone()
    return {"count": dict(row)["count"] if row else 0}


@router.post("/mark-read")
async def mark_all_read(user: CurrentUser):
    """Mark all notifications as read for the current user."""
    with get_db() as conn:
        result = conn.execute(
            "UPDATE notifications SET read = 1 WHERE LOWER(recipient) = LOWER(?) AND read = 0",
            (user["name"],),
        )
        updated = result.rowcount

    # Fire-and-forget write to Sheets
    threading.Thread(
        target=_mark_read_in_sheet,
        args=(user["name"],),
        daemon=True,
    ).start()

    return {"updated": updated}


# ---------------------------------------------------------------------------
# Notification creation helper (used by other routers)
# ---------------------------------------------------------------------------

def create_notification(
    recipient: str,
    notif_type: str,
    title: str,
    message: str,
    link: str = "",
) -> str:
    """
    Create a notification in SQLite and fire-and-forget to Sheets.

    Returns the notification ID.
    """
    notif_id = f"N-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO notifications (notif_id, timestamp, recipient, type, title, message, read, link)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (notif_id, now, recipient, notif_type, title, message, link),
        )

    # Fire-and-forget Sheets write
    threading.Thread(
        target=_write_notification_to_sheet,
        args=(notif_id, now, recipient, notif_type, title, message, link),
        daemon=True,
    ).start()

    _log.info("Notification %s created for %s: %s", notif_id, recipient, title)
    return notif_id


def notify_multiple(
    recipients: list[str],
    notif_type: str,
    title: str,
    message: str,
    link: str = "",
) -> list[str]:
    """Create the same notification for multiple recipients."""
    return [
        create_notification(r, notif_type, title, message, link)
        for r in recipients
    ]


def get_admin_names() -> list[str]:
    """Fetch admin user names from the database."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT name FROM users WHERE role = 'admin'"
        ).fetchall()
    return [dict(r)["name"] for r in rows]


# ---------------------------------------------------------------------------
# Sheets write-through (background)
# ---------------------------------------------------------------------------

def _write_notification_to_sheet(
    notif_id: str, timestamp: str, recipient: str,
    notif_type: str, title: str, message: str, link: str,
) -> None:
    """Append a notification row to the Tickets sheet 'Notifications' tab."""
    try:
        sh = open_tickets()
        ws = get_or_create_worksheet(sh, "Notifications", headers=NOTIF_HEADERS)
        with_retry(lambda: ws.append_row(
            [notif_id, timestamp, recipient, notif_type, title, message, "FALSE", link],
            value_input_option="USER_ENTERED",
        ))
    except Exception:
        _log.exception("Failed to write notification %s to Sheets", notif_id)


def _mark_read_in_sheet(recipient: str) -> None:
    """Mark all notifications as read in the Tickets sheet 'Notifications' tab."""
    try:
        sh = open_tickets()
        ws = get_or_create_worksheet(sh, "Notifications", headers=NOTIF_HEADERS)
        rows = with_retry(lambda: ws.get_all_values())

        # Column G (index 6) is "Read", column C (index 2) is "Recipient"
        cells_to_update = []
        for i, row in enumerate(rows):
            if i == 0:
                continue
            if len(row) >= 7 and row[2].lower() == recipient.lower() and row[6] != "TRUE":
                cells_to_update.append(f"G{i + 1}")

        if cells_to_update:
            # Batch update in chunks of 50
            for chunk_start in range(0, len(cells_to_update), 50):
                chunk = cells_to_update[chunk_start:chunk_start + 50]
                updates = [{
                    "range": cell,
                    "values": [["TRUE"]],
                } for cell in chunk]
                with_retry(lambda u=updates: ws.batch_update(u, value_input_option="USER_ENTERED"))

        _log.info("Marked %d notifications as read in Sheets for %s", len(cells_to_update), recipient)
    except Exception:
        _log.exception("Failed to mark notifications read in Sheets for %s", recipient)
