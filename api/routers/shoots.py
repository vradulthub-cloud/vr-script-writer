"""
Shoot Board API router.

A "shoot" is one day of production for one female talent, sourced from the
Scripts sheet (mirrored to the `scripts` table). Each shoot holds 1–3 scenes
(BG / Solo / JOI across studios) that map best-effort to Grail rows for
MEGA asset state.

Routes:
  GET  /api/shoots/                                                  — list shoots in the current+next month
  GET  /api/shoots/{shoot_id}                                        — single shoot
  POST /api/shoots/{shoot_id}/scenes/{pos}/assets/{at}/revalidate    — force-refresh one cell

Asset-state inference:
  - script_done         → scripts.plot non-empty
  - grail_run           → scene matched in Grail (daily_grail_update.py ran)
  - legal_run           → BOTH talents' legal PDFs exist in the Drive folder
                          (proves legal_docs_run.mjs completed)
  - legal_docs_uploaded → male ID photo (Name.jpg) + ≥1 female ID photo (.jpg)
                          + ≥1 video sign-out (.mov) all present in the folder
  - bg_edit_uploaded    → scene has videos in MEGA (BG/BGCP only)
  - solo_uploaded       → scene has videos in MEGA (Solo/JOI only)
  - title_done          → scene has_thumbnail
  - photoset_uploaded   → scene has_photos
  - storyboard_uploaded → scene has_storyboard
  - call_sheet_sent / encoded_uploaded → no validator yet
"""

from __future__ import annotations

import hashlib
import logging
import re
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
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

AssetType = str

ASSET_ORDER: list[AssetType] = [
    "script_done", "call_sheet_sent", "legal_run", "grail_run",
    "bg_edit_uploaded", "solo_uploaded",
    "title_done", "encoded_uploaded",
    "photoset_uploaded", "storyboard_uploaded", "legal_docs_uploaded",
]

STUDIO_TO_GRAIL_TAB = {
    "FuckPassVR": "FPVR",
    "VRHush":     "VRH",
    "VRAllure":   "VRA",
    "NaughtyJOI": "NNJOI",
}

# For call-sheet title cross-check: Docs use the UI name (VRHush), not the
# Grail tab (VRH). We treat either form as a valid match.
STUDIO_TITLE_TOKENS = {
    "FuckPassVR": ("FUCKPASSVR", "FPVR"),
    "VRHush":     ("VRHUSH",     "VRH"),
    "VRAllure":   ("VRALLURE",   "VRA"),
    "NaughtyJOI": ("NAUGHTYJOI", "NNJOI"),
}

SKIP_SCRIPT_ROWS = re.compile(r"^(cancel|note|tbd|tba)", re.IGNORECASE)

LEGAL_ROOT_FOLDER = "132MZR2EgBeEEJRmF3OJke5WnZozkv2cJ"
LEGAL_CREDS_PATH = "~/.config/google-legal-docs/credentials.json"

