"""
Approvals API router.

Manages the editorial approval workflow. Editors submit content for review;
admins approve or reject. On approval, content can be optionally written
back to the target Google Sheet.

Routes:
  GET   /api/approvals/             — list approvals (filter by status/studio)
  GET   /api/approvals/{id}         — get single approval
  POST  /api/approvals/             — submit new approval request
  PATCH /api/approvals/{id}         — decide: approve or reject (admin only)
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from api.auth import CurrentUser
from api.database import get_db
from api.sheets_client import open_scripts, with_retry

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ApprovalResponse(BaseModel):
    approval_id: str
    scene_id: str
    studio: str
    content_type: str
    submitted_by: str
    submitted_at: str
    status: str
    decided_by: str
    decided_at: str
    content_json: str
    notes: str
    linked_ticket: str
    target_sheet: str
    target_range: str
    superseded_by: str


class ApprovalCreate(BaseModel):
    scene_id: str
    studio: str
    content_type: str           # "script", "description", "title"
    content_json: str           # JSON-encoded content payload
    notes: str = ""
    target_sheet: str = ""
    target_range: str = ""


class ApprovalDecide(BaseModel):
    decision: str               # "Approved" or "Rejected"
    notes: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[ApprovalResponse])
async def list_approvals(
    user: CurrentUser,
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by status. Defaults to non-closed if omitted.",
    ),
    studio: Optional[str] = None,
):
    """
    List approval requests.

    By default returns only pending/active approvals (not Closed or Rejected).
    Pass ?status=all to get everything.
    """
    query = "SELECT * FROM approvals WHERE 1=1"
    params: list = []

    if status_filter and status_filter.lower() != "all":
        query += " AND status = ?"
        params.append(status_filter)
    elif not status_filter:
        # Default: exclude closed/rejected
        query += " AND status NOT IN ('Closed', 'Rejected', 'Approved')"

    if studio:
        query += " AND studio = ?"
        params.append(studio)

    query += " ORDER BY submitted_at DESC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_approval(dict(r)) for r in rows]


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(approval_id: str, user: CurrentUser):
    """Get a single approval by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Approval not found")

    return _row_to_approval(dict(row))


