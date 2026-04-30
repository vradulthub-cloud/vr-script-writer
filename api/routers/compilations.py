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

import hashlib
import json
import logging
import re
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import CurrentUser, require_grail_writer
from api.config import get_settings
from api.database import get_db
from api.prompts import COMP_IDEAS_SYSTEM, DESC_COMPILATION_SYSTEMS, STUDIO_KEY_MAP, get_prompt
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


# Per-studio locks for ID allocation + multi-row writes. The save and PATCH
# paths each do read-modify-write cycles against a shared sheet; without
# serializing per studio, two concurrent saves can claim the same comp_id and
# both write blocks. FastAPI runs sync routes in threads, so a stdlib Lock is
# enough — we do not span processes.
_STUDIO_LOCKS: dict[str, threading.Lock] = defaultdict(threading.Lock)


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

    system_prompt = get_prompt("comp_ideas.system", fallback=COMP_IDEAS_SYSTEM)

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
                max_tokens=1536, temperature=0.8,
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

    system_prompt = get_prompt(f"desc_comp.{studio_key}", fallback=DESC_COMPILATION_SYSTEMS.get(studio_key, ""))
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
    """Write a v3 comp block to the studio's Index worksheet.

    Holds the studio lock across the read-modify-write cycle so two concurrent
    saves can't claim the same comp_id. The MEGA link loop happens before the
    lock — it's the slow part and is pure work on the body, no shared state.
    """
    try:
        from api.sheets_client import with_retry

        studio_key = STUDIO_KEY_MAP.get(body.studio, "")
        if not studio_key:
            _log.warning("Unknown studio on save: %s", body.studio)
            return

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

        # Generate MEGA links per scene (slow — shells to MEGAcmd). Done
        # OUTSIDE the studio lock; this is pure read work on the body and
        # the lock should only span shared-state mutation.
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

        # ID allocation + write must be atomic per studio. Without the lock,
        # two concurrent saves both read max(B)=N and both append a row at
        # comp_id N+1.
        with _STUDIO_LOCKS[studio_key]:
            ws = _open_index_ws(studio_key)
            comp_id = _next_comp_id(ws, studio_key)

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

            # Find append position via col B length (cheap) instead of
            # get_all_values (entire tab, expensive).
            col_b = with_retry(lambda: ws.col_values(2))
            start_idx = len(col_b)  # 0-indexed row where this block starts

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
# Inline edit — title / volume / status / description on an existing block
# ---------------------------------------------------------------------------

class CompIfMatch(BaseModel):
    """Pre-edit snapshot the client saw. Server compares before write to
    reject silent overwrites when two users edit the same comp."""
    title: str
    volume: str = ""
    status: str = ""
    description: str = ""


class CompPatchBody(BaseModel):
    title: Optional[str] = None
    volume: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    if_match: Optional[CompIfMatch] = None


def _comp_etag(title: str, volume: str, status: str, description: str) -> str:
    """Stable hash of the user-editable fields. Order/format must match what
    list_existing_comps returns so a freshly-loaded client agrees with the
    server on the etag."""
    payload = f"{title}␟{volume}␟{status}␟{description}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Scene-list edit — replace the scene rows of an existing block (TKT-0147)
# ---------------------------------------------------------------------------

class CompScenesPatchBody(BaseModel):
    """Replacement scene list for an existing v3 comp block.

    `scene_ids` is the new ordered list. The block is rewritten in place:
    rows are inserted/deleted as needed; subsequent comp blocks shift up or
    down to fit. The meta row's "{n} scenes" tally is recalculated.
    """
    scene_ids: list[str]