# Call-sheet Doc title format (from call_sheets.py): "{M/D/YYYY} - {studios} Call Sheet"
CALL_SHEET_TOKEN_RE = re.compile(r"Call Sheet", re.IGNORECASE)


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
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    shoot_midnight = datetime.combine(shoot_date, datetime.min.time())
    delta = now - shoot_midnight
    return max(0, int(delta.total_seconds() // 3600))


def _shoot_id(shoot_date: str, female: str) -> str:
    """Stable ID per (date, female talent). Excludes male so BG+Solo merge."""
    base = f"{shoot_date}|{female.strip().lower()}"
    h = hashlib.sha1(base.encode()).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "-", female.strip().lower()).strip("-") or "unnamed"
    return f"{shoot_date}-{slug}-{h}"


def _legal_folder_key(shoot_date: date, female: str, male: str) -> tuple[str, str]:
    """(month_name, folder_name) — mirrors legal_docs_run.mjs naming."""
    date_code = shoot_date.strftime("%m%d%y")
    month_name = shoot_date.strftime("%B")
    folder = f"{date_code}-{female.replace(' ', '')}-{male.replace(' ', '')}"
    return month_name, folder


# ---------------------------------------------------------------------------
# Legal Drive lookup — now returns full file list per folder
# ---------------------------------------------------------------------------

def _load_legal_folders(shoot_dates: set[date]) -> dict[tuple[date, str], list[str]]:
    """
    Returns {(shoot_date, folder_name): [filename, ...]} for every legal-run
    folder in Drive for the months covered by `shoot_dates`.

    Cost: one Drive call per unique month for the folder listing, then one
    call per shoot folder to list its children. Degrades to {} on creds miss
    or network error — callers fall back to `not_present`.
    """
    import json
    import os
    import urllib.parse
    import urllib.request

    if not shoot_dates:
        return {}

    creds_path = os.path.expanduser(LEGAL_CREDS_PATH)
    if not os.path.exists(creds_path):
        _log.info("legal creds missing at %s — skipping legal validation", creds_path)
        return {}

    try:
        with open(creds_path) as f:
            creds = json.load(f)

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
            return {}

        def drive_get(url: str) -> dict:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())

        # Step 1: locate each month folder we care about
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
            res = drive_get(
                "https://www.googleapis.com/drive/v3/files"
                f"?q={urllib.parse.quote(q)}&fields=files(id,name)"
            )
            files = (res or {}).get("files") or []
            if files:
                month_folder_ids[month_name] = files[0]["id"]

        # Step 2: for each month, list shoot folders; map folder_name → folder_id
        shoot_folder_ids: dict[tuple[str, str], str] = {}
        for month_name, month_id in month_folder_ids.items():
            q = f"'{month_id}' in parents and trashed=false"
            page_token: Optional[str] = None
            while True:
                qs = f"q={urllib.parse.quote(q)}&fields=nextPageToken,files(id,name)&pageSize=1000"
                if page_token:
                    qs += f"&pageToken={urllib.parse.quote(page_token)}"
                res = drive_get(f"https://www.googleapis.com/drive/v3/files?{qs}")
                for f in (res or {}).get("files") or []:
                    name = f.get("name", "")
                    fid = f.get("id", "")
                    if name and fid:
                        shoot_folder_ids[(month_name, name)] = fid
                page_token = (res or {}).get("nextPageToken")
                if not page_token:
                    break

        # Step 3: for each shoot folder we need, list its children
        result: dict[tuple[date, str], list[str]] = {}
        for d in shoot_dates:
            month_name, folder_name = _legal_folder_key(d, "", "")
            # _legal_folder_key needs names to derive full folder name, so we
            # instead iterate over every shoot folder in the relevant month
            for (mname, fname), fid in shoot_folder_ids.items():
                if mname != d.strftime("%B"):
                    continue
                if not fname.startswith(d.strftime("%m%d%y") + "-"):
                    continue
                q = f"'{fid}' in parents and trashed=false"
                child = drive_get(
                    f"https://www.googleapis.com/drive/v3/files"
                    f"?q={urllib.parse.quote(q)}&fields=files(name,mimeType)&pageSize=1000"
                )
                names = [c.get("name", "") for c in (child.get("files") or [])]
                result[(d, fname)] = names
        return result
    except Exception as exc:  # pragma: no cover
        _log.warning("legal Drive lookup failed: %s", exc)
        return {}


