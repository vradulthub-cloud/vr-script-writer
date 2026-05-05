"""
Scripts API router.

Provides endpoints for script inventory and AI script generation.

Routes:
  GET  /api/scripts/          — list scripts with filters
  GET  /api/scripts/tabs      — list available month tabs from SQLite
  POST /api/scripts/generate  — streaming SSE script generation (or static for NJOI)
  POST /api/scripts/save      — save generated script to SQLite + Sheets
"""

from __future__ import annotations

import json
import logging
import random
import threading
from datetime import datetime, timezone
from typing import Optional

import anthropic
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import CurrentUser
from api.config import get_settings
from api.database import enrich_from_script_row, get_db
from api.prompts import SYSTEM_PROMPT, NJOI_STATIC_PLOT, build_script_prompt, get_prompt
from api.sheets_client import open_scripts, with_retry

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ScriptResponse(BaseModel):
    id: int
    tab_name: str
    sheet_row: int
    studio: str
    shoot_date: str
    location: str
    scene_type: str
    female: str
    male: str
    theme: str
    wardrobe_f: str
    wardrobe_m: str
    plot: str
    title: str
    props: str
    script_status: str


class ScriptGenRequest(BaseModel):
    studio: str
    scene_type: str = "BG"          # "BG" or "BGCP"
    female: str
    male: str = "POV"
    destination: str | None = None  # FPVR only
    director_note: str | None = None


class ScriptSaveBody(BaseModel):
    script_id: int | None = None    # existing row to update (None = create new)
    tab_name: str
    sheet_row: int
    theme: str = ""
    plot: str = ""
    wardrobe_f: str = ""
    wardrobe_m: str = ""
    shoot_location: str = ""
    set_design: str = ""
    props: str = ""
    # Optional — when present, links this save back to a /generate call so we
    # can track raw model output → edited final version diff for fine-tuning.
    generation_id: int | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/tabs")
async def list_tabs(user: CurrentUser):
    """List all available month tab names from the scripts table."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT tab_name FROM scripts ORDER BY tab_name DESC"
        ).fetchall()
    return [dict(r)["tab_name"] for r in rows]


@router.get("/", response_model=list[ScriptResponse])
async def list_scripts(
    user: CurrentUser,
    studio: Optional[str] = None,
    tab_name: Optional[str] = None,
    search: Optional[str] = None,
    needs_script: bool = False,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
):
    """
    List scripts with optional filters.

    - studio: filter by studio UI name
    - tab_name: filter by specific monthly tab (e.g. "April 2026")
    - search: substring match on female performer name
    - needs_script: only rows where plot is empty
    """
    query = "SELECT * FROM scripts WHERE 1=1"
    params: list = []

    if studio:
        query += " AND studio = ?"
        params.append(studio)

    if tab_name:
        query += " AND tab_name = ?"
        params.append(tab_name)

    if search:
        query += " AND female LIKE ?"
        params.append(f"%{search}%")

    if needs_script:
        query += " AND (plot IS NULL OR plot = '')"

    query += " ORDER BY tab_name DESC, sheet_row ASC"

    offset = (page - 1) * limit
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_script(dict(r)) for r in rows]


SCRIPT_MODEL_ID = "vr-scriptwriter:latest"
SCRIPT_TEMPERATURE = 0.8
SCRIPT_MAX_TOKENS = 4096


def _create_generation_row(
    *, body: ScriptGenRequest, user_email: str,
    model_id: str, seed: int, temperature: float,
) -> int:
    """Insert a script_generations row at /generate start; return the row id.

    Empty raw_output at this point — gets filled in via _finalize_generation
    once the stream completes (or stays empty if it errors mid-stream).
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO script_generations
               (generated_at, generated_by, studio, scene_type, female, male,
                destination, director_note, model_id, seed, temperature,
                raw_output, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (
                now, user_email,
                body.studio, body.scene_type, body.female, body.male,
                body.destination or "", body.director_note or "",
                model_id, seed, temperature,
                "",
            ),
        )
        return cur.lastrowid


