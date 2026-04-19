"""
Compilations API router.

Provides endpoints for compilation scene management and AI description generation.

Routes:
  GET  /api/compilations/scenes    — list scenes flagged as compilations
  POST /api/compilations/generate  — streaming SSE compilation description
  POST /api/compilations/save      — save comp plan to SQLite + Sheets write
  GET  /api/compilations/existing  — list existing comps from Index tabs
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Optional

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
# Index-tab schema (one row per scene within a compilation).
#
# A single comp spans N contiguous rows sharing the same Comp ID. Comp-level
# fields (Title, Volume, Status, Description, Notes, Created, Created By)
# repeat on every scene row so each row stands alone for the video editor —
# filter by Comp ID in the sheet UI and every MEGA link is visible.
# ---------------------------------------------------------------------------
INDEX_HEADERS = [
    "Created (UTC)",    # A
    "Created By",       # B
    "Comp ID",          # C — e.g. FPVR-C0007
    "Comp Title",       # D
    "Volume",           # E — "Vol. 3" or "New"
    "Status",           # F — Draft / Planned / Published
    "Scene #",          # G — 1, 2, 3 …
    "Scene ID",         # H — FPVR0369
    "Scene Title",      # I
    "Performers",       # J
    "SLR Link",         # K
    "MEGA Link",        # L — shareable URL for the video editor
    "Description",      # M — only on Scene # = 1
    "Notes",            # N
    "Updated",          # O
]

INDEX_TAB_SUFFIX = " Index"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CompGenRequest(BaseModel):
    studio: str
    title: str
    scene_ids: list[str]
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
    status: str = "Draft"
    volume: str = ""


class CompSceneRow(BaseModel):
    scene_id: str
    scene_num: int
    title: str = ""
    performers: str = ""
    slr_link: str = ""
    mega_link: str = ""


class ExistingComp(BaseModel):
    comp_id: str
    title: str
    volume: str = ""
    status: str = ""
    studio_key: str
    created: str = ""
    created_by: str = ""
    updated: str = ""
    description: str = ""
    notes: str = ""
    scene_count: int = 0
    scenes: list[CompSceneRow] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _studio_key(studio: str) -> str:
    """Map UI studio name → comp index key (FPVR/VRH/VRA/NJOI)."""
    key = STUDIO_KEY_MAP.get(studio)
    if not key:
        raise HTTPException(status_code=400, detail=f"Unknown studio: {studio}")
    return key


def _index_tab_name(studio_key: str) -> str:
    return f"{studio_key}{INDEX_TAB_SUFFIX}"


def _open_index_ws(studio_key: str):
    """Get-or-create the studio's Index worksheet with header row."""
    from api.sheets_client import open_comp_planning, get_or_create_worksheet

    sh = open_comp_planning()
    return get_or_create_worksheet(
        sh,
        _index_tab_name(studio_key),
        headers=INDEX_HEADERS,
        rows=1000,
    )


def _next_comp_id(ws, studio_key: str) -> str:
    """Scan Comp ID column (C) and return the next sequential ID."""
    from api.sheets_client import with_retry

    col_c = with_retry(lambda: ws.col_values(3))  # ['Comp ID', 'FPVR-C0001', ...]
    max_n = 0
    pat = re.compile(rf"^{re.escape(studio_key)}-C(\d+)$")
    for cell in col_c[1:]:  # skip header
        m = pat.match(cell.strip())
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"{studio_key}-C{max_n + 1:04d}"


def _mega_link_for(grail_id: str) -> str:
    """Return a shareable MEGA folder URL (or internal rclone path on non-Windows).

    Wraps comp_tools.mega_export_link with a guard against import failure.
    """
    try:
        import sys, os
        scripts_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from comp_tools import mega_export_link  # type: ignore
        return mega_export_link(grail_id)
    except Exception as exc:
        _log.warning("mega_export_link failed for %s: %s", grail_id, exc)
        return ""


