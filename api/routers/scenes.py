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
import re
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel, Field

from api.auth import CurrentUser, require_grail_writer
from api.database import get_db
from api.sheets_client import open_grail, with_retry

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenes", tags=["scenes"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SceneResponse(BaseModel):
    id: str
    studio: str
    grail_tab: str = ""
    site_code: str = ""
    title: str = ""
    performers: str = ""
    categories: str = ""
    tags: str = ""
    release_date: str = ""
    female: str = ""
    male: str = ""
    plot: str = ""
    theme: str = ""
    is_compilation: bool = False
    has_description: bool = False
    has_videos: bool = False
    video_count: int = 0
    has_thumbnail: bool = False
    has_photos: bool = False
    has_storyboard: bool = False
    storyboard_count: int = 0
    mega_path: str = ""
    grail_row: int = 0


class SceneFieldUpdate(BaseModel):
    value: str = Field(..., min_length=0)


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
    """Get scene counts by studio and overall completion percentage.

    Reads the pre-aggregated scene_stats_cache table. The cache is refreshed
    once per sync (≤300s old) by sync_engine._refresh_scene_stats_cache, so
    this endpoint runs O(studios) rows instead of three full table scans on
    every dashboard load. Falls back to live aggregation if the cache table
    is empty (first boot before the first sync completes).
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT studio, scene_count, complete_count FROM scene_stats_cache"
        ).fetchall()

        if rows:
            by_studio: dict[str, int] = {}
            total = 0
            complete = 0
            for r in rows:
                d = dict(r)
                if d["studio"] == "TOTAL":
                    total = d["scene_count"]
                    complete = d["complete_count"]
                else:
                    by_studio[d["studio"]] = d["scene_count"]
            return SceneStats(
                total=total,
                by_studio=by_studio,
                complete=complete,
                missing_any=total - complete,
            )

        # Cold path — first run before sync_scenes has populated the cache.
        total_row = conn.execute("SELECT COUNT(*) as cnt FROM scenes").fetchone()
        total = dict(total_row)["cnt"]
        studio_rows = conn.execute(
            "SELECT studio, COUNT(*) as cnt FROM scenes GROUP BY studio"
        ).fetchall()
        by_studio = {dict(r)["studio"]: dict(r)["cnt"] for r in studio_rows}
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


@router.get("/recent", response_model=list[SceneResponse])
async def list_recent_scenes(
    user: CurrentUser,
    studios: str = Query(default="FuckPassVR,VRHush,VRAllure"),
    per_studio: int = Query(default=5, ge=1, le=50),
    missing_only: bool = True,
):
    """
    Return the N most recent scenes for each requested studio in one call.

    Replaces the dashboard's three-fetch fan-out (one round-trip per studio)
    with a single backend call. The same per-studio cap is enforced server-side
    via UNION ALL of LIMITed sub-selects so a studio with heavier recent
    activity can't crowd others out.
    """
    studio_list = [s.strip() for s in studios.split(",") if s.strip()]
    if not studio_list:
        return []

    missing_clause = (
        " AND (has_description=0 OR has_videos=0"
        " OR has_thumbnail=0 OR has_photos=0 OR has_storyboard=0)"
        if missing_only else ""
    )

    sub_selects: list[str] = []
    params: list = []
    for studio in studio_list:
        sub_selects.append(
            f"SELECT * FROM scenes WHERE studio = ?{missing_clause}"
            f" ORDER BY id DESC LIMIT ?"
        )
        params.extend([studio, per_studio])

    query = " UNION ALL ".join(sub_selects)

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_scene(dict(r)) for r in rows]


@router.get("/{scene_id}/thumbnail")
async def get_scene_thumbnail(scene_id: str):
    """
    Serve a scene's Video Thumbnail image.

    Public endpoint (no auth) — used as <img src> in the Asset Tracker.
    Downloads from MEGA S4 once, caches on local disk, serves bytes to client.
    """
    from pathlib import Path as _Path
    import s4_client
    from botocore.exceptions import ClientError, BotoCoreError
    from api.config import get_settings

    # 1. Look up the scene in the DB
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, grail_tab, thumb_file, has_thumbnail FROM scenes WHERE id = ?",
            (scene_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Scene not found")
    if not row["has_thumbnail"] or not row["thumb_file"]:
        raise HTTPException(status_code=404, detail="No thumbnail for this scene")

    # 2. Check local cache
    settings = get_settings()
    cache_dir = settings.base_dir / "thumb_cache"
    cache_dir.mkdir(exist_ok=True)
    ext = _Path(row["thumb_file"]).suffix.lower() or ".jpg"
    cache_path = cache_dir / f"{scene_id}{ext}"

    if not cache_path.exists():
        # 3. Download from MEGA S4. resolve_key() handles the 23 VRH scenes
        # whose prefixes were migrated as lowercase.
        canonical_key = s4_client.key_for(
            scene_id, "Video Thumbnail", row["thumb_file"]
        )
        try:
            actual_key = s4_client.resolve_key(row["grail_tab"], canonical_key)
            if actual_key is None:
                _log.warning("S4 thumbnail not found for %s at %s", scene_id, canonical_key)
                raise HTTPException(status_code=404, detail="Thumbnail not in bucket")
            s4_client.get_object(row["grail_tab"], actual_key, cache_path)
        except HTTPException:
            raise
        except (ClientError, BotoCoreError) as exc:
            _log.warning("S4 fetch failed for %s: %s", scene_id, exc)
            raise HTTPException(status_code=502, detail="Thumbnail fetch failed")
        except RuntimeError as exc:  # missing creds → 503 not 502
            _log.error("S4 client misconfigured: %s", exc)
            raise HTTPException(status_code=503, detail="S4 not configured")

    # 4. Serve from cache
    media = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"
    return FileResponse(
        cache_path,
        media_type=media,
        headers={"Cache-Control": "public, max-age=604800"},  # 7 days
    )


@router.get("/", response_model=list[SceneResponse])
async def list_scenes(
    user: CurrentUser,
    studio: Optional[str] = None,
    missing_only: bool = False,
    missing_descriptions: bool = False,
    search: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=2000),
):
    """
    List scenes with optional filters.

    - studio: filter by studio UI name (e.g. "VRHush")
    - missing_only: only scenes missing at least one core asset
    - missing_descriptions: only scenes that have no description yet
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

    if missing_descriptions:
        query += " AND has_description=0"

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
# Scene field edit endpoints (Grail write-through)
# ---------------------------------------------------------------------------

