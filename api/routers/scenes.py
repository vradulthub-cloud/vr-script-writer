"""
Scenes API router.

Provides read endpoints for scene metadata (Grail + MEGA asset status).
All reads go to SQLite (sub-ms). No write endpoints here — Grail writes
go through the approvals flow.

Routes:
  GET /api/scenes/stats    — counts per studio + overall completion %
  GET /api/scenes/         — list scenes with filters
  GET /api/scenes/{id}     — single scene detail
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.auth import CurrentUser
from api.database import get_db

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenes", tags=["scenes"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SceneResponse(BaseModel):
    id: str
    studio: str
    site_code: str
    title: str
    performers: str
    categories: str
    tags: str
    is_compilation: bool
    has_description: bool
    has_videos: bool
    video_count: int
    has_thumbnail: bool
    has_photos: bool
    has_storyboard: bool
    storyboard_count: int
    mega_path: str
    grail_row: int


class SceneStats(BaseModel):
    total: int
    by_studio: dict[str, int]
    complete: int       # all 5 core assets present
    missing_any: int    # missing at least one core asset


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=SceneStats)
async def scene_stats(user: CurrentUser):
    """Get scene counts by studio and overall completion percentage."""
    with get_db() as conn:
        total_row = conn.execute("SELECT COUNT(*) as cnt FROM scenes").fetchone()
        total = dict(total_row)["cnt"]

        studio_rows = conn.execute(
            "SELECT studio, COUNT(*) as cnt FROM scenes GROUP BY studio"
        ).fetchall()
        by_studio = {dict(r)["studio"]: dict(r)["cnt"] for r in studio_rows}

        # "Complete" = has description, videos, thumbnail, photos, and storyboard
        complete_row = conn.execute(
            """SELECT COUNT(*) as cnt FROM scenes
               WHERE has_description=1 AND has_videos=1
                 AND has_thumbnail=1 AND has_photos=1 AND has_storyboard=1"""
        ).fetchone()
        complete = dict(complete_row)["cnt"]

    return SceneStats(
        total=total,
        by_studio=by_studio,
        complete=complete,
        missing_any=total - complete,
    )


@router.get("/", response_model=list[SceneResponse])
async def list_scenes(
    user: CurrentUser,
    studio: Optional[str] = None,
    missing_only: bool = False,
    search: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
):
    """
    List scenes with optional filters.

    - studio: filter by studio UI name (e.g. "VRHush")
    - missing_only: only scenes missing at least one core asset
    - search: substring search in title or performers
    - page/limit: pagination
    """
    query = "SELECT * FROM scenes WHERE 1=1"
    params: list = []

    if studio:
        query += " AND studio = ?"
        params.append(studio)

    if missing_only:
        query += (
            " AND (has_description=0 OR has_videos=0"
            " OR has_thumbnail=0 OR has_photos=0 OR has_storyboard=0)"
        )

    if search:
        query += " AND (title LIKE ? OR performers LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])

    query += " ORDER BY id DESC"

    offset = (page - 1) * limit
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_scene(dict(r)) for r in rows]


@router.get("/{scene_id}", response_model=SceneResponse)
async def get_scene(scene_id: str, user: CurrentUser):
    """Get a single scene by ID (e.g. 'VRH0758')."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Scene not found")

    return _row_to_scene(dict(row))


# ---------------------------------------------------------------------------
# MEGA action endpoints
# ---------------------------------------------------------------------------

@router.post("/mega-refresh")
async def trigger_mega_refresh(user: CurrentUser):
    """
    Write a trigger file requesting a MEGA scan refresh.

    The Windows-side mega_scan_worker.py watches for mega_scan_request.json
    and runs a fresh scan when it appears.
    """
    import json
    from datetime import datetime, timezone
    from api.config import get_settings

    trigger_path = get_settings().base_dir / "mega_scan_request.json"
    data = {
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "requested_by": user.get("email", user.get("name", "unknown")),
    }
    try:
        trigger_path.write_text(json.dumps(data))
        return {"status": "triggered", "message": "MEGA scan requested — worker will run shortly"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write trigger file: {exc}")


class FolderCreateBody(BaseModel):
    scene_id: str


@router.post("/create-folder")
async def create_mega_folder(body: FolderCreateBody, user: CurrentUser):
    """
    Queue a MEGA folder creation request for a scene.

    Appends to mega_folder_request.json — the Windows-side worker
    reads this and runs `mega-mkdir` for each queued scene.
    """
    import json
    from datetime import datetime, timezone
    from api.config import get_settings

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, studio, mega_path FROM scenes WHERE id=?", (body.scene_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Scene not found")

    scene = dict(row)
    trigger_path = get_settings().base_dir / "mega_folder_request.json"
    entry = {
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "requested_by": user.get("email", user.get("name", "unknown")),
        "scene_id": body.scene_id,
        "studio": scene["studio"],
    }
    try:
        existing: list = []
        if trigger_path.exists():
            try:
                existing = json.loads(trigger_path.read_text())
                if not isinstance(existing, list):
                    existing = [existing]
            except Exception:
                existing = []
        existing.append(entry)
        trigger_path.write_text(json.dumps(existing, indent=2))
        return {"status": "queued", "scene_id": body.scene_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to queue folder creation: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_scene(row: dict) -> SceneResponse:
    return SceneResponse(
        id=row["id"],
        studio=row["studio"],
        site_code=row.get("site_code", ""),
        title=row.get("title", ""),
        performers=row.get("performers", ""),
        categories=row.get("categories", ""),
        tags=row.get("tags", ""),
        is_compilation=bool(row.get("is_compilation", 0)),
        has_description=bool(row.get("has_description", 0)),
        has_videos=bool(row.get("has_videos", 0)),
        video_count=row.get("video_count", 0),
        has_thumbnail=bool(row.get("has_thumbnail", 0)),
        has_photos=bool(row.get("has_photos", 0)),
        has_storyboard=bool(row.get("has_storyboard", 0)),
        storyboard_count=row.get("storyboard_count", 0),
        mega_path=row.get("mega_path", ""),
        grail_row=row.get("grail_row", 0),
    )