def _load_call_sheets(shoot_dates: set[date]) -> dict[date, str]:
    """
    Return {date: doc_title} for every date in `shoot_dates` whose Call
    Sheet Google Doc exists. Callers use the doc title to cross-check the
    Scripts sheet (title format is "M/D/YYYY - {studios} Call Sheet").

    Uses vr_oauth_token.json that call_sheets.py already relies on.
    Degrades gracefully on any error — callers fall back to not_present.
    """
    import json
    import os
    import urllib.parse
    import urllib.request

    if not shoot_dates:
        return {}

    # call_sheets.py reads from settings.base_dir / "vr_oauth_token.json"
    from api.config import get_settings
    token_path = get_settings().base_dir / "vr_oauth_token.json"
    if not token_path.exists():
        _log.info("vr_oauth_token missing — skipping call_sheet validation")
        return {}

    try:
        with open(token_path) as f:
            tok = json.load(f)

        params = urllib.parse.urlencode({
            "grant_type":    "refresh_token",
            "refresh_token": tok["refresh_token"],
            "client_id":     tok["client_id"],
            "client_secret": tok["client_secret"],
        }).encode()
        req = urllib.request.Request(
            tok.get("token_uri", "https://oauth2.googleapis.com/token"),
            data=params, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            access_token = json.loads(r.read()).get("access_token")
        if not access_token:
            return {}

        # Call-sheet Doc titles contain the date in M/D/YYYY form (no zero pad).
        # Build a single Drive query per unique month — Drive's fulltext /
        # name-contains search is case-insensitive and indexed.
        found: dict[date, str] = {}
        months = {(d.month, d.year) for d in shoot_dates}
        for month, year in months:
            q = (
                f"name contains '/{year} - ' "
                "and name contains 'Call Sheet' "
                "and mimeType='application/vnd.google-apps.document' "
                "and trashed=false"
            )
            url = (
                "https://www.googleapis.com/drive/v3/files"
                f"?q={urllib.parse.quote(q)}&fields=files(name)&pageSize=1000"
            )
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    res = json.loads(r.read())
            except Exception as exc:
                _log.warning("Call-sheet Drive query failed for %s/%s: %s", month, year, exc)
                continue
            # Parse each title's leading "M/D/YYYY - ..." and collect the dates
            for f in (res.get("files") or []):
                name = f.get("name", "")
                m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})\s*-", name)
                if not m:
                    continue
                try:
                    d = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
                except ValueError:
                    continue
                if d in shoot_dates:
                    # Drive may return trashed duplicates, picking newest by
                    # longer title is arbitrary but deterministic.
                    existing = found.get(d)
                    if existing is None or len(name) > len(existing):
                        found[d] = name
        return found
    except Exception as exc:  # pragma: no cover
        _log.warning("Call-sheet lookup failed: %s", exc)
        return {}


def _validate_legal_files(
    folder_files: list[str],
    female: str,
    male: str,
    date_code: str,
) -> tuple[str, list[ValidityCheck], str, list[ValidityCheck]]:
    """
    Returns ((legal_run_status, legal_run_validity), (legal_docs_status, legal_docs_validity)).

    legal_run:          both PDFs present (legal_docs_run.mjs output)
    legal_docs_uploaded: male ID .jpg + ≥1 female .jpg + ≥1 .mov
    """
    names_lower = [n.lower() for n in folder_files]
    female_nosp = female.replace(" ", "")
    male_nosp = male.replace(" ", "")

    # ── legal_run: PDFs ────────────────────────────────────────────────
    pdf_checks: list[ValidityCheck] = []
    female_pdf = f"{female_nosp}-{date_code}.pdf".lower()
    male_pdf   = f"{male_nosp}-{date_code}.pdf".lower()

    has_female_pdf = female_pdf in names_lower
    has_male_pdf   = male_pdf in names_lower if male_nosp else True

    if has_female_pdf:
        pdf_checks.append(ValidityCheck(check="female_pdf", status="pass",
                                        message=f"{female_nosp} PDF present"))
    else:
        pdf_checks.append(ValidityCheck(check="female_pdf", status="fail",
                                        message=f"Missing {female_nosp}-{date_code}.pdf"))

    if male_nosp:
        if has_male_pdf:
            pdf_checks.append(ValidityCheck(check="male_pdf", status="pass",
                                            message=f"{male_nosp} PDF present"))
        else:
            pdf_checks.append(ValidityCheck(check="male_pdf", status="fail",
                                            message=f"Missing {male_nosp}-{date_code}.pdf"))

    if male_nosp:
        # BG with male: we expect both PDFs
        if has_female_pdf and has_male_pdf:
            legal_run_status = "validated"
        elif has_female_pdf or has_male_pdf:
            legal_run_status = "available"
        else:
            legal_run_status = "not_present"
    else:
        # Female-only BG: only the female PDF matters; male_nosp missing
        # means has_male_pdf defaulted to True, so we'd otherwise false-
        # positive "available" even with nothing uploaded.
        legal_run_status = "validated" if has_female_pdf else "not_present"

    # ── legal_docs_uploaded: IDs + video ─────────────────────────────
    doc_checks: list[ValidityCheck] = []

    # Male ID .jpg — must contain the male's name
    has_male_id = False
    if male_nosp:
        male_id_matches = [
            n for n in folder_files
            if n.lower().endswith(".jpg") and male_nosp.lower() in n.lower().replace(" ", "")
        ]
        has_male_id = bool(male_id_matches)
        if has_male_id:
            doc_checks.append(ValidityCheck(check="male_id", status="pass",
                                            message=f"{male_id_matches[0]} present"))
        else:
            doc_checks.append(ValidityCheck(check="male_id", status="fail",
                                            message=f"Missing {male_nosp} ID photo (.jpg)"))

    # Female ID .jpg — any .jpg that doesn't match the male's name
    female_id_candidates = [
        n for n in folder_files
        if n.lower().endswith(".jpg")
        and (not male_nosp or male_nosp.lower() not in n.lower().replace(" ", ""))
    ]
    has_female_id = bool(female_id_candidates)
    if has_female_id:
        doc_checks.append(ValidityCheck(
            check="female_id", status="pass",
            message=f"{len(female_id_candidates)} female ID photo(s)",
        ))
    else:
        doc_checks.append(ValidityCheck(check="female_id", status="fail",
                                        message="No female ID photos (.jpg)"))

    # Video sign-out (.mov) — any one video
    movs = [n for n in folder_files if n.lower().endswith(".mov")]
    has_video = bool(movs)
    if has_video:
        doc_checks.append(ValidityCheck(check="video_signout", status="pass",
                                        message=f"{movs[0]} present"))
    else:
        doc_checks.append(ValidityCheck(check="video_signout", status="fail",
                                        message="No .mov video sign-out"))

    required = [has_female_id, has_video] + ([has_male_id] if male_nosp else [])
    if all(required):
        legal_docs_status = "validated"
    elif any(required):
        legal_docs_status = "available"
    else:
        legal_docs_status = "not_present"

    return (legal_run_status, pdf_checks, legal_docs_status, doc_checks)


