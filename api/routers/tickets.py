"""
Tickets API router.

Provides CRUD endpoints for the ticketing system:
  GET    /api/tickets/          — list tickets (with filters)
  GET    /api/tickets/{id}      — get single ticket
  POST   /api/tickets/          — create ticket
  PATCH  /api/tickets/{id}      — update ticket (status, assignee, notes)
  GET    /api/tickets/stats     — ticket counts by status

All reads go to SQLite (sub-ms). Writes go to both SQLite + Google Sheets.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.auth import CurrentUser
from api.database import get_db, update_sync_meta
from api.sheets_client import open_tickets, get_or_create_worksheet, with_retry

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

PROJECTS = [
    "VR Player", "Eclatech Hub", "Script Writer",
    "Compilations", "Content Pipeline", "Website", "Other",
]
TICKET_TYPES = [
    "Bug", "Feature Request", "Improvement",
    "Missing Content", "Task", "Question", "Other",
]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["New", "Approved", "In Progress", "In Review", "Closed", "Rejected"]


class TicketCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    project: str = "Other"
    type: str = "Bug"
    priority: str = "Medium"
    linked_items: str = ""


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None
    note: Optional[str] = None


class BulkTicketUpdate(BaseModel):
    ticket_ids: list[str]
    status: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None


class BulkTicketResult(BaseModel):
    updated: list[str]
    skipped: list[dict]  # [{ticket_id, reason}]


class TicketResponse(BaseModel):
    ticket_id: str
    title: str
    description: str
    project: str
    type: str
    priority: str
    status: str
    submitted_by: str
    submitted_at: str
    assignee: str
    notes: str
    resolved_at: str
    linked_items: str


# ---------------------------------------------------------------------------
# Ticket ID generation
# ---------------------------------------------------------------------------
def _next_ticket_id(conn) -> str:
    """Generate the next TKT-XXXX ID."""
    row = conn.execute(
        "SELECT ticket_id FROM tickets ORDER BY ticket_id DESC LIMIT 1"
    ).fetchone()
    if row:
        last = dict(row)["ticket_id"]
        try:
            num = int(last.replace("TKT-", "")) + 1
        except ValueError:
            num = 1
    else:
        num = 1
    return f"TKT-{num:04d}"


# ---------------------------------------------------------------------------
# Sheets write-through helpers
# ---------------------------------------------------------------------------
def _write_ticket_to_sheet(ticket: dict) -> None:
    """Append a ticket row to Sheet1 — the canonical tab that sync_tickets reads.

    Sheet1 schema (1-indexed):
      A=Ticket ID, B=Date Submitted, C=Submitted By, D=Project, E=Type,
      F=Priority, G=Title, H=Description, I=Status, J=Approved By,
      K=Admin Notes, L=Assigned To, M=Date Resolved
    """
    try:
        sh = open_tickets()
        ws = sh.sheet1
        row = [
            ticket["ticket_id"],
            ticket["submitted_at"],
            ticket["submitted_by"],
            ticket["project"],
            ticket["type"],
            ticket["priority"],
            ticket["title"],
            ticket["description"],
            ticket["status"],
            "",                       # Approved By
            ticket["notes"],
            ticket["assignee"],
            ticket["resolved_at"],
        ]
        with_retry(lambda: ws.append_row(row, value_input_option="USER_ENTERED"))
    except Exception as exc:
        _log.error("Failed to write ticket to Sheets: %s", exc)


def _update_ticket_in_sheet(ticket_id: str, updates: dict) -> None:
    """Update a ticket row in Sheet1 by finding its row. Column mapping matches
    the Sheet1 schema documented in `_write_ticket_to_sheet`."""
    try:
        sh = open_tickets()
        ws = sh.sheet1
        cell = with_retry(lambda: ws.find(ticket_id, in_column=1))
        if not cell:
            _log.warning("Ticket %s not found in Sheet1", ticket_id)
            return

        row_num = cell.row
        col_map = {
            "priority": 6,
            "status": 9,
            "notes": 11,
            "assignee": 12,
            "resolved_at": 13,
        }

        for field, value in updates.items():
            col = col_map.get(field)
            if col:
                with_retry(lambda c=col, v=value: ws.update_cell(row_num, c, v))
    except Exception as exc:
        _log.error("Failed to update ticket in Sheets: %s", exc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/stats")
async def ticket_stats(user: CurrentUser):
    """Get ticket counts grouped by status."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM tickets GROUP BY status"
        ).fetchall()
    return {dict(r)["status"]: dict(r)["count"] for r in rows}


