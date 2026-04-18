"""
Compilations API router.

Provides endpoints for compilation scene management and AI description generation.

Routes:
  GET  /api/compilations/scenes    — list scenes flagged as compilations
  POST /api/compilations/generate  — streaming SSE compilation description
  POST /api/compilations/save      — save comp plan to SQLite + optional Sheets write
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import CurrentUser, require_grail_writer
from api.config import get_settings
from api.database import get_db
from api.prompts import DESC_COMPILATION_SYSTEMS, STUDIO_KEY_MAP
from api.routers.scenes import SceneResponse, _row_to_scene

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compilations", tags=["compilations"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CompGenRequest(BaseModel):
    studio: str
    title: str
    scene_ids: list[str]    # selected scene IDs
    notes: str = ""


class IdeasRequest(BaseModel):
    studio: str
    notes: str = ""
    count: int = 5


class CompSaveBody(BaseModel):
    studio: str
    title: str
    scene_ids: list[str]
    description: str = ""
    notes: str = ""
    target_sheet: str = ""
    target_range: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/scenes", response_model=list[SceneResponse])
async def list_compilation_scenes(
    user: CurrentUser,
    studio: Optional[str] = Query(default=None),
):
    """List all scenes flagged as compilations."""
    query = "SELECT * FROM scenes WHERE is_compilation=1"
    params: list = []

    if studio:
        query += " AND studio = ?"
        params.append(studio)

    query += " ORDER BY studio ASC, id DESC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_scene(dict(r)) for r in rows]


@router.post("/ideas")
async def generate_compilation_ideas(body: IdeasRequest, user: CurrentUser):
    """
    Suggest 4–5 compilation concepts for a studio via Claude (streaming SSE).

    Pulls available performers from the database to ground the ideas.
    """
    studio_key = STUDIO_KEY_MAP.get(body.studio)
    if not studio_key:
        raise HTTPException(status_code=400, detail=f"Unknown studio: {body.studio}")

    # Get available performers from scenes
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT performers FROM scenes WHERE studio=? AND performers != '' LIMIT 80",
            (body.studio,),
        ).fetchall()
    all_performers = list({p.strip() for r in rows for p in dict(r)["performers"].split(",") if p.strip()})[:50]

    system_prompt = (
        "You are a creative director for an adult VR studio. Suggest compelling compilation ideas "
        "that would resonate with VR porn viewers. Each idea needs:\n"
        "• A punchy, marketable title (under 60 chars)\n"
        "• A 1-sentence hook explaining the concept\n"
        "• 2-4 performer names from the available roster who fit best\n\n"
        "Format each idea as:\n"
        "TITLE: [title here]\n"
        "CONCEPT: [one sentence]\n"
        "TALENT: [comma-separated names]\n\n"
        "Generate exactly 5 ideas. Be creative — themes can include: body type, nationality, "
        "act type, era/nostalgic angle, performer archetype, season/holiday, etc."
    )

    user_parts = [f"Studio: {body.studio}"]
    if all_performers:
        user_parts.append(f"Available performers: {', '.join(all_performers[:40])}")
    if body.notes:
        user_parts.append(f"Creative direction: {body.notes}")
    n_ideas = max(3, min(10, body.count))
    user_parts.append(f"\nSuggest {n_ideas} compilation ideas for this studio.")
    user_prompt = "\n".join(user_parts)

    settings = get_settings()

    def event_stream():
        try:
            from api.ollama_client import ollama_stream
            for delta in ollama_stream(
                "comp_idea", user_prompt, system=system_prompt,
                max_tokens=1024, temperature=0.8,
            ):
                yield f"data: {json.dumps({'type': 'text', 'text': delta})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            _log.error("Compilation ideas generation failed: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/generate")
async def generate_compilation_description(body: CompGenRequest, user: CurrentUser):
    """
    Generate a compilation description via Claude (streaming SSE).

    Pulls performer names from the selected scene_ids and builds a
    context-rich prompt for the studio's compilation system prompt.
    """
    studio_key = STUDIO_KEY_MAP.get(body.studio)
    if not studio_key:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown studio: {body.studio}",
        )

    system_prompt = DESC_COMPILATION_SYSTEMS.get(studio_key)
    if not system_prompt:
        raise HTTPException(
            status_code=400,
            detail=f"No compilation prompt for studio key: {studio_key}",
        )

    # Fetch performer info for selected scenes
    performers_info: list[str] = []
    if body.scene_ids:
        with get_db() as conn:
            placeholders = ", ".join("?" * len(body.scene_ids))
            rows = conn.execute(
                f"SELECT id, title, performers FROM scenes WHERE id IN ({placeholders})",
                body.scene_ids,
            ).fetchall()
        for row in rows:
            d = dict(row)
            performers_info.append(f"- {d['id']}: {d['title']} ({d['performers']})")

    user_prompt_parts = [
        f"Write a compilation description for {body.studio}.",
        f"",
        f"Compilation Title: {body.title}",
        f"Number of scenes: {len(body.scene_ids)}",
    ]

    if performers_info:
        user_prompt_parts.append(f"\nIncluded scenes:\n" + "\n".join(performers_info))

    if body.notes:
        user_prompt_parts.append(f"\nAdditional notes: {body.notes}")

    user_prompt = "\n".join(user_prompt_parts)
    settings = get_settings()

    def event_stream():
        try:
            from api.ollama_client import ollama_stream
            for delta in ollama_stream(
                "description", user_prompt, system=system_prompt,
                max_tokens=2048, temperature=0.7,
            ):
                yield f"data: {json.dumps({'type': 'text', 'text': delta})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            _log.error("Compilation description generation failed: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/save")
async def save_compilation(body: CompSaveBody, user: CurrentUser):
    """
    Save a compilation plan to SQLite tasks table and optionally write to Sheets.

    Stores the comp plan as a completed task for history tracking.
    """
    from api.database import create_task, update_task

    task_id = create_task(
        task_type="comp_save",
        params={
            "studio": body.studio,
            "title": body.title,
            "scene_ids": body.scene_ids,
            "description": body.description,
            "notes": body.notes,
        },
        created_by=user["name"],
    )
    update_task(task_id, status="completed", result={"status": "saved"})

    # Fire-and-forget Sheets write if target is specified
    if body.target_sheet and body.target_range:
        threading.Thread(
            target=_write_comp_to_sheet,
            args=(body,),
            daemon=True,
        ).start()

    return {"task_id": task_id, "status": "saved"}


# ---------------------------------------------------------------------------
# Sheets write helper
# ---------------------------------------------------------------------------

def _write_comp_to_sheet(body: CompSaveBody) -> None:
    """Write compilation plan to the comp planning sheet."""
    try:
        from api.sheets_client import open_comp_planning, with_retry

        sh = open_comp_planning()
        ws = sh.sheet1

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        row = [
            now,
            body.studio,
            body.title,
            ", ".join(body.scene_ids),
            body.description,
            body.notes,
        ]
        with_retry(lambda: ws.append_row(row, value_input_option="USER_ENTERED"))

    except Exception as exc:
        _log.error("Failed to write compilation to Sheets: %s", exc)


# ---------------------------------------------------------------------------
# Existing compilations (from planning sheet)
# ---------------------------------------------------------------------------

class ExistingComp(BaseModel):
    title: str
    scenes: list[str]       # scene IDs
    date: str = ""          # when created


@router.get("/existing", response_model=list[ExistingComp])
async def list_existing_comps(
    user: CurrentUser,
    studio: Optional[str] = None,
):
    """
    List existing compilations from the comp planning sheet.

    Reads the sheet on every call (not cached in SQLite).
    """
    try:
        from api.sheets_client import open_comp_planning, with_retry, fetch_all_rows

        sh = open_comp_planning()
        ws = sh.sheet1
        rows = fetch_all_rows(ws)

        comps = []
        for row in rows:
            if len(row) < 4:
                continue
            row_date = row[0] if row[0] else ""
            row_studio = row[1] if len(row) > 1 else ""
            row_title = row[2] if len(row) > 2 else ""
            row_scenes = row[3] if len(row) > 3 else ""

            if studio and row_studio != studio:
                continue
            if not row_title:
                continue

            scene_ids = [s.strip() for s in row_scenes.split(",") if s.strip()]
            comps.append(ExistingComp(
                title=row_title,
                scenes=scene_ids,
                date=row_date,
            ))

        return comps
    except Exception as exc:
        _log.error("Failed to load existing comps: %s", exc)
        return []


@router.post("/grail-write")
async def write_comp_to_grail(body: CompSaveBody, _writer: dict = Depends(require_grail_writer)):
    """Write compilation scenes to the Grail sheet. Requires grail-writer permission."""
    # Mark scenes as compilation in SQLite
    with get_db() as conn:
        for scene_id in body.scene_ids:
            conn.execute(
                "UPDATE scenes SET is_compilation=1 WHERE id=?",
                (scene_id,),
            )

    return {"status": "written", "scene_count": len(body.scene_ids)}
