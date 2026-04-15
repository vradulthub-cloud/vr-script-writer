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
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import CurrentUser
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
    user_parts.append("\nSuggest 5 compilation ideas for this studio.")
    user_prompt = "\n".join(user_parts)

    settings = get_settings()

    def event_stream():
        try:
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'type': 'text', 'text': text})}\n\n"
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
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'type': 'text', 'text': text})}\n\n"
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