@router.get("/", response_model=list[TicketResponse])
async def list_tickets(
    user: CurrentUser,
    status_filter: Optional[str] = Query(None, alias="status"),
    project: Optional[str] = None,
    priority: Optional[str] = None,
    assignee: Optional[str] = None,
    type_filter: Optional[str] = Query(None, alias="type"),
    limit: Optional[int] = Query(None, ge=1, le=500),
):
    """List tickets with optional filters.

    `type=Audit` is the underlying primitive for the admin audit log — every
    permission change is written as a synthetic Audit ticket (see
    users-panel.tsx). Capping with `limit` lets the audit panel ask for just
    the most recent N rows without paying for the whole table.
    """
    query = "SELECT * FROM tickets WHERE 1=1"
    params: list = []

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    if project:
        query += " AND project = ?"
        params.append(project)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if assignee:
        query += " AND assignee = ?"
        params.append(assignee)
    if type_filter:
        query += " AND type = ?"
        params.append(type_filter)

    query += " ORDER BY submitted_at DESC"
    if limit:
        query += f" LIMIT {int(limit)}"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(r) for r in rows]


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str, user: CurrentUser):
    """Get a single ticket by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return dict(row)


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(body: TicketCreate, user: CurrentUser):
    """Create a new ticket."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    with get_db() as conn:
        ticket_id = _next_ticket_id(conn)
        ticket = {
            "ticket_id": ticket_id,
            "title": body.title,
            "description": body.description,
            "project": body.project,
            "type": body.type,
            "priority": body.priority,
            "status": "New",
            "submitted_by": user["name"],
            "submitted_at": now,
            "assignee": "",
            "notes": "",
            "resolved_at": "",
            "linked_items": body.linked_items,
        }

        conn.execute(
            """INSERT INTO tickets
               (ticket_id, title, description, project, type, priority,
                status, submitted_by, submitted_at, assignee, notes,
                resolved_at, linked_items)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            list(ticket.values()),
        )

    # Write-through to Google Sheets (fire-and-forget for now)
    import threading
    threading.Thread(target=_write_ticket_to_sheet, args=(ticket,), daemon=True).start()

    # Notify admins about new ticket
    try:
        from api.routers.notifications import notify_multiple, get_admin_names, TYPE_TICKET_CREATED
        admins = [n for n in get_admin_names() if n != user["name"]]
        if admins:
            notify_multiple(
                admins,
                TYPE_TICKET_CREATED,
                f"New ticket: {ticket_id}",
                f'{user["name"]} submitted "{body.title}"',
                "/tickets",
            )
    except Exception as exc:
        _log.warning("Failed to send ticket notification: %s", exc)

    return ticket


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(ticket_id: str, body: TicketUpdate, user: CurrentUser):
    """Update a ticket's status, assignee, priority, or add a note."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Ticket not found")

        ticket = dict(row)
        sheet_updates: dict = {}

        # Permission: only submitter, assignee, or admin can mutate a ticket.
        is_admin = (user.get("role") or "").lower() == "admin"
        is_submitter = (ticket.get("submitted_by") or "") == user["name"]
        is_assignee  = (ticket.get("assignee") or "") == user["name"]
        if not (is_admin or is_submitter or is_assignee):
            raise HTTPException(
                status_code=403,
                detail="Only the submitter, assignee, or an admin can update this ticket",
            )

        if body.status and body.status != ticket["status"]:
            ticket["status"] = body.status
            sheet_updates["status"] = body.status

            if body.status in ("Closed", "Rejected"):
                ticket["resolved_at"] = now
                sheet_updates["resolved_at"] = now

        if body.assignee is not None:
            ticket["assignee"] = body.assignee
            sheet_updates["assignee"] = body.assignee

        if body.priority and body.priority != ticket["priority"]:
            ticket["priority"] = body.priority
            sheet_updates["priority"] = body.priority

        if body.note:
            note_entry = f"[{now} {user['name']}] {body.note}"
            existing_notes = ticket["notes"]
            ticket["notes"] = (
                f"{existing_notes}\n{note_entry}" if existing_notes else note_entry
            )
            sheet_updates["notes"] = ticket["notes"]

        # Update SQLite
        conn.execute(
            """UPDATE tickets
               SET status=?, assignee=?, priority=?, notes=?, resolved_at=?
               WHERE ticket_id=?""",
            (
                ticket["status"],
                ticket["assignee"],
                ticket["priority"],
                ticket["notes"],
                ticket["resolved_at"],
                ticket_id,
            ),
        )

    # Write-through to Sheets
    if sheet_updates:
        import threading
        threading.Thread(
            target=_update_ticket_in_sheet,
            args=(ticket_id, sheet_updates),
            daemon=True,
        ).start()

    # Notify on status change or assignment
    try:
        from api.routers.notifications import create_notification, TYPE_TICKET_STATUS, TYPE_TICKET_ASSIGNED
        if "status" in sheet_updates:
            # Notify the ticket submitter if it's not the person making the change
            submitter = ticket.get("submitted_by", "")
            if submitter and submitter != user["name"]:
                create_notification(
                    submitter,
                    TYPE_TICKET_STATUS,
                    f"{ticket_id} → {body.status}",
                    f'{user["name"]} changed status to {body.status}',
                    "/tickets",
                )
        if "assignee" in sheet_updates and body.assignee and body.assignee != user["name"]:
            create_notification(
                body.assignee,
                TYPE_TICKET_ASSIGNED,
                f"Assigned: {ticket_id}",
                f'{user["name"]} assigned "{ticket["title"]}" to you',
                "/tickets",
            )
    except Exception as exc:
        _log.warning("Failed to send ticket notification: %s", exc)

    return ticket


@router.post("/bulk-update", response_model=BulkTicketResult)
async def bulk_update_tickets(body: BulkTicketUpdate, user: CurrentUser):
    """
    Apply the same status / assignee / priority to many tickets at once.

    Per-ticket permission check still applies — a non-admin only updates
    tickets they submitted or are assigned. Skipped tickets are returned
    with their reason so the UI can show a partial-success summary.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    is_admin = (user.get("role") or "").lower() == "admin"

    if not body.ticket_ids:
        return BulkTicketResult(updated=[], skipped=[])
    if not any([body.status, body.assignee is not None, body.priority]):
        raise HTTPException(status_code=400, detail="No fields to update")

    updated: list[str] = []
    skipped: list[dict] = []
    touched_for_notify: list[dict] = []

    with get_db() as conn:
        for ticket_id in body.ticket_ids:
            row = conn.execute(
                "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if not row:
                skipped.append({"ticket_id": ticket_id, "reason": "not_found"})
                continue

            ticket = dict(row)
            is_submitter = (ticket.get("submitted_by") or "") == user["name"]
            is_assignee  = (ticket.get("assignee") or "") == user["name"]
            if not (is_admin or is_submitter or is_assignee):
                skipped.append({"ticket_id": ticket_id, "reason": "forbidden"})
                continue

            sheet_updates: dict = {}
            if body.status and body.status != ticket["status"]:
                ticket["status"] = body.status
                sheet_updates["status"] = body.status
                if body.status in ("Closed", "Rejected"):
                    ticket["resolved_at"] = now
                    sheet_updates["resolved_at"] = now
            if body.assignee is not None and body.assignee != ticket["assignee"]:
                ticket["assignee"] = body.assignee
                sheet_updates["assignee"] = body.assignee
            if body.priority and body.priority != ticket["priority"]:
                ticket["priority"] = body.priority
                sheet_updates["priority"] = body.priority

            if not sheet_updates:
                skipped.append({"ticket_id": ticket_id, "reason": "no_change"})
                continue

            conn.execute(
                """UPDATE tickets
                   SET status=?, assignee=?, priority=?, resolved_at=?
                   WHERE ticket_id=?""",
                (
                    ticket["status"], ticket["assignee"], ticket["priority"],
                    ticket["resolved_at"], ticket_id,
                ),
            )
            updated.append(ticket_id)
            touched_for_notify.append({"ticket": ticket, "updates": sheet_updates})

    import threading
    for item in touched_for_notify:
        threading.Thread(
            target=_update_ticket_in_sheet,
            args=(item["ticket"]["ticket_id"], item["updates"]),
            daemon=True,
        ).start()

    try:
        from api.routers.notifications import create_notification, TYPE_TICKET_STATUS, TYPE_TICKET_ASSIGNED
        for item in touched_for_notify:
            t = item["ticket"]
            u = item["updates"]
            if "status" in u:
                submitter = t.get("submitted_by", "")
                if submitter and submitter != user["name"]:
                    create_notification(
                        submitter, TYPE_TICKET_STATUS,
                        f"{t['ticket_id']} → {u['status']}",
                        f'{user["name"]} changed status to {u["status"]}',
                        "/tickets",
                    )
            if "assignee" in u and u["assignee"] and u["assignee"] != user["name"]:
                create_notification(
                    u["assignee"], TYPE_TICKET_ASSIGNED,
                    f"Assigned: {t['ticket_id']}",
                    f'{user["name"]} assigned "{t["title"]}" to you',
                    "/tickets",
                )
    except Exception as exc:
        _log.warning("Bulk ticket notifications partly failed: %s", exc)

    return BulkTicketResult(updated=updated, skipped=skipped)