# ---------------------------------------------------------------------------
# Routes — list / generate
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
    """Suggest compilation concepts for a studio via Ollama (streaming SSE)."""
    studio_key = STUDIO_KEY_MAP.get(body.studio)
    if not studio_key:
        raise HTTPException(status_code=400, detail=f"Unknown studio: {body.studio}")

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
    """Generate a compilation description via Ollama (streaming SSE)."""
    studio_key = STUDIO_KEY_MAP.get(body.studio)
    if not studio_key:
        raise HTTPException(status_code=400, detail=f"Unknown studio: {body.studio}")

    system_prompt = DESC_COMPILATION_SYSTEMS.get(studio_key)
    if not system_prompt:
        raise HTTPException(
            status_code=400,
            detail=f"No compilation prompt for studio key: {studio_key}",
        )

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
        "",
        f"Compilation Title: {body.title}",
        f"Number of scenes: {len(body.scene_ids)}",
    ]
    if performers_info:
        user_prompt_parts.append("\nIncluded scenes:\n" + "\n".join(performers_info))
    if body.notes:
        user_prompt_parts.append(f"\nAdditional notes: {body.notes}")

    user_prompt = "\n".join(user_prompt_parts)

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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Save — persist to SQLite + write to Sheets Index tab (background)
# ---------------------------------------------------------------------------

@router.post("/save")
async def save_compilation(body: CompSaveBody, user: CurrentUser):
    """Save a compilation to SQLite tasks + write to the studio's Index tab."""
    from api.database import create_task, update_task

    # Validate studio eagerly so the UI gets a fast failure
    _studio_key(body.studio)

    task_id = create_task(
        task_type="comp_save",
        params={
            "studio": body.studio,
            "title": body.title,
            "scene_ids": body.scene_ids,
            "description": body.description,
            "notes": body.notes,
            "status": body.status,
            "volume": body.volume,
        },
        created_by=user["name"],
    )
    update_task(task_id, status="completed", result={"status": "saved"})

    # Fire-and-forget sheet write. This can take 10-30s because MEGA link
    # generation serially shells out to MEGAcmd per scene.
    threading.Thread(
        target=_write_comp_to_index,
        args=(body, user.get("name", "")),
        daemon=True,
    ).start()

    return {"task_id": task_id, "status": "saved"}


