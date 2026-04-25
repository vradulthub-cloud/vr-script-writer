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

import asyncio
import hashlib
import json
import logging
import re
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import CurrentUser, validate_sse_token
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
# LEGAL_CREDS_PATH removed — use service account via _get_drive_token() instead

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
    female_rate: Optional[str] = None
    male_talent: str = ""
    male_agency: str = ""
    male_rate: Optional[str] = None
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



# ---------------------------------------------------------------------------
# Budget sheet rate lookup — cached 5 min
# ---------------------------------------------------------------------------
import threading as _threading_bgt
_BUDGET_CACHE: dict = {}
_BUDGET_LOCK = _threading_bgt.Lock()


def _load_budget_rates() -> dict:
    """Return {(date_str, female_lower): {female_rate, male_rate}} from budget sheet.
    Cached 5 minutes."""
    import time as _time
    now = _time.monotonic()
    with _BUDGET_LOCK:
        cached = _BUDGET_CACHE.get("data")
        if cached is not None and now - _BUDGET_CACHE.get("ts", 0) < 300:
            return cached
    try:
        from api.sheets_client import open_budgets, with_retry
        wb = with_retry(open_budgets)
        rates: dict = {}
        _months = ("january","february","march","april","may","june",
                   "july","august","september","october","november","december")
        for ws in wb.worksheets():
            if not any(m in ws.title.lower() for m in _months):
                continue
            rows = with_retry(ws.get_all_values)
            if not rows:
                continue
            for row in rows[1:]:
                if len(row) < 5 or not row[0].strip() or not row[4].strip():
                    continue
                raw_date = row[0].strip().split(" ")[0].split("T")[0]
                parts = raw_date.replace("/", "-").split("-")
                if len(parts) == 3:
                    if len(parts[0]) == 4:
                        date_str = raw_date.replace("/", "-")
                    else:
                        m_p, d_p, y_p = parts
                        y_full = "20" + y_p if len(y_p) == 2 else y_p
                        date_str = "{}-{}-{}".format(y_full, m_p.zfill(2), d_p.zfill(2))
                else:
                    continue
                f_talent = row[4].strip()
                f_rate_raw = row[6].strip() if len(row) > 6 else ""
                m_rate_raw = row[10].strip() if len(row) > 10 else ""
                def _fmt(v):
                    if not v:
                        return None
                    try:
                        return "${:,}".format(int(float(v)))
                    except (ValueError, TypeError):
                        return v or None
                key = (date_str, f_talent.lower())
                if key not in rates:
                    rates[key] = {"female_rate": _fmt(f_rate_raw), "male_rate": _fmt(m_rate_raw)}
        with _BUDGET_LOCK:
            _BUDGET_CACHE["data"] = rates
            _BUDGET_CACHE["ts"] = now
        return rates
    except Exception as exc:
        _log.warning("budget rate lookup failed: %s", exc)
        with _BUDGET_LOCK:
            return _BUDGET_CACHE.get("data") or {}


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