# Grail column mapping (1-based): Scene#=2, Title=4, Performers=5, Categories=6, Tags=7
GRAIL_COL = {"title": 4, "categories": 6, "tags": 7}


def _write_grail_cell(grail_tab: str, grail_row: int, col: int, value: str) -> None:
    """Write a single cell to the Grail sheet (background thread safe)."""
    try:
        sh = open_grail()
        ws = sh.worksheet(grail_tab)
        with_retry(lambda: ws.update_cell(grail_row, col, value))
        _log.info("Grail write: %s row %d col %d", grail_tab, grail_row, col)
    except Exception:
        _log.exception("Failed to write Grail cell: %s R%dC%d", grail_tab, grail_row, col)


@router.patch("/{scene_id}/title")
async def update_scene_title(scene_id: str, body: SceneFieldUpdate, user: CurrentUser):
    """Update a scene's title in SQLite + Grail sheet. Requires grail-writer permission."""
    if user["name"] not in {"Drew", "David", "Duc"}:
        raise HTTPException(status_code=403, detail="Grail write access required")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scene not found")
        scene = dict(row)
        conn.execute("UPDATE scenes SET title = ? WHERE id = ?", (body.value, scene_id))

    threading.Thread(
        target=_write_grail_cell,
        args=(scene["grail_tab"], scene["grail_row"], GRAIL_COL["title"], body.value),
        daemon=True,
    ).start()

    return {"ok": True, "field": "title", "value": body.value}


