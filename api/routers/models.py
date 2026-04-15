"""
Models API router.

Provides read endpoints for the model/performer booking database.
Sourced from the Booking sheet, synced into the bookings SQLite table.

Routes:
  GET /api/models/        — list all models, optional search
  GET /api/models/{name}  — get single model by name (case-insensitive)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.auth import CurrentUser
from api.database import get_db

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ModelResponse(BaseModel):
    name: str
    agency: str
    agency_link: str
    rate: str
    rank: str           # Great / Good / Moderate / Poor
    notes: str          # Available For / acts (from Notes column)
    info: str           # Raw compact metadata string
    # Parsed info fields
    age: str
    last_booked: str
    bookings_count: str
    location: str
    # Computed
    opportunity_score: int   # 0–100


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[ModelResponse])
async def list_models(
    user: CurrentUser,
    search: Optional[str] = Query(default=None, description="Search by name or agency"),
):
    """List all models from the bookings table, optionally filtered by name or agency."""
    query = "SELECT name, agency, agency_link, rate, rank, notes, info FROM bookings WHERE 1=1"
    params: list = []

    if search:
        query += " AND (name LIKE ? OR agency LIKE ? OR notes LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    query += " ORDER BY name ASC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_model(dict(r)) for r in rows]


@router.get("/{name}", response_model=ModelResponse)
async def get_model(name: str, user: CurrentUser):
    """Get a single model by name (case-insensitive exact match)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT name, agency, agency_link, rate, rank, notes, info FROM bookings WHERE LOWER(name) = LOWER(?)",
            (name,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Model '{name}' not found")

    return _row_to_model(dict(row))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_info(info: str) -> dict[str, str]:
    """Parse the compact info string into individual fields.

    Format: "Age: 30 · Last booked: Oct 2025 · Bookings: 3 · Location: Vegas"
    The separator is ' · ' (space + U+00B7 middle dot + space).
    """
    result = {"age": "", "last_booked": "", "bookings_count": "", "location": ""}
    if not info:
        return result

    # Split on any variant of the separator (middle dot, bullet, or plain dash)
    parts = re.split(r"\s*[·•\-]\s*", info)
    for part in parts:
        part = part.strip()
        if part.lower().startswith("age:"):
            result["age"] = part[4:].strip()
        elif part.lower().startswith("last booked:"):
            result["last_booked"] = part[12:].strip()
        elif part.lower().startswith("bookings:"):
            result["bookings_count"] = part[9:].strip()
        elif part.lower().startswith("location:"):
            result["location"] = part[9:].strip()
    return result


def _months_since_booked(last_booked: str) -> Optional[int]:
    """Parse 'Oct 2025' or 'March 2026' into months-ago integer.

    Returns None if parsing fails.
    """
    if not last_booked:
        return None
    now = datetime.now(timezone.utc)
    for fmt in ("%b %Y", "%B %Y", "%m/%Y", "%Y"):
        try:
            dt = datetime.strptime(last_booked.strip(), fmt)
            months = (now.year - dt.year) * 12 + (now.month - dt.month)
            return max(0, months)
        except ValueError:
            continue
    return None


def _opportunity_score(rank: str, last_booked: str) -> int:
    """Compute a 0-100 opportunity score from available booking-sheet data.

    Components available without platform scraping:
      - Rank score  (0-25): quality signal from booker experience
      - Urgency score (0-30): time since last booking with our studios

    Both are normalized to 0-100 (max raw = 55).
    """
    # Rank component
    rank_map = {"great": 25, "good": 18, "moderate": 10, "poor": 3}
    rank_score = rank_map.get(rank.lower().strip(), 0)

    # Urgency component
    months = _months_since_booked(last_booked)
    if months is None:
        urgency_score = 30  # Never booked = maximum urgency
    elif months > 36:
        urgency_score = 28
    elif months > 24:
        urgency_score = 22
    elif months > 12:
        urgency_score = 15
    elif months > 6:
        urgency_score = 8
    else:
        urgency_score = 3

    raw = rank_score + urgency_score
    return round(raw / 55 * 100)


def _row_to_model(row: dict) -> ModelResponse:
    info = row.get("info", "") or ""
    parsed = _parse_info(info)
    rank = row.get("rank", "") or ""
    score = _opportunity_score(rank, parsed["last_booked"])

    return ModelResponse(
        name=row.get("name", ""),
        agency=row.get("agency", ""),
        agency_link=row.get("agency_link", ""),
        rate=row.get("rate", ""),
        rank=rank,
        notes=row.get("notes", ""),
        info=info,
        age=parsed["age"],
        last_booked=parsed["last_booked"],
        bookings_count=parsed["bookings_count"],
        location=parsed["location"],
        opportunity_score=score,
    )