def _finalize_generation(gen_id: int, raw_output: str) -> None:
    """Update the script_generations row with the accumulated stream output."""
    if not gen_id:
        return
    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE script_generations SET raw_output=? WHERE id=?",
                (raw_output, gen_id),
            )
    except Exception as exc:
        _log.warning("Failed to finalize generation %d: %s", gen_id, exc)


@router.post("/generate")
async def generate_script(body: ScriptGenRequest, user: CurrentUser):
    """
    Generate a VR production script via Ollama (streamed) or static plot for NJOI.

    Every call creates a row in script_generations capturing the prompt input,
    model parameters, and (after the stream completes) the raw model output —
    so we can later correlate raw output with what got edited and approved.
    For streaming responses, the client receives a `generation_id` SSE event
    before any text deltas; that id should be passed back on /save so the
    edited version is linked to the source generation.
    """
    user_email = user.get("email", "")

    # NJOI uses a fixed plot — no AI, but still log the call for completeness
    if body.studio == "NaughtyJOI":
        gen_id = _create_generation_row(
            body=body, user_email=user_email,
            model_id="static-njoi", seed=0, temperature=0.0,
        )
        _finalize_generation(gen_id, NJOI_STATIC_PLOT)
        return {
            "plot": NJOI_STATIC_PLOT,
            "theme": "JOI Experience",
            "streaming": False,
            "generation_id": gen_id,
        }

    seed = random.randint(0, 2**31 - 1)
    gen_id = _create_generation_row(
        body=body, user_email=user_email,
        model_id=SCRIPT_MODEL_ID, seed=seed, temperature=SCRIPT_TEMPERATURE,
    )

    def event_stream():
        accumulated: list[str] = []
        try:
            from api.ollama_client import ollama_stream
            prompt = build_script_prompt(
                body.studio,
                body.scene_type,
                body.female,
                body.male,
                body.destination,
                body.director_note,
            )
            sys_p = get_prompt("script.system", fallback=SYSTEM_PROMPT)
            # Send the generation_id first so the client can attach it to /save.
            yield f"data: {json.dumps({'type': 'generation_id', 'id': gen_id})}\n\n"
            for delta in ollama_stream(
                "script", prompt, system=sys_p,
                max_tokens=SCRIPT_MAX_TOKENS, temperature=SCRIPT_TEMPERATURE, seed=seed,
            ):
                accumulated.append(delta)
                yield f"data: {json.dumps({'type': 'text', 'text': delta})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            _log.error("Script generation failed: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
        finally:
            # Persist whatever we got — even partial output is useful training
            # signal for "what made the model fail mid-script".
            _finalize_generation(gen_id, "".join(accumulated))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/save")
