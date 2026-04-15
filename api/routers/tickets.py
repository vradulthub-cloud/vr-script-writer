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
    """Write a ticket row to the Google Sheets Tickets tab (async-safe)."""
    try:
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
        row = [
            ticket["ticket_id"],
            ticket["title"],
            ticket["description"],
            ticket["project"],
            ticket["type"],
            ticket["priority"],
            ticket["status"],
            ticket["submitted_by"],
            ticket["submitted_at"],
            ticket["assignee"],
            ticket["notes"],
            ticket["resolved_at"],
            ticket["linked_items"],
        ]
        with_retry(lambda: ws.append_row(row, value_input_option="USER_ENTERED"))
    except Exception as exc:
        _log.error("Failed to write ticket to Sheets: %s", exc)


def _update_ticket_in_sheet(ticket_id: str, updates: dict) -> None:
    """Update a ticket row in Google Sheets by finding its row."""
    try:
        sh = open_tickets()
        ws = get_or_create_worksheet(sh, "Tickets")
        cell = with_retry(lambda: ws.find(ticket_id, in_column=1))
        if not cell:
            _log.warning("Ticket %s not found in sheet", ticket_id)
            return

        row_num = cell.row
        # Column mapping: A=1=ticket_id, B=2=title, ... G=7=status, J=10=assignee, K=11=notes, L=12=resolved_at
        col_map = {
            "status": 7,
            "assignee": 10,
            "notes": 11,
            "priority": 6,
            "resolved_at": 12,
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
):
    """List tickets with optional filters."""
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

    query += " ORDER BY submitted_at DESC"

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

    return ticket
