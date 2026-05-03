"""
Background tasks API router.

Surfaces the local `tasks` table (script_gen, desc_gen, mega_scan, etc.) so
the admin panel can show what's running and what's recently completed.
Reads only — task creation lives inside the worker code paths that own
each task type. Admin-only because task params/results may include
prompts and other internals editors don't need to see.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.auth import require_admin
from api.database import get_db

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskRow(BaseModel):
    task_id: str
    task_type: str
    status: str
    progress: float = 0.0
    created_at: str
    started_at: str = ""
    completed_at: str = ""
    created_by: str = ""
    error: str = ""
    # We keep params/result as opaque strings so the row stays small over the
    # wire. The admin panel only needs an at-a-glance summary; full payloads
    # would balloon the response (some scene-gen tasks store 10kB of prompts).


class TaskStats(BaseModel):
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    total: int = 0


@router.get("/stats", response_model=TaskStats)
async def task_stats(_admin: dict = Depends(require_admin)):
    """Counts grouped by status — feeds the quick-stats strip."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM tasks GROUP BY status"
        ).fetchall()
    counts = {dict(r)["status"]: dict(r)["count"] for r in rows}
    total = sum(counts.values())
    return TaskStats(
        pending=counts.get("pending", 0),
        running=counts.get("running", 0),
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
        total=total,
    )


@router.get("/", response_model=list[TaskRow])
async def list_tasks(
    _admin: dict = Depends(require_admin),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Most-recent tasks first. Defaults to the last 50 across all statuses."""
    query = "SELECT * FROM tasks"
    params: list = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    # Order by created_at DESC — completed_at is null for pending/running, and
    # most callers care about "what's been queued recently" more than "what
    # finished recently".
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    out: list[TaskRow] = []
    for r in rows:
        d = dict(r)
        out.append(TaskRow(
            task_id=d["task_id"],
            task_type=d["task_type"],
            status=d.get("status") or "pending",
            progress=float(d.get("progress") or 0),
            created_at=d.get("created_at") or "",
            started_at=d.get("started_at") or "",
            completed_at=d.get("completed_at") or "",
            created_by=d.get("created_by") or "",
            error=d.get("error") or "",
        ))
    return out