async def save_script(body: ScriptSaveBody, user: CurrentUser):
    """
    Save a generated script back to SQLite and fire-and-forget to Sheets.

    If script_id is provided, updates that row.
    Otherwise creates a new row.

    Runs the slop filter (see api.slop_filter) across every user-visible
    field at save time so the model's raw output streams live but the
    copy that lands in Sheets is post-processed.
    """
    from api.slop_filter import post_process

    body = body.model_copy(update={
        "theme": post_process(body.theme or ""),
        "plot": post_process(body.plot or ""),
        "wardrobe_f": post_process(body.wardrobe_f or ""),
        "wardrobe_m": post_process(body.wardrobe_m or ""),
        "shoot_location": post_process(body.shoot_location or ""),
        "props": post_process(body.props or ""),
    })
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        if body.script_id is not None:
            # Update existing row
            row = conn.execute(
                "SELECT * FROM scripts WHERE id = ?", (body.script_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Script not found")

            conn.execute(
                """UPDATE scripts
                   SET theme=?, plot=?, wardrobe_f=?, wardrobe_m=?,
                       location=?, props=?, synced_at=?
                   WHERE id=?""",
                (
                    body.theme,
                    body.plot,
                    body.wardrobe_f,
                    body.wardrobe_m,
                    body.shoot_location,
                    body.props,
                    now,
                    body.script_id,
                ),
            )
            script_id = body.script_id
        else:
            # Insert new row
            cursor = conn.execute(
                """INSERT INTO scripts
                   (tab_name, sheet_row, studio, theme, plot,
                    wardrobe_f, wardrobe_m, location, props, synced_at)
                   VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    body.tab_name,
                    body.sheet_row,
                    body.theme,
                    body.plot,
                    body.wardrobe_f,
                    body.wardrobe_m,
                    body.shoot_location,
                    body.props,
                    now,
                ),
            )
            script_id = cursor.lastrowid

    # Link this save back to the originating /generate call so we can later
    # diff raw model output against the edited final version. Editor may have
    # tweaked anything between the model's stream output and what they hit
    # Save on — that diff is the highest-signal training data we get.
    if body.generation_id:
        _link_generation_to_save(body.generation_id, script_id, body)

    # Fire-and-forget Sheets write
    threading.Thread(
        target=_write_script_to_sheet,
        args=(body,),
        daemon=True,
    ).start()

    return {"id": script_id, "status": "saved"}


def _link_generation_to_save(gen_id: int, script_id: int, body: ScriptSaveBody) -> None:
    """Attach a saved script to its source generation, capturing the post-edit
    version. status is 'edited' when the saved plot differs meaningfully from
    raw_output, else 'approved-asis'."""
    edited_to = json.dumps({
        "theme":       body.theme,
        "plot":        body.plot,
        "wardrobe_f":  body.wardrobe_f,
        "wardrobe_m":  body.wardrobe_m,
        "location":    body.shoot_location,
        "props":       body.props,
    })
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT raw_output FROM script_generations WHERE id=?", (gen_id,)
            ).fetchone()
            if not row:
                _log.warning("save linked to unknown generation_id=%d", gen_id)
                return
            raw = (dict(row).get("raw_output") or "").strip()
            # Heuristic: if the saved plot text appears verbatim in raw_output,
            # the editor approved without changes. Anything else is 'edited'.
            new_status = "approved-asis" if (body.plot.strip() and body.plot.strip() in raw) else "edited"
            conn.execute(
                """UPDATE script_generations
                   SET status=?, edited_to=?, script_id=?
                   WHERE id=?""",
                (new_status, edited_to, script_id, gen_id),
            )
    except Exception as exc:
        _log.warning("Failed to link generation %d to script %d: %s", gen_id, script_id, exc)


# ---------------------------------------------------------------------------
# Script validation
# ---------------------------------------------------------------------------

BANNED_WORDS = {"alcohol", "drunk", "choking", "choke", "drug", "incest", "underage", "minor", "sleep", "unconscious"}


class ValidateBody(BaseModel):
    theme: str = ""
    plot: str = ""
    wardrobe_f: str = ""
    wardrobe_m: str = ""
    shoot_location: str = ""
    female: str = ""
    male: str = ""


@router.post("/validate")
async def validate_script(body: ValidateBody, user: CurrentUser):
    """Check a script for rule violations."""
    violations: list[str] = []

    if not body.theme.strip():
        violations.append("Missing required section: THEME")
    if not body.plot.strip():
        violations.append("Missing required section: PLOT")
    if not body.shoot_location.strip():
        violations.append("Missing required section: SHOOT LOCATION")
    if not body.wardrobe_f.strip():
        violations.append("Missing required section: WARDROBE - FEMALE")

    # Check for banned content
    all_text = f"{body.plot} {body.theme} {body.shoot_location}".lower()
    for word in BANNED_WORDS:
        if word in all_text:
            violations.append(f"Banned content: '{word}' found in script")

    # Male talent name should not appear as a character in the plot
    if body.male and body.male != "POV":
        first_name = body.male.split()[0].lower()
        if first_name in body.plot.lower():
            violations.append(f"Male talent first name '{first_name}' appears in plot — should use 'you' instead")

    # Slop phrase detection — mirrors the Streamlit substitution list so
    # editors can see exactly which lines the save-time filter will rewrite.
    try:
        from api.slop_filter import find_slop
        violations.extend(find_slop(body.plot))
        violations.extend(find_slop(body.theme))
    except Exception:
        # Non-fatal — slop list is a nice-to-have, not a save-gate.
        pass

    return {"violations": violations, "passed": len(violations) == 0}


# ---------------------------------------------------------------------------
# Script title generation
# ---------------------------------------------------------------------------

class TitleGenBody(BaseModel):
    studio: str
    female: str = ""
    male: str = ""
    theme: str = ""
    plot: str = ""
    wardrobe_f: str = ""
    wardrobe_m: str = ""
    location: str = ""
    props: str = ""


@router.post("/title-generate")
async def generate_script_title(body: TitleGenBody, user: CurrentUser):
    """Generate an AI title for a script (Claude with Ollama fallback).

    Caller-supplied body fields (the in-progress script editor's unsaved state)
    win over the DB; any empty fields are filled from the latest matching
    scripts-table row so titles still hook into concrete plot details when the
    UI hands us a sparse body.
    """
    with get_db() as conn:
        merged = enrich_from_script_row(
            conn,
            studio=body.studio,
            female=body.female,
            overrides={
                "theme":      body.theme,
                "plot":       body.plot,
                "wardrobe_f": body.wardrobe_f,
                "wardrobe_m": body.wardrobe_m,
                "location":   body.location,
                "props":      body.props,
                "male":       body.male,
            },
        )

    # If the Scripts Sheet already has a title for this row, return it directly
    # — writers' titles are the source of truth, and AI-regenerating discards
    # their work. Caller's body.theme/plot/etc don't override the sheet title;
    # the sheet wins because that's where titles are authored.
    sheet_title = (merged.get("title") or "").strip()
    if sheet_title:
        return {"title": sheet_title, "source": "script_sheet"}

    try:
        from api.prompts import generate_title_with_fallback
        title = generate_title_with_fallback(
            body.studio, body.female, merged["theme"], merged["plot"],
            male=merged["male"],
            wardrobe_f=merged["wardrobe_f"],
            wardrobe_m=merged["wardrobe_m"],
            location=merged["location"],
            props=merged["props"],
        )
        return {"title": title, "source": "ai"}
    except RuntimeError as exc:
        _log.error("Script title generation failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Title generation failed: {exc}")


# ---------------------------------------------------------------------------
# Sheets write helper
# ---------------------------------------------------------------------------

def _write_script_to_sheet(body: ScriptSaveBody) -> None:
    """Write script fields back to the correct row in the Scripts sheet."""
    try:
        sh = open_scripts()
        ws = sh.worksheet(body.tab_name)

        row_num = body.sheet_row

        # Column indices (1-based for gspread update_cell):
        # G=7=Theme, H=8=WardrobeF, I=9=WardrobeM, J=10=Plot, L=12=Props
        updates = [
            (7, body.theme),
            (8, body.wardrobe_f),
            (9, body.wardrobe_m),
            (10, body.plot),
            (12, body.props),
        ]
        for col, value in updates:
            if value:
                with_retry(lambda c=col, v=value: ws.update_cell(row_num, c, v))

    except Exception as exc:
        _log.error("Failed to write script to Sheets: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_script(row: dict) -> ScriptResponse:
    return ScriptResponse(
        id=row["id"],
        tab_name=row.get("tab_name", ""),
        sheet_row=row.get("sheet_row", 0),
        studio=row.get("studio", ""),
        shoot_date=row.get("shoot_date", ""),
        location=row.get("location", ""),
        scene_type=row.get("scene_type", ""),
        female=row.get("female", ""),
        male=row.get("male", ""),
        theme=row.get("theme", ""),
        wardrobe_f=row.get("wardrobe_f", ""),
        wardrobe_m=row.get("wardrobe_m", ""),
        plot=row.get("plot", ""),
        title=row.get("title", ""),
        props=row.get("props", ""),
        script_status=row.get("script_status", ""),
    )
