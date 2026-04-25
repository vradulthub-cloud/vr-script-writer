"""
Notifications API router.

Provides endpoints for the in-app notification system:
  GET    /api/notifications/             — list current user's notifications
  GET    /api/notifications/unread-count — unread count for badge
  POST   /api/notifications/mark-read    — mark all as read for current user

Also provides a helper function for other routers to create notifications.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import CurrentUser, validate_sse_token
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


@router.get("/diagnostic")
async def diagnostic(user: CurrentUser):
    """Admin-only health check — counts and recent activity for the
    notifications subsystem. Use this to verify the system is alive without
    SSH'ing into the server."""
    if user.get("role") != "admin":
        from fastapi import HTTPException, status as st
        raise HTTPException(status_code=st.HTTP_403_FORBIDDEN, detail="Admin only")

    with get_db() as conn:
        admins = [
            dict(r)["name"]
            for r in conn.execute(
                "SELECT name FROM users WHERE LOWER(role) = 'admin' ORDER BY name"
            ).fetchall()
        ]
        totals = dict(conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN read=0 THEN 1 ELSE 0 END) AS unread "
            "FROM notifications"
        ).fetchone())
        latest_row = conn.execute(
            "SELECT timestamp FROM notifications ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        per_recipient = [
            dict(r) for r in conn.execute(
                "SELECT recipient, COUNT(*) AS total, "
                "SUM(CASE WHEN read=0 THEN 1 ELSE 0 END) AS unread "
                "FROM notifications GROUP BY recipient ORDER BY total DESC"
            ).fetchall()
        ]
        per_type = [
            dict(r) for r in conn.execute(
                "SELECT type, COUNT(*) AS total FROM notifications "
                "GROUP BY type ORDER BY total DESC"
            ).fetchall()
        ]
        my_unread = conn.execute(
            "SELECT COUNT(*) AS c FROM notifications "
            "WHERE LOWER(recipient) = LOWER(?) AND read = 0",
            (user["name"],),
        ).fetchone()["c"]

    return {
        "current_user": user["name"],
        "current_user_unread": my_unread,
        "admins": admins,
        "totals": {"total": totals["total"], "unread": totals["unread"] or 0},
        "latest_timestamp": latest_row["timestamp"] if latest_row else None,
        "per_recipient": per_recipient,
        "per_type": per_type,
    }


@router.post("/test")
async def send_test_notification(user: CurrentUser):
    """Admin-only — fire a test notification at the calling user. Lets you
    verify the bell, polling, and timestamps are working without provoking
    a real event."""
    if user.get("role") != "admin":
        from fastapi import HTTPException, status as st
        raise HTTPException(status_code=st.HTTP_403_FORBIDDEN, detail="Admin only")

    notif_id = create_notification(
        user["name"],
        "ticket_status",
        "Test notification",
        "If you can see this, the notification pipeline is working end-to-end.",
        "/tickets",
    )
    return {"notif_id": notif_id, "recipient": user["name"]}


@router.get("/stream")
async def stream_notifications(
    request: Request,
    token: Optional[str] = Query(default=None),
):
    """
    Server-Sent Events stream for notifications.

    Browsers connect via:
        new EventSource('/api/notifications/stream?token=<jwt>')

    The EventSource API cannot set custom headers, so the JWT is passed as a
    query parameter.  The same Google ID token validation that CurrentUser
    performs is applied here via validate_sse_token.

    Event format:
        data: <JSON array of notification objects>\\n\\n

    A heartbeat comment is sent every 30 s to keep the connection alive.
    """
    user = await validate_sse_token(request, token)

    async def _generator() -> AsyncGenerator[str, None]:
        last_hash = ""
        recipient = user["name"]
        try:
            while True:
                try:
                    with get_db() as conn:
                        rows = conn.execute(
                            """
                            SELECT notif_id, timestamp, recipient, type, title,
                                   message, read, link
                            FROM notifications
                            WHERE LOWER(recipient) = LOWER(?)
                            ORDER BY timestamp DESC
                            LIMIT 50
                            """,
                            (recipient,),
                        ).fetchall()
                    payload = json.dumps([dict(r) for r in rows], default=str)
                    current_hash = hashlib.sha256(payload.encode()).hexdigest()
                    if current_hash != last_hash:
                        last_hash = current_hash
                        yield f"data: {payload}\n\n"
                except Exception as exc:
                    _log.warning("notifications SSE: error fetching notifications: %s", exc)

                # Heartbeat comment — keeps connection alive, ignored by EventSource
                yield ": heartbeat\n\n"
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            # Client disconnected cleanly
            _log.debug("notifications SSE: client disconnected (%s)", recipient)

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


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
    # ISO-8601 with explicit Z so JS clients parse as UTC unambiguously across
    # browsers. Legacy rows use "YYYY-MM-DD HH:MM" (UTC, unmarked); the frontend
    # parser handles both.
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

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