@router.patch("/{scene_id}/categories")
async def update_scene_categories(scene_id: str, body: SceneFieldUpdate, user: CurrentUser):
    """Update a scene's categories in SQLite + Grail sheet."""
    if user["name"] not in {"Drew", "David", "Duc"}:
        raise HTTPException(status_code=403, detail="Grail write access required")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scene not found")
        scene = dict(row)
        conn.execute("UPDATE scenes SET categories = ? WHERE id = ?", (body.value, scene_id))

    threading.Thread(
        target=_write_grail_cell,
        args=(scene["grail_tab"], scene["grail_row"], GRAIL_COL["categories"], body.value),
        daemon=True,
    ).start()

    return {"ok": True, "field": "categories", "value": body.value}


@router.patch("/{scene_id}/tags")
async def update_scene_tags(scene_id: str, body: SceneFieldUpdate, user: CurrentUser):
    """Update a scene's tags in SQLite + Grail sheet."""
    if user["name"] not in {"Drew", "David", "Duc"}:
        raise HTTPException(status_code=403, detail="Grail write access required")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scene not found")
        scene = dict(row)
        conn.execute("UPDATE scenes SET tags = ? WHERE id = ?", (body.value, scene_id))

    threading.Thread(
        target=_write_grail_cell,
        args=(scene["grail_tab"], scene["grail_row"], GRAIL_COL["tags"], body.value),
        daemon=True,
    ).start()

    return {"ok": True, "field": "tags", "value": body.value}


# ---------------------------------------------------------------------------
# AI title generation
# ---------------------------------------------------------------------------

class TitleGenerateBody(BaseModel):
    female: str = ""
    male: str = ""
    theme: str = ""
    plot: str = ""
    wardrobe_f: str = ""
    wardrobe_m: str = ""
    location: str = ""
    props: str = ""


@router.post("/{scene_id}/generate-title")
async def generate_scene_title(scene_id: str, body: TitleGenerateBody, user: CurrentUser):
    """Generate an AI title suggestion for a scene (Claude with Ollama fallback).

    The scenes row is often sparse for pre-production scenes — only
    `performers` is populated, while theme/plot/wardrobe live in the scripts
    sheet until the Grail row is filled in. We therefore:

      1. Start from the scenes row (and any client-sent overrides).
      2. If `female` is missing, parse it from `performers` (first comma part).
      3. If theme/plot are still empty, look up the matching scripts row
         (studio + case-insensitive female name, newest tab first) and pull
         theme/plot/wardrobe/location/props from there.

    Without step 3, Claude receives an empty user prompt and replies
    "I don't see a script provided" — the bug this endpoint was hitting on
    pre-Grail scenes (e.g. VRH0764 for Harley Love).
    """
    with get_db() as conn:
        row = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scene not found")
        scene = dict(row)

        studio     = scene.get("studio", "VRHush")
        female     = body.female     or scene.get("female", "")     or ""
        male       = body.male       or scene.get("male", "")       or ""
        theme      = body.theme      or scene.get("theme", "")      or ""
        plot       = body.plot       or scene.get("plot", "")       or ""
        wardrobe_f = body.wardrobe_f or scene.get("wardrobe_f", "") or ""
        wardrobe_m = body.wardrobe_m or scene.get("wardrobe_m", "") or ""
        location   = body.location   or ""
        props      = body.props      or ""

        # Derive female from `performers` when the scene row hasn't been
        # flattened. Scenes sync populates performers ("Female, Male") before
        # the dedicated columns on fresh rows.
        if not female and scene.get("performers"):
            female = scene["performers"].split(",")[0].strip()

        # If the scenes row lacks theme/plot, fetch the matching script row.
        # This is the load-bearing path for pre-Grail scenes — without it,
        # Claude gets an empty prompt and refuses.
        if (not theme or not plot) and female:
            srow = conn.execute(
                "SELECT theme, plot, wardrobe_f, wardrobe_m, location, props, male "
                "FROM scripts "
                "WHERE studio = ? AND LOWER(female) = LOWER(?) "
                "ORDER BY tab_name DESC LIMIT 1",
                (studio, female),
            ).fetchone()
            if srow:
                s = dict(srow)
                theme      = theme      or (s.get("theme")      or "")
                plot       = plot       or (s.get("plot")       or "")
                wardrobe_f = wardrobe_f or (s.get("wardrobe_f") or "")
                wardrobe_m = wardrobe_m or (s.get("wardrobe_m") or "")
                location   = location   or (s.get("location")   or "")
                props      = props      or (s.get("props")      or "")
                male       = male       or (s.get("male")       or "")
                _log.info("generate-title %s: enriched from scripts row (female=%s)", scene_id, female)
            else:
                _log.warning("generate-title %s: no scripts match for female=%r studio=%s", scene_id, female, studio)

    try:
        from api.prompts import generate_title_with_fallback
        title = generate_title_with_fallback(
            studio, female, theme, plot,
            male=male,
            wardrobe_f=wardrobe_f,
            wardrobe_m=wardrobe_m,
            location=location,
            props=props,
        )
        return {"title": title}
    except RuntimeError as exc:
        _log.error("Title generation failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Title generation failed: {exc}")