# ---------------------------------------------------------------------------
# Grail scene matching
# ---------------------------------------------------------------------------

_COMPILATION_RE = re.compile(r"\b(vol\.?|compilation|best\b)", re.IGNORECASE)


def _match_scene_row(conn, studio: str, female: str, shoot_date: date) -> Optional[dict]:
    """
    Find the Grail scene created for THIS shoot. `daily_grail_update.py`
    appends a new Grail row on the morning of each shoot, so the most
    recently-appended row for (studio, talent) is the row for the nearest
    shoot.

    Rules:
      - Skip compilations (Vol./Best/Compilation)
      - Order by `grail_row DESC` (append order ≈ shoot order) so the
        newest-added row wins over an ancient archive scene
      - For FUTURE shoots (shoot_date > today), do not match — the Grail
        row doesn't exist yet, and matching to any older scene creates a
        false "grail_run: validated"
    """
    grail_tab = STUDIO_TO_GRAIL_TAB.get(studio, "")
    if not grail_tab:
        return None
    if shoot_date > date.today():
        return None  # No Grail row exists until the morning of the shoot

    rows = conn.execute(
        """SELECT id, studio, grail_tab, grail_row, title, performers, female, male,
                  has_thumbnail, has_videos, video_count, has_photos, has_storyboard,
                  release_date, is_compilation
             FROM scenes
            WHERE grail_tab = ?
              AND (
                    LOWER(female)     LIKE LOWER(?)
                 OR LOWER(performers) LIKE LOWER(?)
              )
            ORDER BY grail_row DESC""",
        (grail_tab, f"%{female.strip()}%", f"%{female.strip()}%"),
    ).fetchall()
    for r in rows:
        d = dict(r)
        title = (d.get("title") or "").strip()
        if d.get("is_compilation") or _COMPILATION_RE.search(title):
            continue
        return d
    return None


# ---------------------------------------------------------------------------
# Scene state vector
# ---------------------------------------------------------------------------

