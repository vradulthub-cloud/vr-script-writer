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
# v3 block-per-comp Index tab schema.
#
# Each compilation is a visual block of rows:
#   1. Title row  — col B: comp_id, col D: title, col E: "Vol. X · STATUS"
#   2. Meta row   — col D: "Created {date} by {user} · {N} scenes\n{description}"
#   3. Sub-header — col B: "#", C: "SCENE ID", D: "SCENE TITLE", …
#   4+. Scene rows — col B: scene_num, C: scene_id, D: title, E: performers,
#                    F: mega_link, G: slr_link
#   N. Spacer row  — empty, 28px tall
#
# Parsing: scan col B for STUDIO-CNNNN pattern → title row starts a new block.
# ---------------------------------------------------------------------------
INDEX_TAB_SUFFIX = " Index"

# Studio accent colors (r/g/b, 0-1 scale)
STUDIO_ACCENTS: dict[str, tuple[float, float, float]] = {
    "FPVR": (0.231, 0.510, 0.965),
    "VRH":  (0.545, 0.361, 0.965),
    "VRA":  (0.925, 0.282, 0.600),
    "NJOI": (0.976, 0.451, 0.086),
}

# Status colors for the "Vol. X · STATUS" label in the title row
STATUS_COLORS: dict[str, dict] = {
    "Draft":     {"red": 0.60, "green": 0.60, "blue": 0.60},
    "Planned":   {"red": 0.95, "green": 0.77, "blue": 0.25},
    "Published": {"red": 0.30, "green": 0.75, "blue": 0.45},
}


def _rgb(r: float, g: float, b: float) -> dict:
    return {"red": r, "green": g, "blue": b}


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
    """Get-or-create the studio's Index worksheet (no header row — block format)."""
    from api.sheets_client import open_comp_planning, with_retry
    import gspread as _gspread

    sh = open_comp_planning()
    tab_name = _index_tab_name(studio_key)
    try:
        return with_retry(lambda: sh.worksheet(tab_name))
    except _gspread.WorksheetNotFound:
        return with_retry(lambda: sh.add_worksheet(title=tab_name, rows=3000, cols=8))


def _next_comp_id(ws, studio_key: str) -> str:
    """Scan col B (Comp ID in title rows) and return the next sequential ID."""
    from api.sheets_client import with_retry

    col_b = with_retry(lambda: ws.col_values(2))  # col B, 1-indexed
    max_n = 0
    pat = re.compile(rf"^{re.escape(studio_key)}-C(\d+)$")
    for cell in col_b:
        m = pat.match(cell.strip())
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"{studio_key}-C{max_n + 1:04d}"