# ---------------------------------------------------------------------------
# Script lookup for description generator
# ---------------------------------------------------------------------------

@router.get("/{scene_id}/script")
async def get_scene_script(scene_id: str, user: CurrentUser):
    """
    Return the Scripts Sheet data for the scene's primary female performer.

    Used by the description generator to pre-fill plot, theme, wardrobe, and
    scene_type without requiring the user to manually paste them.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT studio, performers FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scene not found")
        scene = dict(row)
        female = (scene.get("performers") or "").split(",")[0].strip()
        if not female:
            return {"plot": "", "theme": "", "wardrobe_f": "", "wardrobe_m": "", "scene_type": ""}
        srow = conn.execute(
            "SELECT theme, plot, wardrobe_f, wardrobe_m, scene_type "
            "FROM scripts "
            "WHERE studio = ? AND LOWER(female) = LOWER(?) "
            "ORDER BY tab_name DESC LIMIT 1",
            (scene["studio"], female),
        ).fetchone()
        if not srow:
            return {"plot": "", "theme": "", "wardrobe_f": "", "wardrobe_m": "", "scene_type": ""}
        s = dict(srow)
        return {
            "plot": s.get("plot") or "",
            "theme": s.get("theme") or "",
            "wardrobe_f": s.get("wardrobe_f") or "",
            "wardrobe_m": s.get("wardrobe_m") or "",
            "scene_type": s.get("scene_type") or "",
        }


# ---------------------------------------------------------------------------
# Naming validation
# ---------------------------------------------------------------------------

# Expected prefixes by studio
_STUDIO_PREFIXES = {
    "FuckPassVR": "FPVR", "VRHush": "VRH", "VRAllure": "VRA", "NaughtyJOI": "NNJOI",
}


@router.get("/{scene_id}/naming-issues")
async def naming_issues(scene_id: str, user: CurrentUser):
    """Check file naming conventions for a scene's MEGA assets."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scene not found")
        scene = dict(row)

    issues: list[dict] = []
    prefix = _STUDIO_PREFIXES.get(scene["studio"], scene["id"][:3].upper())
    expected_folder = scene["id"]  # e.g., "FPVR0042"

    # Check folder name pattern
    if not re.match(rf"^{prefix}\d{{4}}$", scene["id"]):
        issues.append({"type": "folder", "file": scene["id"], "issue": f"ID should match {prefix}XXXX pattern"})

    # Check mega_path exists
    if not scene.get("mega_path"):
        issues.append({"type": "folder", "file": scene["id"], "issue": "No MEGA folder found"})

    return {"scene_id": scene_id, "issues": issues, "ok": len(issues) == 0}


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
        grail_tab=row.get("grail_tab", ""),
        site_code=row.get("site_code", ""),
        title=row.get("title", ""),
        performers=row.get("performers", ""),
        categories=row.get("categories", ""),
        tags=row.get("tags", ""),
        release_date=row.get("release_date", ""),
        female=row.get("female", ""),
        male=row.get("male", ""),
        plot=row.get("plot", ""),
        theme=row.get("theme", ""),
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
