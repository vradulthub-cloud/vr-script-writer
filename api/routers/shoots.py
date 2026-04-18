"""
Shoot Board API router.

A "shoot" is one day of production for one pair of talent (female + male),
sourced from the Scripts sheet (mirrored to the `scripts` table). Each shoot
holds 1–3 scenes that map (best-effort) to Grail rows for MEGA asset state.

Routes:
  GET  /api/shoots/                                                  — list shoots in a ±14-day window
  GET  /api/shoots/{shoot_id}                                        — single shoot
  POST /api/shoots/{shoot_id}/scenes/{pos}/assets/{at}/revalidate    — force-refresh one cell

Asset-state inference is best-effort from existing data:
  - script_done         → scripts.plot non-empty
  - bg_edit_uploaded    → scene has videos in MEGA (BG/BGCP only)
  - solo_uploaded       → scene has videos in MEGA (Solo/JOI only)
  - title_done          → scene has_thumbnail
  - photoset_uploaded   → scene has_photos
  - storyboard_uploaded → scene has_storyboard
  - everything else     → not_present (no data source yet; user will wire up)
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.auth import CurrentUser
from api.database import get_db

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shoots", tags=["shoots"])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AssetType = str  # one of the 13 below — kept loose for forward-compat

ASSET_ORDER: list[AssetType] = [
    "script_done", "call_sheet_sent", "legal_run", "grail_run",
    "bg_edit_uploaded", "solo_uploaded",
    "title_done", "encoded_uploaded",
    "photoset_uploaded", "storyboard_uploaded", "legal_docs_uploaded",
]

# Legal run (legal_docs_run.mjs) creates Drive folders named "{MMDDYY}-{Female}-{Male}"
# under a per-month folder, under ROOT_FOLDER.
LEGAL_ROOT_FOLDER = "132MZR2EgBeEEJRmF3OJke5WnZozkv2cJ"
LEGAL_CREDS_PATH = "~/.config/google-legal-docs/credentials.json"

# Map Grail-tab short names ← studio UI name
STUDIO_TO_GRAIL_TAB = {
    "FuckPassVR": "FPVR",
    "VRHush":     "VRH",
    "VRAllure":   "VRA",
    "NaughtyJOI": "NNJOI",
}

SKIP_SCRIPT_ROWS = re.compile(r"^(cancel|note|tbd|tba)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Pydantic models (1:1 with hub/lib/api.ts)
# ---------------------------------------------------------------------------

class ValidityCheck(BaseModel):
    check: str
    status: str  # pass | warn | fail
    message: str


class SceneAssetState(BaseModel):
    asset_type: AssetType
    status: str  # not_present | available | validated | stuck
    first_seen_at: str = ""
    validated_at: str = ""
    last_checked_at: str = ""
    validity: list[ValidityCheck] = []


class BoardShootScene(BaseModel):
    scene_id: str = ""
    studio: str
    scene_type: str
    grail_tab: str = ""
    position: int
    title: str = ""
    performers: str = ""
    has_thumbnail: bool = False
    mega_path: str = ""
    assets: list[SceneAssetState]


class Shoot(BaseModel):
    shoot_id: str
    shoot_date: str
    female_talent: str
    female_agency: str = ""
    male_talent: str = ""
    male_agency: str = ""
    destination: str = ""
    location: str = ""
    home_owner: str = ""
    source_tab: str = ""
    status: str = "active"
    scenes: list[BoardShootScene]
    aging_hours: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_shoot_date(s: str) -> Optional[date]:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _aging_hours(shoot_date: date) -> int:
    """Hours since midnight of shoot_date. 0 if shoot is today or upcoming."""
    now = datetime.utcnow()
    shoot_midnight = datetime.combine(shoot_date, datetime.min.time())
    delta = now - shoot_midnight
    return max(0, int(delta.total_seconds() // 3600))


def _shoot_id(shoot_date: str, female: str, male: str) -> str:
    base = f"{shoot_date}|{female.strip().lower()}|{male.strip().lower()}"
    h = hashlib.sha1(base.encode()).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "-", female.strip().lower()).strip("-") or "unnamed"
    return f"{shoot_date}-{slug}-{h}"


def _scene_state(
    scene_row: Optional[dict],
    script_row: dict,
    scene_type: str,
    shoot_date_iso: str,
    legal_folder_present: bool,
    checked_at: str,
) -> list[SceneAssetState]:
    """Compute the 11-cell state vector for one scene."""
    assets: dict[str, SceneAssetState] = {}
    validated_stamp = checked_at

    def put(at: str, status: str, validity: list[ValidityCheck] | None = None):
        assets[at] = SceneAssetState(
            asset_type=at,
            status=status,
            first_seen_at=validated_stamp if status != "not_present" else "",
            validated_at=validated_stamp if status == "validated" else "",
            last_checked_at=checked_at,
            validity=validity or [],
        )

    # script_done — has a plot string in the Scripts sheet
    plot = (script_row.get("plot") or "").strip()
    put("script_done", "validated" if plot else "not_present")

    # grail_run — daily_grail_update.py writes a Grail row with a scene_id on
    # the morning of the shoot. If we have a Grail match, that routine ran.
    grail_ran = bool(scene_row and (scene_row.get("id") or "").strip())
    put("grail_run", "validated" if grail_ran else "not_present")

    # legal_run — legal_docs_run.mjs creates a Drive folder
    # "{MMDDYY}-{Female}-{Male}" on the morning of each BG shoot.
    is_bg = scene_type.lower() in ("bg", "bgcp")
    if is_bg:
        put("legal_run", "validated" if legal_folder_present else "not_present")
    else:
        put("legal_run", "not_present")

    # call_sheet_sent / encoded_uploaded / legal_docs_uploaded — no validator yet
    for at in ("call_sheet_sent", "encoded_uploaded", "legal_docs_uploaded"):
        put(at, "not_present")

    # Asset state from MEGA scan
    if scene_row is None:
        for at in ("bg_edit_uploaded", "solo_uploaded", "title_done", "photoset_uploaded", "storyboard_uploaded"):
            put(at, "not_present")
    else:
        has_videos = bool(scene_row.get("has_videos"))
        video_count = int(scene_row.get("video_count") or 0)
        is_solo_like = scene_type.lower() in ("solo", "joi")

        # BG vs Solo: only fill the one that applies, the other stays not_present
        if is_solo_like:
            put("bg_edit_uploaded", "not_present")
            if has_videos:
                put("solo_uploaded", "validated")
            else:
                put("solo_uploaded", "not_present")
        else:
            put("solo_uploaded", "not_present")
            if has_videos:
                put("bg_edit_uploaded", "validated")
            else:
                put("bg_edit_uploaded", "not_present")

        put("title_done",       "validated" if scene_row.get("has_thumbnail")  else "not_present")
        put("photoset_uploaded", "validated" if scene_row.get("has_photos")     else "not_present")
        put("storyboard_uploaded","validated" if scene_row.get("has_storyboard") else "not_present")

        # Sanity: if shoot was >48h ago and videos exist but count is 0 → warn
        if has_videos and video_count == 0:
            assets["bg_edit_uploaded" if not is_solo_like else "solo_uploaded"].validity.append(
                ValidityCheck(check="count", status="warn", message="Folder present but 0 files")
            )

    return [assets[at] for at in ASSET_ORDER]


def _legal_folder_key(shoot_date: date, female: str, male: str) -> tuple[str, str]:
    """(month_name, folder_name) — mirrors legal_docs_run.mjs naming."""
    date_code = shoot_date.strftime("%m%d%y")
    month_name = shoot_date.strftime("%B")
    folder = f"{date_code}-{female.replace(' ', '')}-{male.replace(' ', '')}"
    return month_name, folder


def _load_legal_folders(shoot_dates: set[date]) -> set[tuple[date, str]]:
    """
    Returns a set of (shoot_date, folder_name) for every legal-run folder that
    exists in Drive for the months covered by `shoot_dates`. One Drive call per
    month (listing the month folder's children).

    Degrades gracefully: if creds are missing or Drive errors, returns empty set
    and callers fall back to `not_present`.
    """
    import json
    import os
    import urllib.parse
    import urllib.request

    if not shoot_dates:
        return set()

    creds_path = os.path.expanduser(LEGAL_CREDS_PATH)
    if not os.path.exists(creds_path):
        _log.info("legal creds missing at %s — skipping legal_run validation", creds_path)
        return set()

    try:
        with open(creds_path) as f:
            creds = json.load(f)

        # Refresh access token
        params = urllib.parse.urlencode({
            "grant_type":    "refresh_token",
            "refresh_token": creds["refresh_token"],
            "client_id":     creds["client_id"],
            "client_secret": creds["client_secret"],
        }).encode()
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=params, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            token = json.loads(r.read()).get("access_token")
        if not token:
            _log.warning("legal token refresh returned no access_token")
            return set()

        def drive_get(url: str) -> dict:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())

        # Build month → (year, folder_id) map for all months we care about
        month_to_year: dict[str, int] = {}
        for d in shoot_dates:
            month_to_year.setdefault(d.strftime("%B"), d.year)

        month_folder_ids: dict[str, str] = {}
        for month_name in month_to_year:
            q = (
                f"'{LEGAL_ROOT_FOLDER}' in parents "
                f"and name='{month_name}' "
                "and mimeType='application/vnd.google-apps.folder' "
                "and trashed=false"
            )
            url = (
                "https://www.googleapis.com/drive/v3/files"
                f"?q={urllib.parse.quote(q)}&fields=files(id,name)"
            )
            res = drive_get(url)
            files = (res or {}).get("files") or []
            if files:
                month_folder_ids[month_name] = files[0]["id"]

        # List children of each month folder; collect folder names
        month_folder_names: dict[str, set[str]] = {}
        for month_name, folder_id in month_folder_ids.items():
            q = f"'{folder_id}' in parents and trashed=false"
            names: set[str] = set()
            page_token: Optional[str] = None
            while True:
                qs = f"q={urllib.parse.quote(q)}&fields=nextPageToken,files(id,name)&pageSize=1000"
                if page_token:
                    qs += f"&pageToken={urllib.parse.quote(page_token)}"
                res = drive_get(f"https://www.googleapis.com/drive/v3/files?{qs}")
                for f in (res or {}).get("files") or []:
                    n = f.get("name")
                    if n:
                        names.add(n)
                page_token = (res or {}).get("nextPageToken")
                if not page_token:
                    break
            month_folder_names[month_name] = names

        found: set[tuple[date, str]] = set()
        for d in shoot_dates:
            month_name, _ = _legal_folder_key(d, "", "")
            for name in month_folder_names.get(month_name, ()):
                found.add((d, name))
        return found
    except Exception as exc:  # pragma: no cover — network/auth hiccup
        _log.warning("legal Drive lookup failed: %s", exc)
        return set()


def _match_scene_row(conn, studio: str, female: str) -> Optional[dict]:
    """
    Best-effort match: newest Grail scene for this studio that lists `female`
    in performers/female. Doesn't guarantee uniqueness — the shoot board shows
    'pending Grail' when no match is found, which is fine for pre-shoot state.
    """
    grail_tab = STUDIO_TO_GRAIL_TAB.get(studio, "")
    if not grail_tab:
        return None

    rows = conn.execute(
        """SELECT id, studio, grail_tab, title, performers, female, male,
                  has_thumbnail, has_videos, video_count, has_photos, has_storyboard,
                  release_date
             FROM scenes
            WHERE grail_tab = ?
              AND (
                    LOWER(female)     LIKE LOWER(?)
                 OR LOWER(performers) LIKE LOWER(?)
              )
            ORDER BY release_date DESC
            LIMIT 1""",
        (grail_tab, f"%{female.strip()}%", f"%{female.strip()}%"),
    ).fetchall()
    return dict(rows[0]) if rows else None


def _load_shoots_window(from_date: date, to_date: date, include_cancelled: bool) -> list[Shoot]:
    checked_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with get_db() as conn:
        rows = conn.execute(
            """SELECT tab_name, sheet_row, studio, shoot_date, location, scene_type,
                      female, male, plot, title, script_status
                 FROM scripts
                WHERE shoot_date != ''""",
        ).fetchall()

        groups: dict[str, list[dict]] = {}
        for r in rows:
            d = dict(r)
            sd = _parse_shoot_date(d["shoot_date"])
            if sd is None or not (from_date <= sd <= to_date):
                continue
            female = (d.get("female") or "").strip()
            if not female or SKIP_SCRIPT_ROWS.match(female):
                continue
            status = (d.get("script_status") or "").strip().lower()
            if not include_cancelled and status in ("cancelled", "cancel"):
                continue
            key = (sd.isoformat(), female.lower(), (d.get("male") or "").strip().lower())
            groups.setdefault("|".join(key), []).append({**d, "_parsed_date": sd.isoformat()})

        # One Drive round-trip per unique month, then we're membership-checking locally.
        shoot_dates = {date.fromisoformat(items[0]["_parsed_date"]) for items in groups.values() if items}
        legal_set = _load_legal_folders(shoot_dates)

        shoots: list[Shoot] = []
        for _, items in groups.items():
            # Stable ordering inside a shoot
            items.sort(key=lambda x: (x.get("studio") or "", int(x.get("sheet_row") or 0)))
            first = items[0]
            sd_iso = first["_parsed_date"]
            sd_obj = date.fromisoformat(sd_iso)
            female = (first.get("female") or "").strip()
            male = (first.get("male") or "").strip()
            shoot_id = _shoot_id(sd_iso, female, male)

            _, legal_folder_name = _legal_folder_key(sd_obj, female, male)
            legal_present = (sd_obj, legal_folder_name) in legal_set

            scenes: list[BoardShootScene] = []
            for position, it in enumerate(items[:3], start=1):
                studio = (it.get("studio") or "").strip()
                scene_type = (it.get("scene_type") or "BG").strip() or "BG"
                scene_row = _match_scene_row(conn, studio, female)
                assets = _scene_state(scene_row, it, scene_type, sd_iso, legal_present, checked_at)
                scenes.append(BoardShootScene(
                    scene_id=(scene_row or {}).get("id", "") or "",
                    studio=studio,
                    scene_type=scene_type,
                    grail_tab=STUDIO_TO_GRAIL_TAB.get(studio, ""),
                    position=position,
                    title=(scene_row or {}).get("title", "") or "",
                    performers=f"{female}{(' / ' + male) if male else ''}",
                    has_thumbnail=bool((scene_row or {}).get("has_thumbnail")),
                    mega_path="",
                    assets=assets,
                ))

            shoots.append(Shoot(
                shoot_id=shoot_id,
                shoot_date=sd_iso,
                female_talent=female,
                male_talent=male,
                source_tab=first.get("tab_name") or "",
                status=(first.get("script_status") or "active").lower().strip() or "active",
                scenes=scenes,
                aging_hours=_aging_hours(date.fromisoformat(sd_iso)),
            ))

        shoots.sort(key=lambda s: s.shoot_date, reverse=True)
        return shoots


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[Shoot])
async def list_shoots(
    user: CurrentUser,
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
    studio: Optional[str] = Query(default=None),
    include_cancelled: bool = Query(default=False),
):
    today = date.today()
    fd = _parse_shoot_date(from_date) if from_date else today - timedelta(days=14)
    td = _parse_shoot_date(to_date) if to_date else today + timedelta(days=14)
    if fd is None or td is None:
        raise HTTPException(status_code=400, detail="Invalid from_date / to_date")

    shoots = _load_shoots_window(fd, td, include_cancelled)
    if studio:
        shoots = [s for s in shoots if any(sc.studio == studio for sc in s.scenes)]
    return shoots


def _find_shoot(shoot_id: str) -> Shoot:
    today = date.today()
    for s in _load_shoots_window(today - timedelta(days=60), today + timedelta(days=60), include_cancelled=True):
        if s.shoot_id == shoot_id:
            return s
    raise HTTPException(status_code=404, detail="Shoot not found")


@router.get("/{shoot_id}", response_model=Shoot)
async def get_shoot(shoot_id: str, user: CurrentUser):
    return _find_shoot(shoot_id)


@router.post(
    "/{shoot_id}/scenes/{position}/assets/{asset_type}/revalidate",
    response_model=SceneAssetState,
)
async def revalidate_asset(shoot_id: str, position: int, asset_type: str, user: CurrentUser):
    """
    Re-run inference for a single cell. Right now this just reloads the shoot
    and returns the freshly-computed state — useful after a MEGA scan.
    """
    shoot = _find_shoot(shoot_id)
    for sc in shoot.scenes:
        if sc.position == position:
            for a in sc.assets:
                if a.asset_type == asset_type:
                    return a
    raise HTTPException(status_code=404, detail="Asset cell not found")