def _parse_vol_status(raw: str) -> tuple[str, str]:
    """Parse 'Vol. 3  ·  Draft' → ('Vol. 3', 'Draft')."""
    if "·" in raw:
        parts = [p.strip() for p in raw.split("·", 1)]
        return parts[0], parts[1]
    return "", raw.strip()


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
        "act type, era/nostalgic angle, performer archetype, season/holiday, etc.\n\n"
        "Example output (use as format reference only — do not copy):\n"
        "TITLE: Best American Blondes Vol. 1\n"
        "CONCEPT: Sun-kissed US blondes delivering the definitive American VR experience.\n"
        "TALENT: Kenzie Anne, Haley Reed, Alex Blake\n\n"
        "TITLE: Petite Powerhouses\n"
        "CONCEPT: Small frames, maximum intensity — compact performers who command every scene.\n"
        "TALENT: Lulu Chu, Freya Parker, Lily Larimar\n\n"
        "TITLE: European Tour\n"
        "CONCEPT: A passport-stamping best-of from FuckPassVR's European city shoots.\n"
        "TALENT: Anissa Kate, Tina Kay, Rebecca Volpetti"
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
    """Write a v3 comp block to the studio's Index worksheet."""
    try:
        from api.sheets_client import with_retry

        studio_key = STUDIO_KEY_MAP.get(body.studio, "")
        if not studio_key:
            _log.warning("Unknown studio on save: %s", body.studio)
            return

        ws = _open_index_ws(studio_key)
        comp_id = _next_comp_id(ws, studio_key)
        now_dt = datetime.now(timezone.utc)
        date_str = f"{now_dt.day} {now_dt.strftime('%b %Y')}"  # "19 Apr 2026"

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

        # Generate MEGA links per scene (slow — shells to MEGAcmd)
        scene_rows_data: list[dict] = []
        for i, sid in enumerate(body.scene_ids, start=1):
            meta = scene_meta.get(sid, {})
            mega_url = _mega_link_for(sid)
            scene_rows_data.append({
                "num": i,
                "scene_id": sid,
                "title": meta.get("title", ""),
                "performers": meta.get("performers", ""),
                "mega_url": mega_url,
            })

        n_scenes = len(scene_rows_data)
        status = body.status or "Draft"
        vol_status = f"{body.volume}  ·  {status}" if body.volume else status
        meta_parts = [f"Created {date_str} by {created_by}  ·  {n_scenes} scene{'s' if n_scenes != 1 else ''}"]
        if body.description:
            meta_parts.append(body.description)
        meta_text = "\n".join(meta_parts)

        # v3 block rows — 8 columns (A-H)
        block_rows: list[list] = [
            ["", comp_id, "", body.title, vol_status, "", "", ""],     # title row
            ["", "", "", meta_text, "", "", "", ""],                   # meta row
            ["", "#", "SCENE ID", "SCENE TITLE", "PERFORMERS", "MEGA", "SLR", "NOTES"],  # sub-header
        ]
        for sd in scene_rows_data:
            block_rows.append([
                "", str(sd["num"]), sd["scene_id"], sd["title"],
                sd["performers"], sd["mega_url"], "", "",
            ])
        block_rows.append(["", "", "", "", "", "", "", ""])  # spacer

        # Append data then apply formatting
        all_vals = with_retry(lambda: ws.get_all_values())
        start_idx = len(all_vals)  # 0-indexed row where this block starts

        with_retry(lambda: ws.append_rows(block_rows, value_input_option="USER_ENTERED"))
        _format_comp_block(ws, studio_key, status, start_idx, n_scenes)
        _log.info("Wrote comp block %s (%s) — %d scenes", comp_id, studio_key, n_scenes)
    except Exception as exc:
        _log.error("Failed to write comp block to Index tab: %s", exc, exc_info=True)