def _write_comp_to_index(body: CompSaveBody, created_by: str) -> None:
    """Append per-scene rows to the studio's {STUDIO} Index worksheet."""
    try:
        from api.sheets_client import with_retry

        studio_key = STUDIO_KEY_MAP.get(body.studio, "")
        if not studio_key:
            _log.warning("Unknown studio on save: %s", body.studio)
            return

        ws = _open_index_ws(studio_key)
        comp_id = _next_comp_id(ws, studio_key)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        # Look up scene metadata
        scene_meta: dict[str, dict] = {}
        if body.scene_ids:
            with get_db() as conn:
                placeholders = ", ".join("?" * len(body.scene_ids))
                rows = conn.execute(
                    f"SELECT id, title, performers FROM scenes WHERE id IN ({placeholders})",
                    body.scene_ids,
                ).fetchall()
            scene_meta = {dict(r)["id"]: dict(r) for r in rows}

        # Build rows in the same order the user picked them
        new_rows: list[list] = []
        for i, sid in enumerate(body.scene_ids, start=1):
            meta = scene_meta.get(sid, {})
            mega = _mega_link_for(sid)
            desc_cell = body.description if i == 1 else ""
            notes_cell = body.notes if i == 1 else ""
            new_rows.append([
                now,                              # A Created
                created_by,                       # B Created By
                comp_id,                          # C Comp ID
                body.title,                       # D Comp Title
                body.volume or "",                # E Volume
                body.status or "Draft",           # F Status
                i,                                # G Scene #
                sid,                              # H Scene ID
                meta.get("title", ""),            # I Scene Title
                meta.get("performers", ""),       # J Performers
                "",                               # K SLR Link (reserved)
                mega,                             # L MEGA Link
                desc_cell,                        # M Description
                notes_cell,                       # N Notes
                now,                              # O Updated
            ])

        if new_rows:
            with_retry(lambda: ws.append_rows(new_rows, value_input_option="USER_ENTERED"))
            _log.info("Wrote %d scene rows for comp %s (%s)", len(new_rows), comp_id, studio_key)
    except Exception as exc:
        _log.error("Failed to write compilation to Index tab: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Existing comps — read Index tabs, group by Comp ID
# ---------------------------------------------------------------------------

@router.get("/existing", response_model=list[ExistingComp])
async def list_existing_comps(
    user: CurrentUser,
    studio: Optional[str] = None,
):
    """List existing compilations from the Index tabs, grouped by Comp ID.

    If `studio` is given (UI name or key), only that studio's tab is read.
    Otherwise all four studio tabs are read and merged.
    """
    from api.sheets_client import fetch_as_dicts

    # Figure out which studio_keys to read
    if studio:
        # Accept either UI name ("FuckPassVR") or key ("FPVR")
        keys = [STUDIO_KEY_MAP.get(studio, studio)]
    else:
        keys = list(STUDIO_KEY_MAP.values())

    comps_by_id: dict[str, ExistingComp] = {}

    for key in keys:
        try:
            ws = _open_index_ws(key)
            records = fetch_as_dicts(ws)
        except Exception as exc:
            _log.warning("Could not read %s Index: %s", key, exc)
            continue

        for rec in records:
            cid = str(rec.get("Comp ID", "")).strip()
            if not cid:
                continue
            scene_num_raw = rec.get("Scene #", "")
            try:
                scene_num = int(scene_num_raw)
            except (TypeError, ValueError):
                continue

            if cid not in comps_by_id:
                comps_by_id[cid] = ExistingComp(
                    comp_id=cid,
                    title=str(rec.get("Comp Title", "")).strip(),
                    volume=str(rec.get("Volume", "")).strip(),
                    status=str(rec.get("Status", "")).strip(),
                    studio_key=key,
                    created=str(rec.get("Created (UTC)", "")).strip(),
                    created_by=str(rec.get("Created By", "")).strip(),
                    updated=str(rec.get("Updated", "")).strip(),
                    description="",
                    notes="",
                    scene_count=0,
                    scenes=[],
                )

            comp = comps_by_id[cid]
            comp.scenes.append(CompSceneRow(
                scene_id=str(rec.get("Scene ID", "")).strip(),
                scene_num=scene_num,
                title=str(rec.get("Scene Title", "")).strip(),
                performers=str(rec.get("Performers", "")).strip(),
                slr_link=str(rec.get("SLR Link", "")).strip(),
                mega_link=str(rec.get("MEGA Link", "")).strip(),
            ))
            # Description lives on scene #1 — grab it when we see it
            if scene_num == 1:
                comp.description = str(rec.get("Description", "")).strip()
                comp.notes = str(rec.get("Notes", "")).strip()

    # Finalise
    results: list[ExistingComp] = []
    for comp in comps_by_id.values():
        comp.scenes.sort(key=lambda s: s.scene_num)
        comp.scene_count = len(comp.scenes)
        results.append(comp)

    # Newest-first by Created timestamp (falls back alphabetically)
    results.sort(key=lambda c: (c.created, c.comp_id), reverse=True)
    return results


# ---------------------------------------------------------------------------
# Grail write (unchanged — flags scenes as is_compilation)
# ---------------------------------------------------------------------------

@router.post("/grail-write")
async def write_comp_to_grail(body: CompSaveBody, _writer: dict = Depends(require_grail_writer)):
    """Flag scenes as is_compilation=1 in the scenes table."""
    with get_db() as conn:
        for scene_id in body.scene_ids:
            conn.execute(
                "UPDATE scenes SET is_compilation=1 WHERE id=?",
                (scene_id,),
            )
    return {"status": "written", "scene_count": len(body.scene_ids)}