def _get_drive_token() -> Optional[str]:
    """Return a short-lived Drive read-only access token via the service account."""
    from google.oauth2 import service_account as _sa
    from google.auth.transport.requests import Request as _GReq
    from api.config import get_settings
    try:
        settings = get_settings()
        creds = _sa.Credentials.from_service_account_file(
            str(settings.service_account_file),
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        creds.refresh(_GReq())
        return creds.token
    except Exception as exc:
        _log.warning("drive token fetch failed: %s", exc)
        return None



def _get_drive_rw_token() -> Optional[str]:
    """Return a short-lived Drive read-write access token (needed for file copy/delete)."""
    from google.oauth2 import service_account as _sa
    from google.auth.transport.requests import Request as _GReq
    from api.config import get_settings
    try:
        settings = get_settings()
        creds = _sa.Credentials.from_service_account_file(
            str(settings.service_account_file),
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        creds.refresh(_GReq())
        return creds.token
    except Exception as exc:
        _log.warning("drive rw token fetch failed: %s", exc)
        return None


def _ocr_pdf_id(pdf_id: str, rw_token: str) -> str:
    """Copy PDF as a Google Doc (triggers Drive OCR), export text, delete the copy."""
    import urllib.request
    import urllib.parse
    import json

    body = json.dumps({
        "name": "_w9_tmp_extract",
        "mimeType": "application/vnd.google-apps.document",
    }).encode()
    req = urllib.request.Request(
        f"https://www.googleapis.com/drive/v3/files/{pdf_id}/copy",
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {rw_token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        doc = json.loads(r.read())
    doc_id = doc.get("id")
    if not doc_id:
        raise ValueError("drive copy returned no id")

    try:
        req2 = urllib.request.Request(
            f"https://www.googleapis.com/drive/v3/files/{doc_id}/export"
            f"?mimeType={urllib.parse.quote('text/plain')}",
            headers={"Authorization": f"Bearer {rw_token}"},
        )
        with urllib.request.urlopen(req2, timeout=15) as r2:
            return r2.read().decode("utf-8", errors="replace")
    finally:
        try:
            urllib.request.urlopen(
                urllib.request.Request(
                    f"https://www.googleapis.com/drive/v3/files/{doc_id}",
                    method="DELETE",
                    headers={"Authorization": f"Bearer {rw_token}"},
                ),
                timeout=10,
            ).close()
        except Exception:
            pass


def _parse_w9_ocr_name(text: str) -> str:
    """Extract the legal name (Line 1) from OCR text of a W9 form."""
    import re as _re
    boilerplate = ("required", "leave this", "do not", "line blank", "income tax return",
                   "form w-9", "form w9", "request for taxpayer")
    for pattern in (
        r"Name\s*\(as shown[^)]+\)[^\n]*\n\s*([A-Z][^\n]{2,80})",
        r"1\s+Name[^\n]*\n\s*([A-Z][^\n]{2,80})",
        r"Name[^\n]*\n\s*([A-Z][a-z][^\n]{2,60})",
    ):
        m = _re.search(pattern, text, _re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if not any(x in candidate.lower() for x in boilerplate) and len(candidate) >= 3:
                return candidate
    return ""


def _load_legal_folders(shoot_dates: set[date]) -> dict[tuple[date, str], list[str]]:
    """
    Returns {(shoot_date, folder_name): [filename, ...]} for every legal-run
    folder in Drive for the months covered by `shoot_dates`.

    Cost: one Drive call per unique month for the folder listing, then one
    call per shoot folder to list its children. Degrades to {} on creds miss
    or network error — callers fall back to `not_present`.
    """
    import urllib.parse
    import urllib.request
    import json

    if not shoot_dates:
        return {}

    token = _get_drive_token()
    if not token:
        return {}

    try:
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

def _load_asset_state_overlay(conn, scene_ids: list[str]) -> dict[str, dict[str, dict]]:
    """
    Bulk-load the remote `scene_asset_state` rows for these scene_ids and
    return {scene_id: {asset_type: {status, validity_json}}}.

    This table is written by mega_scan_worker / asset_states sync and is the
    freshest source of truth for MEGA-derived cells (photoset_uploaded,
    bg_edit_uploaded, title_done, etc.). The scenes table booleans are fed
    from a sparse mega_scan.json and go stale fast, so we treat
    scene_asset_state as the authoritative overlay when a row exists.
    """
    import json as _json
    if not scene_ids:
        return {}
    placeholders = ",".join("?" * len(scene_ids))
    rows = conn.execute(
        f"""SELECT scene_id, asset_type, status, validity_json
              FROM scene_asset_state
             WHERE scene_id IN ({placeholders})""",
        scene_ids,
    ).fetchall()
    out: dict[str, dict[str, dict]] = {}
    for r in rows:
        d = dict(r)
        validity = []
        raw = d.get("validity_json") or ""
        if raw:
            try:
                validity = _json.loads(raw) or []
            except Exception:
                validity = []
        out.setdefault(d["scene_id"], {})[d["asset_type"]] = {
            "status":   d.get("status") or "not_present",
            "validity": validity,
        }
    return out


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
    asset_overlay: Optional[dict[str, dict]] = None,
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

    # MEGA-derived states — primary signal comes from the `scenes` booleans
    # (fed by mega_scan.json, refreshed per hot/cold scan). The
    # `scene_asset_state` overlay is treated as *additive* — it can confirm
    # validation or attach validity checks, but it must never *demote* a
    # cell below what `scenes` already says is present. A stale overlay row
    # stuck at `not_present` would otherwise override fresh, correct data
    # (see: every BGCP scene after 2026-04-13 showing blank despite assets
    # existing in MEGA).
    is_solo_like = scene_type.lower() in ("solo", "joi")
    mega_cells = ("bg_edit_uploaded", "solo_uploaded", "title_done",
                  "photoset_uploaded", "storyboard_uploaded", "encoded_uploaded")

    _STATUS_RANK = {"not_present": 0, "available": 1, "stuck": 2, "validated": 3}

    def _merge_overlay(at: str, fallback_status: str) -> None:
        """
        Resolve final status for `at` as max(fallback, overlay). Overlay
        validity checks are always carried forward so a "validated" cell
        can still surface warnings.
        """
        overlay_row = (asset_overlay or {}).get(at)
        checks: list[ValidityCheck] = []
        overlay_status = ""
        if overlay_row:
            overlay_status = overlay_row.get("status") or ""
            for v in overlay_row.get("validity") or []:
                if not isinstance(v, dict):
                    continue
                try:
                    checks.append(ValidityCheck(
                        check=str(v.get("check", "")),
                        status=str(v.get("status", "")),
                        message=str(v.get("message", "")),
                    ))
                except Exception:
                    continue
        fallback_rank = _STATUS_RANK.get(fallback_status, 0)
        overlay_rank  = _STATUS_RANK.get(overlay_status, 0)
        final = overlay_status if overlay_rank > fallback_rank else fallback_status
        put(at, final, checks)

    if scene_row is None and not asset_overlay:
        for at in mega_cells:
            put(at, "not_present")
    else:
        has_videos = bool((scene_row or {}).get("has_videos"))
        video_count = int((scene_row or {}).get("video_count") or 0)

        # bg_edit / solo — the cell that doesn't match the scene_type stays not_present
        if is_solo_like:
            _merge_overlay("solo_uploaded", "validated" if has_videos else "not_present")
            put("bg_edit_uploaded", "not_present")
        else:
            _merge_overlay("bg_edit_uploaded", "validated" if has_videos else "not_present")
            put("solo_uploaded", "not_present")

        _merge_overlay("title_done",          "validated" if (scene_row or {}).get("has_thumbnail")  else "not_present")
        _merge_overlay("photoset_uploaded",   "validated" if (scene_row or {}).get("has_photos")     else "not_present")
        _merge_overlay("storyboard_uploaded", "validated" if (scene_row or {}).get("has_storyboard") else "not_present")
        _merge_overlay("encoded_uploaded",    "not_present")

        if has_videos and video_count == 0:
            target = "bg_edit_uploaded" if not is_solo_like else "solo_uploaded"
            if target in assets:
                assets[target].validity.append(
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
        try:
            budget_rates = _load_budget_rates()
        except Exception:
            budget_rates = {}

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
            # Pre-match each scene so we can bulk-load the overlay
            matched: list[tuple[dict, str, str, Optional[dict]]] = []
            for it in items[:3]:
                studio = (it.get("studio") or "").strip()
                scene_type = (it.get("scene_type") or "BG").strip() or "BG"
                scene_row = _match_scene_row(conn, studio, female, sd_obj)
                matched.append((it, studio, scene_type, scene_row))

            overlay_ids = [sr.get("id") for _, _, _, sr in matched if sr and sr.get("id")]
            overlay_map = _load_asset_state_overlay(conn, overlay_ids)

            for position, (it, studio, scene_type, scene_row) in enumerate(matched, start=1):
                scene_id = (scene_row or {}).get("id") or ""
                assets = _scene_state(
                    scene_row, it, scene_type,
                    legal_run_status, legal_run_v,
                    legal_docs_status, legal_docs_v,
                    call_sheet_status, call_sheet_v,
                    checked_at,
                    asset_overlay=overlay_map.get(scene_id),
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

            bgt = budget_rates.get((sd_iso, female.lower()), {})
            shoots.append(Shoot(
                shoot_id=shoot_id,
                shoot_date=sd_iso,
                female_talent=female,
                female_rate=bgt.get("female_rate"),
                male_talent=male,
                male_rate=bgt.get("male_rate"),
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


# ---------------------------------------------------------------------------
# SSE stream endpoint
# ---------------------------------------------------------------------------

@router.get("/stream")
async def stream_shoots(
    request: Request,
    token: Optional[str] = Query(default=None),
):
    """
    Server-Sent Events stream for the shoot board.

    Browsers connect via:
        new EventSource('/api/shoots/stream?token=<jwt>')

    The EventSource API cannot set custom headers, so the JWT is passed as a
    query parameter.  The same Google ID token validation that CurrentUser
    performs is applied here via validate_sse_token.

    Event format:
        data: <JSON array of Shoot objects>\\n\\n

    A heartbeat comment is sent every 15 s to keep the connection alive
    through proxies and load-balancers that close idle connections.
    """
    user = await validate_sse_token(request, token)

    async def _generator() -> AsyncGenerator[str, None]:
        last_hash = ""
        default_from, default_to = _default_window()
        try:
            while True:
                try:
                    shoots = _load_shoots_window(default_from, default_to, include_cancelled=False)
                    payload = json.dumps(
                        [s.model_dump() for s in shoots],
                        default=str,
                    )
                    current_hash = hashlib.sha256(payload.encode()).hexdigest()
                    if current_hash != last_hash:
                        last_hash = current_hash
                        yield f"data: {payload}\n\n"
                except Exception as exc:
                    _log.warning("shoots SSE: error building shoots: %s", exc)

                # Heartbeat comment — keeps connection alive, ignored by EventSource
                yield ": heartbeat\n\n"
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            # Client disconnected cleanly
            _log.debug("shoots SSE: client disconnected (%s)", user.get("name"))

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


# ---------------------------------------------------------------------------
# Legal docs endpoint — appended patch
# ---------------------------------------------------------------------------

class LegalDocFile(BaseModel):
    name: str
    web_view_link: str
    mime_type: str = ""


class LegalDocsResult(BaseModel):
    folder_url: Optional[str] = None
    folder_name: Optional[str] = None
    files: list[LegalDocFile] = []
    w9_name: Optional[str] = None


def _extract_w9_name(pdf_bytes: bytes, pdf_id: str = "", rw_token: str = "") -> str:
    """Extract Line 1 (legal name) from a W9 PDF.

    Tries in order:
    1. Drive OCR (copy-as-doc) — works on flattened/scanned PDFs
    2. pypdf AcroForm fields — works on electronically-filled PDFs
    3. pypdf text extraction — last resort for simple text-based PDFs
    """
    # ── 1. Drive OCR (most reliable for flattened forms) ─────────────────────
    if pdf_id and rw_token:
        try:
            ocr_text = _ocr_pdf_id(pdf_id, rw_token)
            name = _parse_w9_ocr_name(ocr_text)
            if name:
                return name
        except Exception as ocr_exc:
            _log.warning("w9 ocr failed: %s", ocr_exc)

    # ── 2. pypdf AcroForm fields (electronically-filled PDFs) ────────────────
    import io
    import re as _re
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        fields = reader.get_fields() or {}
        if fields:
            for key in sorted(fields.keys()):
                field = fields[key]
                val = field.get("/V", "")
                if not isinstance(val, str):
                    continue
                val = val.strip()
                # Skip empty, checkbox states (NameObject "/Yes"/"/Off"), booleans, digits
                if (not val or len(val) < 2 or val.startswith("/")
                        or val in ("Yes", "Off", "On", "True", "False")
                        or val.isdigit()):
                    continue
                return val
        # ── 3. Text extraction fallback ───────────────────────────────────────
        if reader.pages:
            text = reader.pages[0].extract_text() or ""
            m = _re.search(r"Name\s*\(as shown[^\n]*\)\s*\n([^\n]+)", text, _re.IGNORECASE)
            if m:
                return m.group(1).strip()
    except Exception:
        pass
    return ""


def _get_shoot_legal_docs(shoot_date: date, female: str, male: str) -> LegalDocsResult:
    """Walk Drive legal folder hierarchy and return files for this shoot."""
    import urllib.parse
    import urllib.request
    import json

    token = _get_drive_token()
    if not token:
        return LegalDocsResult()

    try:
        def drive_get(url: str) -> dict:
            r2 = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(r2, timeout=10) as resp:
                return json.loads(resp.read())

        month_name, _ = _legal_folder_key(shoot_date, female, male)
        date_prefix = shoot_date.strftime("%m%d%y") + "-"
        female_slug = female.replace(" ", "").lower()
        male_slug = male.replace(" ", "").lower() if male else ""

        def _folder_matches(fname: str) -> bool:
            name_lower = fname.replace("-", "").lower()
            if not fname.startswith(date_prefix):
                return False
            if female_slug and female_slug not in name_lower:
                return False
            if male_slug and male_slug not in name_lower:
                return False
            return True

        # Step 1: find the month folder
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
        month_files = (res or {}).get("files") or []
        if not month_files:
            return LegalDocsResult()
        month_id = month_files[0]["id"]

        # Step 2: list shoot folders in the month folder, find the one for this shoot
        q = f"'{month_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        res = drive_get(
            "https://www.googleapis.com/drive/v3/files"
            f"?q={urllib.parse.quote(q)}&fields=files(id,name)&pageSize=1000"
        )
        for folder in (res or {}).get("files") or []:
            fname: str = folder.get("name", "")
            fid: str = folder.get("id", "")
            if not _folder_matches(fname):
                continue

            # Step 3: list files in the shoot folder
            q2 = f"'{fid}' in parents and trashed=false"
            res2 = drive_get(
                "https://www.googleapis.com/drive/v3/files"
                f"?q={urllib.parse.quote(q2)}&fields=files(id,name,mimeType,webViewLink)&pageSize=1000"
            )
            raw_files = res2.get("files") or []
            files = [
                LegalDocFile(
                    name=c.get("name", ""),
                    web_view_link=c.get(
                        "webViewLink",
                        f"https://drive.google.com/file/d/{c.get('id', '')}/view",
                    ),
                    mime_type=c.get("mimeType", ""),
                )
                for c in raw_files
                if c.get("name")
            ]

            # Extract name from the W9 PDF (AcroForm fields, for electronically-filled PDFs)
            w9_name: Optional[str] = None
            w9_entries = [c for c in raw_files if c.get("mimeType") == "application/pdf"]
            if w9_entries:
                try:
                    w9_id = w9_entries[0]["id"]
                    dl_req = urllib.request.Request(
                        f"https://www.googleapis.com/drive/v3/files/{w9_id}?alt=media",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    with urllib.request.urlopen(dl_req, timeout=15) as dl_resp:
                        pdf_bytes = dl_resp.read()
                    w9_name = _extract_w9_name(pdf_bytes, pdf_id=w9_id, rw_token=_get_drive_rw_token() or "")
                except Exception as w9_exc:
                    _log.warning("w9 name extraction failed: %s", w9_exc)

            return LegalDocsResult(
                folder_url=f"https://drive.google.com/drive/folders/{fid}",
                folder_name=fname,
                files=files,
                w9_name=w9_name or None,
            )

        return LegalDocsResult()
    except Exception as exc:
        _log.warning("legal docs lookup failed: %s", exc)
        return LegalDocsResult()


@router.get("/{shoot_id}/legal-docs", response_model=LegalDocsResult)
async def get_shoot_legal_docs(shoot_id: str, user: CurrentUser):
    """Return Drive legal-folder URL and file list for a shoot."""
    shoot = _find_shoot(shoot_id)
    shoot_date_obj = _parse_shoot_date(shoot.shoot_date)
    if not shoot_date_obj:
        return LegalDocsResult()
    return _get_shoot_legal_docs(shoot_date_obj, shoot.female_talent, shoot.male_talent)
