"""
Calendar events API router.

Custom events shown on the Shoot Tracker calendar (alongside shoots and US
holidays). Shared across the team — no per-user scoping. Stored in SQLite
only (not synced to Sheets) since these are operational scratch notes,
not authoritative production data.

Endpoints:
  GET    /api/calendar-events/?from=YYYY-MM-DD&to=YYYY-MM-DD
  POST   /api/calendar-events/
  DELETE /api/calendar-events/{event_id}
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.auth import CurrentUser
from api.database import get_db

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calendar-events", tags=["calendar-events"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CalendarEvent(BaseModel):
    event_id: str
    date: str
    title: str
    kind: str = ""
    color: str = ""
    notes: str = ""
    created_by: str = ""
    created_at: str


class CreateEventRequest(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    title: str = Field(..., min_length=1, max_length=200)
    kind: str = Field("", max_length=40)
    color: str = Field("", max_length=20)
    notes: str = Field("", max_length=2000)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[CalendarEvent])
async def list_events(
    user: CurrentUser,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    """List calendar events. Optionally filter by date range (inclusive)."""
    sql = (
        "SELECT event_id, date, title, kind, color, notes, created_by, created_at "
        "FROM calendar_events"
    )
    clauses: list[str] = []
    params: list = []
    if from_date:
        clauses.append("date >= ?")
        params.append(from_date)
    if to_date:
        clauses.append("date <= ?")
        params.append(to_date)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY date ASC, created_at ASC"

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.post("/", response_model=CalendarEvent, status_code=status.HTTP_201_CREATED)
async def create_event(payload: CreateEventRequest, user: CurrentUser):
    """Create a new calendar event."""
    # Validate date format defensively — pydantic accepts any string by design.
    try:
        datetime.strptime(payload.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date must be YYYY-MM-DD",
        )

    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()
    created_by = user.get("name", "") or user.get("email", "")

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO calendar_events
            (event_id, date, title, kind, color, notes, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                payload.date,
                payload.title.strip(),
                payload.kind.strip(),
                payload.color.strip(),
                payload.notes.strip(),
                created_by,
                created_at,
            ),
        )

    _log.info("Calendar event %s created by %s on %s", event_id, created_by, payload.date)

    return CalendarEvent(
        event_id=event_id,
        date=payload.date,
        title=payload.title.strip(),
        kind=payload.kind.strip(),
        color=payload.color.strip(),
        notes=payload.notes.strip(),
        created_by=created_by,
        created_at=created_at,
    )


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: str, user: CurrentUser):
    """Delete a calendar event. Anyone on the team may delete any event."""
    with get_db() as conn:
        result = conn.execute(
            "DELETE FROM calendar_events WHERE event_id = ?",
            (event_id,),
        )
        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )
    _log.info("Calendar event %s deleted by %s", event_id, user.get("name", ""))
    return None