def _scene_state(
    scene_row: Optional[dict],
    script_row: dict,
    scene_type: str,
    legal_run_status: str,
    legal_run_validity: list[ValidityCheck],
    legal_docs_status: str,
    legal_docs_validity: list[ValidityCheck],
    call_sheet_status: str,
    call_sheet_validity: list[ValidityCheck],
    checked_at: str,
) -> list[SceneAssetState]:
    """Compute the 11-cell state vector for one scene."""
    assets: dict[str, SceneAssetState] = {}

    def put(at: str, status: str, validity: Optional[list[ValidityCheck]] = None):
        assets[at] = SceneAssetState(
            asset_type=at,
            status=status,
            first_seen_at=checked_at if status != "not_present" else "",
            validated_at=checked_at if status == "validated" else "",
            last_checked_at=checked_at,
            validity=validity or [],
        )

    # script_done — plot filled in Scripts sheet
    plot = (script_row.get("plot") or "").strip()
    put("script_done", "validated" if plot else "not_present")

    # grail_run — scene matched in Grail DB
    grail_ran = bool(scene_row and (scene_row.get("id") or "").strip())
    put("grail_run", "validated" if grail_ran else "not_present")

    # legal_run / legal_docs_uploaded — only meaningful for BG/BGCP
    is_bg = scene_type.lower() in ("bg", "bgcp")
    if is_bg:
        put("legal_run", legal_run_status, legal_run_validity)
        put("legal_docs_uploaded", legal_docs_status, legal_docs_validity)
    else:
        put("legal_run", "not_present")
        put("legal_docs_uploaded", "not_present")

    # call_sheet_sent — Doc whose title matches this shoot's date.
    # Status + validity is computed once per shoot (in _load_shoots_window)
    # because the Doc is shared across all scenes on the same day.
    put("call_sheet_sent", call_sheet_status, call_sheet_validity)

    # encoded_uploaded — no validator yet
    put("encoded_uploaded", "not_present")

    # MEGA-derived states
    if scene_row is None:
        for at in ("bg_edit_uploaded", "solo_uploaded", "title_done", "photoset_uploaded", "storyboard_uploaded"):
            put(at, "not_present")
    else:
        has_videos = bool(scene_row.get("has_videos"))
        video_count = int(scene_row.get("video_count") or 0)
        is_solo_like = scene_type.lower() in ("solo", "joi")

        if is_solo_like:
            put("bg_edit_uploaded", "not_present")
            put("solo_uploaded", "validated" if has_videos else "not_present")
        else:
            put("solo_uploaded", "not_present")
            put("bg_edit_uploaded", "validated" if has_videos else "not_present")

        put("title_done",        "validated" if scene_row.get("has_thumbnail")  else "not_present")
        put("photoset_uploaded", "validated" if scene_row.get("has_photos")     else "not_present")
        put("storyboard_uploaded","validated" if scene_row.get("has_storyboard") else "not_present")

        if has_videos and video_count == 0:
            assets["bg_edit_uploaded" if not is_solo_like else "solo_uploaded"].validity.append(
                ValidityCheck(check="count", status="warn", message="Folder present but 0 files")
            )

    return [assets[at] for at in ASSET_ORDER]


# ---------------------------------------------------------------------------
# Window loader
# ---------------------------------------------------------------------------