@router.patch("/{comp_id}/scenes")
async def patch_existing_comp_scenes(
    comp_id: str, body: CompScenesPatchBody, user: CurrentUser,
):
    """Replace the scene list of an existing v3 block.

    Locates the block by col B == comp_id, computes the existing scene-row
    span, and rewrites it with the new ordered list. If the count changed,
    extra rows are deleted or inserted so subsequent comps shift cleanly;
    formatting is re-applied to the new block extent.
    """
    from api.sheets_client import with_retry

    m = re.match(r"^([A-Z]+)-C\d{4}$", comp_id)
    if not m:
        raise HTTPException(status_code=400, detail=f"Invalid comp_id: {comp_id}")
    key = m.group(1)
    if key not in STUDIO_ACCENTS:
        raise HTTPException(status_code=400, detail=f"Unknown studio key: {key}")

    new_scene_ids = [sid.strip() for sid in body.scene_ids if sid and sid.strip()]
    if not new_scene_ids:
        raise HTTPException(status_code=400, detail="scene_ids cannot be empty")
    if len(new_scene_ids) != len(set(new_scene_ids)):
        raise HTTPException(status_code=400, detail="scene_ids must be unique")

    # Pull title/performers metadata for the new scene list (DB read, no lock).
    with get_db() as conn:
        placeholders = ", ".join("?" * len(new_scene_ids))
        rows = conn.execute(
            f"SELECT id, title, performers FROM scenes WHERE id IN ({placeholders})",
            new_scene_ids,
        ).fetchall()
        scene_meta = {dict(r)["id"]: dict(r) for r in rows}

    new_scene_rows_data = []
    for i, sid in enumerate(new_scene_ids, start=1):
        meta = scene_meta.get(sid, {})
        new_scene_rows_data.append({
            "num": i,
            "scene_id": sid,
            "title": meta.get("title", ""),
            "performers": meta.get("performers", ""),
            "mega_url": _mega_link_for(sid),
        })
    new_n = len(new_scene_rows_data)

    # The whole rewrite is held under the studio lock so a save / metadata
    # patch can't shift our row indices mid-way.
    with _STUDIO_LOCKS[key]:
        try:
            ws = _open_index_ws(key)
            col_b = with_retry(lambda: ws.col_values(2))
        except Exception as exc:
            _log.error("Could not open Index for %s: %s", key, exc)
            raise HTTPException(status_code=502, detail="Sheet read failed") from exc

        # Locate title row
        title_row_idx: Optional[int] = None
        for i, cell in enumerate(col_b):
            if cell.strip() == comp_id:
                title_row_idx = i
                break
        if title_row_idx is None:
            raise HTTPException(status_code=404, detail=f"Comp not found: {comp_id}")

        # Walk forward from first_scene to count existing scene rows. A scene
        # row's col B is a digit; any other value (empty=spacer, next comp_id)
        # ends the block.
        first_scene_idx = title_row_idx + 3
        old_n = 0
        i = first_scene_idx
        while i < len(col_b):
            v = col_b[i].strip()
            if v.isdigit():
                old_n += 1
                i += 1
            else:
                break

        if old_n == 0:
            raise HTTPException(
                status_code=409,
                detail=f"No scene rows found under {comp_id} — block may be malformed",
            )

        # Read the meta row so we can update the "{n} scenes" tally without
        # losing the description suffix or created-by fragment.
        meta_row_n = title_row_idx + 2  # 1-indexed
        try:
            meta_window = with_retry(lambda: ws.get(f"D{meta_row_n}"))
        except Exception as exc:
            _log.error("Could not read meta row for %s: %s", comp_id, exc)
            raise HTTPException(status_code=502, detail="Sheet read failed") from exc
        cur_meta = (list(meta_window) + [[""]])[0]
        cur_meta_text = (list(cur_meta) + [""])[0]
        head, _, desc_tail = cur_meta_text.partition("\n")
        # Replace the "N scene[s]" fragment in the head while preserving
        # "Created date by user" prefix.
        new_head = re.sub(
            r"(\d+)\s+scenes?",
            f"{new_n} scene{'s' if new_n != 1 else ''}",
            head,
            count=1,
        )
        if new_head == head and "scene" not in head:
            # Older blocks without a scene tally — append one.
            new_head = f"{head.rstrip()}  ·  {new_n} scene{'s' if new_n != 1 else ''}"
        new_meta_text = f"{new_head}\n{desc_tail}".rstrip("\n") if desc_tail else new_head

        # Build new scene block rows (8 cols A-H) — same shape as save().
        new_scene_block: list[list] = []
        for sd in new_scene_rows_data:
            new_scene_block.append([
                "", str(sd["num"]), sd["scene_id"], sd["title"],
                sd["performers"], sd["mega_url"], "", "",
            ])

        # ── Apply ────────────────────────────────────────────────────────────
        # 1) Update the meta row's tally + description.
        # 2) Resize the scene-row span to new_n (delete extra / insert new).
        # 3) Write the scene-row values.
        # 4) Re-apply v3 formatting over [title_idx, spacer_idx].
        first_scene_n = first_scene_idx + 1  # gspread is 1-indexed
        try:
            with_retry(lambda: ws.update(
                f"D{meta_row_n}",
                [[new_meta_text]],
                value_input_option="USER_ENTERED",
            ))
            if new_n < old_n:
                # Shrink — delete the extras (gspread delete_rows is 1-indexed,
                # inclusive at both ends).
                drop_from = first_scene_n + new_n
                drop_to = first_scene_n + old_n - 1
                with_retry(lambda: ws.delete_rows(drop_from, drop_to))
            elif new_n > old_n:
                # Grow — insert blanks; we'll fill via update next.
                blank_rows = [["", "", "", "", "", "", "", ""]] * (new_n - old_n)
                # insert_rows(values, row=N) inserts BEFORE row N. We want to
                # insert directly after the last existing scene row, i.e. at
                # row first_scene_n + old_n.
                insert_at = first_scene_n + old_n
                with_retry(lambda: ws.insert_rows(blank_rows, row=insert_at))
            # Now write all new_n scene values in the now-correctly-sized span.
            with_retry(lambda: ws.update(
                f"A{first_scene_n}:H{first_scene_n + new_n - 1}",
                new_scene_block,
                value_input_option="USER_ENTERED",
            ))
            # Re-apply v3 formatting over the title-thru-spacer band.
            current_status = "Draft"
            try:
                # Cheap re-read of the title row's E cell to recover status.
                row_e = with_retry(lambda: ws.get(f"E{title_row_idx + 1}"))
                cur_e = (list(row_e) + [[""]])[0]
                cur_e_text = (list(cur_e) + [""])[0].strip()
                _, current_status = _parse_vol_status(cur_e_text)
            except Exception:
                pass
            _format_comp_block(ws, key, current_status or "Draft", title_row_idx, new_n)
        except Exception as exc:
            _log.error("Failed to patch scene list for %s: %s", comp_id, exc, exc_info=True)
            raise HTTPException(status_code=502, detail="Sheet write failed") from exc

    _log.info("Patched scene list for %s by %s — old=%d new=%d", comp_id, user.email, old_n, new_n)
    return {
        "status": "ok",
        "comp_id": comp_id,
        "scene_count": new_n,
        "scene_ids": new_scene_ids,
    }