@router.post("/", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
async def create_approval(body: ApprovalCreate, user: CurrentUser):
    """Submit new content for approval review."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    approval_id = f"APR-{ts}"

    approval = {
        "approval_id": approval_id,
        "scene_id": body.scene_id,
        "studio": body.studio,
        "content_type": body.content_type,
        "submitted_by": user["name"],
        "submitted_at": now,
        "status": "Pending",
        "decided_by": "",
        "decided_at": "",
        "content_json": body.content_json,
        "notes": body.notes,
        "linked_ticket": "",
        "target_sheet": body.target_sheet,
        "target_range": body.target_range,
        "superseded_by": "",
    }

    with get_db() as conn:
        conn.execute(
            """INSERT INTO approvals
               (approval_id, scene_id, studio, content_type,
                submitted_by, submitted_at, status, decided_by,
                decided_at, content_json, notes, linked_ticket,
                target_sheet, target_range, superseded_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [approval[k] for k in (
                "approval_id", "scene_id", "studio", "content_type",
                "submitted_by", "submitted_at", "status", "decided_by",
                "decided_at", "content_json", "notes", "linked_ticket",
                "target_sheet", "target_range", "superseded_by",
            )],
        )

    # Notify admins about new approval submission
    try:
        from api.routers.notifications import notify_multiple, get_admin_names, TYPE_APPROVAL_SUBMITTED
        admins = [n for n in get_admin_names() if n != user["name"]]
        if admins:
            notify_multiple(
                admins,
                TYPE_APPROVAL_SUBMITTED,
                f"New {body.content_type}: {body.scene_id}",
                f'{user["name"]} submitted {body.content_type} for review',
                "/approvals",
            )
    except Exception as exc:
        _log.warning("Failed to send approval notification: %s", exc)

    return _row_to_approval(approval)


@router.patch("/{approval_id}", response_model=ApprovalResponse)
async def decide_approval(
    approval_id: str,
    body: ApprovalDecide,
    user: CurrentUser,
):
    """
    Approve or reject a pending approval request.

    Admin access required. On approval with target_sheet + target_range set,
    fires a background write back to the appropriate Google Sheet.
    """
    if user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required to decide approvals",
        )

    if body.decision not in ("Approved", "Rejected"):
        raise HTTPException(
            status_code=400,
            detail="decision must be 'Approved' or 'Rejected'",
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Approval not found")

        approval = dict(row)

        # Build updated notes (append decision note if provided)
        existing_notes = approval.get("notes", "")
        if body.notes:
            note_entry = f"[{now} {user['name']}] {body.notes}"
            new_notes = f"{existing_notes}\n{note_entry}" if existing_notes else note_entry
        else:
            new_notes = existing_notes

        conn.execute(
            """UPDATE approvals
               SET status=?, decided_by=?, decided_at=?, notes=?
               WHERE approval_id=?""",
            (body.decision, user["name"], now, new_notes, approval_id),
        )

    approval["status"] = body.decision
    approval["decided_by"] = user["name"]
    approval["decided_at"] = now
    approval["notes"] = new_notes

    # On approval: fire-and-forget Sheets write if target is set
    if (
        body.decision == "Approved"
        and approval.get("content_type") == "script"
        and approval.get("target_sheet")
        and approval.get("target_range")
    ):
        threading.Thread(
            target=_write_script_to_sheet,
            args=(approval,),
            daemon=True,
        ).start()

    # Notify the original submitter about the decision
    try:
        from api.routers.notifications import create_notification, TYPE_APPROVAL_DECIDED
        submitter = approval.get("submitted_by", "")
        if submitter and submitter != user["name"]:
            status_word = "approved" if body.decision == "Approved" else "rejected"
            create_notification(
                submitter,
                TYPE_APPROVAL_DECIDED,
                f"{approval.get('content_type', 'Content')} {status_word}",
                f'{user["name"]} {status_word} your {approval.get("content_type", "")} for {approval.get("scene_id", "")}',
                "/approvals",
            )
    except Exception as exc:
        _log.warning("Failed to send approval decision notification: %s", exc)

    return _row_to_approval(approval)


# ---------------------------------------------------------------------------
# Sheets write helper
# ---------------------------------------------------------------------------

def _write_script_to_sheet(approval: dict) -> None:
    """
    Write approved script content back to the target Google Sheet.

    Expects approval["content_json"] to be a JSON string with script fields,
    and approval["target_range"] to be a cell range like "J5" or "G5:J5".
    """
    try:
        content = json.loads(approval.get("content_json", "{}"))
        target_range = approval.get("target_range", "")

        if not target_range or not content:
            return

        sh = open_scripts()
        # target_sheet stores the tab name for the scripts sheet
        tab_name = approval.get("target_sheet", "")
        ws = sh.worksheet(tab_name) if tab_name else sh.sheet1

        # Write each field to the appropriate cell
        # Content keys expected: theme, plot, wardrobe_f, wardrobe_m, props
        col_map = {
            "theme": 7,       # G
            "wardrobe_f": 8,  # H
            "wardrobe_m": 9,  # I
            "plot": 10,       # J
            "props": 12,      # L
        }

        # Extract row number from target_range (e.g. "J5" → row 5)
        row_num = None
        import re
        m = re.search(r"\d+", target_range)
        if m:
            row_num = int(m.group())

        if row_num:
            for field, col in col_map.items():
                value = content.get(field, "")
                if value:
                    with_retry(lambda c=col, v=value: ws.update_cell(row_num, c, v))

    except Exception as exc:
        _log.error("Failed to write approved script to Sheets: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_approval(row: dict) -> ApprovalResponse:
    return ApprovalResponse(
        approval_id=row.get("approval_id", ""),
        scene_id=row.get("scene_id", ""),
        studio=row.get("studio", ""),
        content_type=row.get("content_type", ""),
        submitted_by=row.get("submitted_by", ""),
        submitted_at=row.get("submitted_at", ""),
        status=row.get("status", ""),
        decided_by=row.get("decided_by", ""),
        decided_at=row.get("decided_at", ""),
        content_json=row.get("content_json", ""),
        notes=row.get("notes", ""),
        linked_ticket=row.get("linked_ticket", ""),
        target_sheet=row.get("target_sheet", ""),
        target_range=row.get("target_range", ""),
        superseded_by=row.get("superseded_by", ""),
    )