def _load_shoots_window(from_date: date, to_date: date, include_cancelled: bool) -> list[Shoot]:
    checked_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"

    with get_db() as conn:
        rows = conn.execute(
            """SELECT tab_name, sheet_row, studio, shoot_date, location, scene_type,
                      female, male, plot, title, script_status
                 FROM scripts
                WHERE shoot_date != ''""",
        ).fetchall()

        # Group by (date, female) — male excluded so BG+Solo on same day merge.
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
            key = f"{sd.isoformat()}|{female.lower()}"
            groups.setdefault(key, []).append({**d, "_parsed_date": sd.isoformat()})

        # One Drive round-trip each for legal docs + call sheets, spanning
        # every shoot date in the window
        shoot_dates = {date.fromisoformat(items[0]["_parsed_date"]) for items in groups.values() if items}
        legal_folders = _load_legal_folders(shoot_dates)
        call_sheet_dates = _load_call_sheets(shoot_dates)

        shoots: list[Shoot] = []
        for _, items in groups.items():
            items.sort(key=lambda x: (x.get("studio") or "", int(x.get("sheet_row") or 0)))
            first = items[0]
            sd_iso = first["_parsed_date"]
            sd_obj = date.fromisoformat(sd_iso)
            female = (first.get("female") or "").strip()
            # Male: take the first non-empty male across all scenes on this
            # day. A female doing BG (with male) + Solo (no male) on the same
            # day would otherwise report male='' if the Solo row sorted first,
            # which breaks legal folder lookup and shoot-card display.
            male = ""
            for it in items:
                m = (it.get("male") or "").strip()
                if m:
                    male = m
                    break
            shoot_id = _shoot_id(sd_iso, female)

            _, legal_folder_name = _legal_folder_key(sd_obj, female, male)
            legal_files = legal_folders.get((sd_obj, legal_folder_name), [])
            date_code = sd_obj.strftime("%m%d%y")
            legal_run_status, legal_run_v, legal_docs_status, legal_docs_v = _validate_legal_files(
                legal_files, female, male, date_code,
            )

            # Call sheet: validated if Drive Doc exists for this date AND
            # the Doc title mentions every studio we have scripts for.
            # Docs use either the UI name (VRHush) or tab (VRH) — either counts.
            expected_studios = {
                (it.get("studio") or "").strip()
                for it in items
            }
            expected_studios.discard("")
            call_sheet_title = call_sheet_dates.get(sd_obj)
            call_sheet_v: list[ValidityCheck] = []
            if call_sheet_title:
                title_upper = call_sheet_title.upper()
                missing_studios = []
                for studio_name in expected_studios:
                    tokens = STUDIO_TITLE_TOKENS.get(studio_name)
                    if tokens is None:
                        continue  # unknown studio; don't false-warn
                    if not any(t in title_upper for t in tokens):
                        missing_studios.append(studio_name)
                if missing_studios:
                    call_sheet_v.append(ValidityCheck(
                        check="studio_match", status="warn",
                        message=f"Call sheet missing studios: {', '.join(sorted(missing_studios))}",
                    ))
                    call_sheet_status = "available"
                else:
                    call_sheet_v.append(ValidityCheck(
                        check="studio_match", status="pass",
                        message=f"Doc: {call_sheet_title[:60]}",
                    ))
                    call_sheet_status = "validated"
            else:
                call_sheet_status = "not_present"

            scenes: list[BoardShootScene] = []
            for position, it in enumerate(items[:3], start=1):
                studio = (it.get("studio") or "").strip()
                scene_type = (it.get("scene_type") or "BG").strip() or "BG"
                scene_row = _match_scene_row(conn, studio, female, sd_obj)
                assets = _scene_state(
                    scene_row, it, scene_type,
                    legal_run_status, legal_run_v,
                    legal_docs_status, legal_docs_v,
                    call_sheet_status, call_sheet_v,
                    checked_at,
                )
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
                aging_hours=_aging_hours(sd_obj),
            ))

        shoots.sort(key=lambda s: s.shoot_date, reverse=True)
        return shoots


def _default_window() -> tuple[date, date]:
    """Current month + next month — covers 'all the month's shoots' per user."""
    today = date.today()
    start = today.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    last_day_next = monthrange(next_month.year, next_month.month)[1]
    end = next_month.replace(day=last_day_next)
    return start, end


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
    default_from, default_to = _default_window()
    fd = _parse_shoot_date(from_date) if from_date else default_from
    td = _parse_shoot_date(to_date) if to_date else default_to
    if fd is None or td is None:
        raise HTTPException(status_code=400, detail="Invalid from_date / to_date")

    shoots = _load_shoots_window(fd, td, include_cancelled)
    if studio:
        shoots = [s for s in shoots if any(sc.studio == studio for sc in s.scenes)]
    return shoots


def _find_shoot(shoot_id: str) -> Shoot:
    today = date.today()
    for s in _load_shoots_window(today - timedelta(days=90), today + timedelta(days=90), include_cancelled=True):
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
    shoot = _find_shoot(shoot_id)
    for sc in shoot.scenes:
        if sc.position == position:
            for a in sc.assets:
                if a.asset_type == asset_type:
                    return a
    raise HTTPException(status_code=404, detail="Asset cell not found")