@router.patch("/{comp_id}")
async def patch_existing_comp(comp_id: str, body: CompPatchBody, user: CurrentUser):
    """Update title / volume / status / description on an existing v3 block.

    Locates the block by scanning col B (cheap) instead of the whole tab,
    reads only the two affected rows, then rewrites cols D/E in place.
    Optimistic-locking: if `if_match` is supplied and any field has changed
    on the server since the client loaded it, returns 409 with the latest
    snapshot so the client can show a conflict UI.
    """
    from api.sheets_client import with_retry

    m = re.match(r"^([A-Z]+)-C\d{4}$", comp_id)
    if not m:
        raise HTTPException(status_code=400, detail=f"Invalid comp_id: {comp_id}")
    key = m.group(1)
    if key not in STUDIO_ACCENTS:
        raise HTTPException(status_code=400, detail=f"Unknown studio key: {key}")

    # Hold the studio lock across the read-modify-write so a save of a new
    # comp can't insert a row mid-PATCH and shift our index.
    with _STUDIO_LOCKS[key]:
        try:
            ws = _open_index_ws(key)
            col_b = with_retry(lambda: ws.col_values(2))
        except Exception as exc:
            _log.error("Could not open Index for %s: %s", key, exc)
            raise HTTPException(status_code=502, detail="Sheet read failed") from exc

        title_row_idx: Optional[int] = None  # 0-indexed
        for i, cell in enumerate(col_b):
            if cell.strip() == comp_id:
                title_row_idx = i
                break
        if title_row_idx is None:
            raise HTTPException(status_code=404, detail=f"Comp not found: {comp_id}")

        title_row_n = title_row_idx + 1   # gspread is 1-indexed
        meta_row_n = title_row_idx + 2

        # Read only the two rows we touch — D:E of the title row, D of the meta row.
        try:
            window = with_retry(lambda: ws.get(f"D{title_row_n}:E{meta_row_n}"))
        except Exception as exc:
            _log.error("Could not read rows for %s: %s", comp_id, exc)
            raise HTTPException(status_code=502, detail="Sheet read failed") from exc

        window = (list(window) + [[""], [""]])[:2]
        title_window = (list(window[0]) + ["", ""])[:2]
        meta_window = (list(window[1]) + ["", ""])[:2]

        cur_title = title_window[0].strip()
        cur_vol, cur_status = _parse_vol_status(title_window[1].strip())
        cur_meta = meta_window[0]
        cur_meta_head = cur_meta
        cur_desc = ""
        if "\n" in cur_meta:
            cur_meta_head, cur_desc = cur_meta.split("\n", 1)
            cur_desc = cur_desc.strip()

        # Optimistic check — if the client's snapshot doesn't match what's on
        # the sheet now, surface the conflict instead of clobbering.
        if body.if_match is not None:
            client_tag = _comp_etag(
                body.if_match.title,
                body.if_match.volume,
                body.if_match.status or "Draft",
                body.if_match.description,
            )
            server_tag = _comp_etag(cur_title, cur_vol, cur_status or "Draft", cur_desc)
            if client_tag != server_tag:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Compilation was modified by someone else.",
                        "current": {
                            "title": cur_title,
                            "volume": cur_vol,
                            "status": cur_status,
                            "description": cur_desc,
                        },
                    },
                )

        new_title = body.title.strip() if body.title is not None else cur_title
        new_vol = body.volume.strip() if body.volume is not None else cur_vol
        new_status = body.status.strip() if body.status is not None else cur_status
        new_desc = body.description if body.description is not None else cur_desc

        if new_status and new_status not in STATUS_COLORS:
            raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

        new_vol_status = f"{new_vol}  ·  {new_status}" if new_vol else (new_status or "")
        new_meta = f"{cur_meta_head}\n{new_desc}".rstrip() if new_desc else cur_meta_head

        try:
            with_retry(lambda: ws.update(
                f"D{title_row_n}:E{title_row_n}",
                [[new_title, new_vol_status]],
                value_input_option="USER_ENTERED",
            ))
            with_retry(lambda: ws.update(
                f"D{meta_row_n}",
                [[new_meta]],
                value_input_option="USER_ENTERED",
            ))
        except Exception as exc:
            _log.error("Failed to patch %s: %s", comp_id, exc, exc_info=True)
            raise HTTPException(status_code=502, detail="Sheet write failed") from exc

    _log.info("Patched comp %s by %s", comp_id, user.email)
    return {
        "status": "ok",
        "comp_id": comp_id,
        "title": new_title,
        "volume": new_vol,
        "comp_status": new_status,
        "description": new_desc,
    }


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