def _format_comp_block(
    ws,
    studio_key: str,
    status: str,
    start_idx: int,
    n_scenes: int,
) -> None:
    """Apply v3 block formatting to the rows we just appended."""
    from api.sheets_client import with_retry

    sid = ws.id
    at = STUDIO_ACCENTS.get(studio_key, (0.5, 0.5, 0.5))
    accent_rgb = _rgb(*at)
    status_rgb = STATUS_COLORS.get(status, _rgb(0.6, 0.6, 0.6))
    gray = _rgb(0.55, 0.55, 0.55)
    light_gray = _rgb(0.80, 0.80, 0.80)

    title_idx   = start_idx
    meta_idx    = start_idx + 1
    subhdr_idx  = start_idx + 2
    first_scene = start_idx + 3
    spacer_idx  = start_idx + 3 + n_scenes

    requests: list[dict] = []

    # ── Row heights ───────────────────────────────────────────────────────
    heights = [
        (title_idx, 32),
        (meta_idx, 22),
        (subhdr_idx, 18),
        *[(first_scene + i, 22) for i in range(n_scenes)],
        (spacer_idx, 28),
    ]
    for r_idx, px in heights:
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "ROWS",
                          "startIndex": r_idx, "endIndex": r_idx + 1},
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        })

    # ── Col A accent stripe across entire block ───────────────────────────
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": title_idx, "endRowIndex": spacer_idx + 1,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {"backgroundColor": accent_rgb}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # ── Title row ─────────────────────────────────────────────────────────
    # Col B: comp_id — bold, monospace, studio color
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": title_idx, "endRowIndex": title_idx + 1,
                      "startColumnIndex": 1, "endColumnIndex": 2},
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {
                        "bold": True, "fontFamily": "Roboto Mono", "fontSize": 11,
                        "foregroundColorStyle": {"rgbColor": accent_rgb},
                    },
                    "verticalAlignment": "MIDDLE",
                    "padding": {"left": 8, "right": 4, "top": 4, "bottom": 4},
                }
            },
            "fields": "userEnteredFormat(textFormat,verticalAlignment,padding)",
        }
    })
    # Col D: title — bold, 13pt
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": title_idx, "endRowIndex": title_idx + 1,
                      "startColumnIndex": 3, "endColumnIndex": 4},
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {"bold": True, "fontSize": 13},
                    "verticalAlignment": "MIDDLE",
                    "padding": {"left": 8, "right": 4, "top": 4, "bottom": 4},
                }
            },
            "fields": "userEnteredFormat(textFormat,verticalAlignment,padding)",
        }
    })
    # Col E: vol·status — right-aligned, status color, bold
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": title_idx, "endRowIndex": title_idx + 1,
                      "startColumnIndex": 4, "endColumnIndex": 5},
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {
                        "bold": True, "fontSize": 10,
                        "foregroundColorStyle": {"rgbColor": status_rgb},
                    },
                    "horizontalAlignment": "RIGHT",
                    "verticalAlignment": "MIDDLE",
                    "padding": {"left": 4, "right": 10, "top": 4, "bottom": 4},
                }
            },
            "fields": "userEnteredFormat(textFormat,horizontalAlignment,verticalAlignment,padding)",
        }
    })

    # ── Meta row ─────────────────────────────────────────────────────────
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": meta_idx, "endRowIndex": meta_idx + 1,
                      "startColumnIndex": 3, "endColumnIndex": 8},
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {
                        "italic": True, "fontSize": 9,
                        "foregroundColorStyle": {"rgbColor": gray},
                    },
                    "wrapStrategy": "WRAP",
                    "verticalAlignment": "MIDDLE",
                    "padding": {"left": 8, "right": 8, "top": 3, "bottom": 3},
                }
            },
            "fields": "userEnteredFormat(textFormat,wrapStrategy,verticalAlignment,padding)",
        }
    })

    # ── Sub-header row ────────────────────────────────────────────────────
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": subhdr_idx, "endRowIndex": subhdr_idx + 1,
                      "startColumnIndex": 1, "endColumnIndex": 8},
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {
                        "bold": True, "fontSize": 8,
                        "foregroundColorStyle": {"rgbColor": _rgb(0.65, 0.65, 0.65)},
                    },
                    "verticalAlignment": "BOTTOM",
                    "padding": {"left": 8, "right": 4, "top": 2, "bottom": 4},
                    "borders": {
                        "bottom": {
                            "style": "SOLID",
                            "colorStyle": {"rgbColor": light_gray},
                        }
                    },
                }
            },
            "fields": "userEnteredFormat(textFormat,verticalAlignment,padding,borders)",
        }
    })

    # ── Scene rows ────────────────────────────────────────────────────────
    if n_scenes > 0:
        # Col B (scene #): centered, gray, small
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sid,
                          "startRowIndex": first_scene, "endRowIndex": spacer_idx,
                          "startColumnIndex": 1, "endColumnIndex": 2},
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "fontSize": 9,
                            "foregroundColorStyle": {"rgbColor": gray},
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(textFormat,horizontalAlignment,verticalAlignment)",
            }
        })
        # Col C (scene_id): monospace
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sid,
                          "startRowIndex": first_scene, "endRowIndex": spacer_idx,
                          "startColumnIndex": 2, "endColumnIndex": 3},
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"fontFamily": "Roboto Mono", "fontSize": 10},
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(textFormat,verticalAlignment)",
            }
        })
        # Col F (MEGA link): studio accent, bold
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sid,
                          "startRowIndex": first_scene, "endRowIndex": spacer_idx,
                          "startColumnIndex": 5, "endColumnIndex": 6},
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "bold": True, "fontSize": 10,
                            "foregroundColorStyle": {"rgbColor": accent_rgb},
                        },
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(textFormat,verticalAlignment)",
            }
        })
        # Alternating row banding
        for i in range(n_scenes):
            bg = _rgb(1.0, 1.0, 1.0) if i % 2 == 0 else _rgb(0.965, 0.965, 0.965)
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sid,
                              "startRowIndex": first_scene + i, "endRowIndex": first_scene + i + 1,
                              "startColumnIndex": 1, "endColumnIndex": 8},
                    "cell": {"userEnteredFormat": {"backgroundColor": bg}},
                    "fields": "userEnteredFormat.backgroundColor",
                }
            })

    # ── Spacer row: white ─────────────────────────────────────────────────
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": spacer_idx, "endRowIndex": spacer_idx + 1,
                      "startColumnIndex": 1, "endColumnIndex": 8},
            "cell": {"userEnteredFormat": {"backgroundColor": _rgb(1.0, 1.0, 1.0)}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    with_retry(lambda: ws.spreadsheet.batch_update({"requests": requests}))


# ---------------------------------------------------------------------------
# Existing comps — read Index tabs, group by Comp ID
# ---------------------------------------------------------------------------

@router.get("/existing", response_model=list[ExistingComp])
async def list_existing_comps(
    user: CurrentUser,
    studio: Optional[str] = None,
):
    """List existing compilations from the v3 block-format Index tabs.

    Parses by scanning col B for STUDIO-CNNNN patterns (title rows).
    """
    from api.sheets_client import with_retry

    keys = [STUDIO_KEY_MAP.get(studio, studio)] if studio else list(STUDIO_KEY_MAP.values())

    results: list[ExistingComp] = []

    for key in keys:
        try:
            ws = _open_index_ws(key)
            all_rows = with_retry(lambda: ws.get_all_values())
        except Exception as exc:
            _log.warning("Could not read %s Index: %s", key, exc)
            continue

        pat = re.compile(rf"^{re.escape(key)}-C\d{{4}}$")
        current: ExistingComp | None = None

        for row in all_rows:
            # Pad to 8 cols so all index accesses are safe
            r = (list(row) + [""] * 8)[:8]
            col_b = r[1].strip()

            if pat.match(col_b):
                # Title row — flush previous comp, start new one
                if current is not None:
                    current.scene_count = len(current.scenes)
                    results.append(current)
                vol, status = _parse_vol_status(r[4].strip())
                current = ExistingComp(
                    comp_id=col_b,
                    title=r[3].strip(),
                    volume=vol,
                    status=status,
                    studio_key=key,
                    created="",
                    created_by="",
                    updated="",
                    description="",
                    notes="",
                    scene_count=0,
                    scenes=[],
                )

            elif col_b == "" and current is not None:
                # Meta row — col D starts with "Created"
                col_d = r[3].strip()
                if col_d.startswith("Created"):
                    dm = re.match(r"Created (.+?) by (.+?)\s+·", col_d)
                    if dm:
                        current.created = dm.group(1)
                        current.created_by = dm.group(2)
                    if "\n" in col_d:
                        current.description = col_d.split("\n", 1)[1].strip()

            elif col_b.isdigit() and current is not None:
                # Scene row
                current.scenes.append(CompSceneRow(
                    scene_id=r[2].strip(),
                    scene_num=int(col_b),
                    title=r[3].strip(),
                    performers=r[4].strip(),
                    slr_link=r[6].strip(),
                    mega_link=r[5].strip(),
                ))

        # Flush last comp
        if current is not None:
            current.scene_count = len(current.scenes)
            results.append(current)

    for comp in results:
        comp.scenes.sort(key=lambda s: s.scene_num)

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
