"""
Compliance router — iPad-based talent documentation workflow.

Handles the pre-production legal compliance package for BG shoots:
  1. Get BG shoots for a date with Drive folder / photo status
  2. Prepare Drive folder (create if missing, copy templates, fill dates)
  3. Upload ID + verification photos to Drive (and optionally MEGA)
  4. Sync completed package to MEGA Grail/{studio}/{scene_id}/Legal/

Routes:
  GET  /api/compliance/shoots?date=YYYY-MM-DD    — BG shoots for a date
  POST /api/compliance/shoots/{id}/prepare        — ensure Drive folder + PDFs
  POST /api/compliance/shoots/{id}/photos         — upload photos (multipart)
  POST /api/compliance/shoots/{id}/mega-sync      — copy everything to MEGA
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import base64
import re

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from api.auth import CurrentUser
from api.config import get_settings
from api.compliance_db import (
    SignedTalent,
    contract_version,
    get_signed_pdf_path,
    is_shoot_complete,
    list_signed_talents,
    upsert_signature,
)
from api.compliance_pdf import render_agreement_pdf
from api.routers.shoots import (
    LEGAL_ROOT_FOLDER,
    _get_drive_rw_token,
    _get_drive_token,
    _load_shoots_window,
    _parse_shoot_date,
)

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compliance", tags=["compliance"])

# ─── Drive template IDs (mirrored from legal_docs_run.mjs) ───────────────────

FEMALE_TPL_ID = "1ey06iXodjkOhK6BK-Q9nsQ2UtiaAo5Oc"
MALE_TPLS: dict[str, str] = {
    "MikeMancini":  "1xlbezjCXjTkxBwyI-QdaS4JGyCeESSc-",
    "JaydenMarcos": "13qNXBqrygLrcnMsKI9sZy_3XOYP0Gjok",
    "DannySteele":  "1PxyfZnZZqeOe4DiqNN7AmeQuNcrfXc2j",
}
DATE_FIELDS = {"Date 1", "Date 2", "Custom Field 13"}

_RCLONE = r"C:\Users\andre\rclone.exe"
_RCLONE_CONF = r"C:\Users\andre\.config\rclone\rclone.conf"

STUDIO_TO_MEGA: dict[str, str] = {
    "FuckPassVR": "FPVR",
    "VRHush":     "VRH",
    "VRAllure":   "VRA",
    "NaughtyJOI": "NNJOI",
}


# ─── Response models ──────────────────────────────────────────────────────────

class ComplianceShoot(BaseModel):
    shoot_id: str
    shoot_date: str
    female_talent: str
    male_talent: str
    drive_folder_url: Optional[str] = None
    drive_folder_id: Optional[str] = None
    drive_folder_name: Optional[str] = None
    pdfs_ready: bool = False
    photos_uploaded: int = 0
    is_complete: bool = False
    scene_id: str = ""
    studio: str = ""


class PrepareResult(BaseModel):
    folder_id: str
    folder_url: str
    folder_name: str
    female_pdf_id: str = ""
    male_pdf_id: str = ""
    male_known: bool = False
    dates_filled: bool = False
    message: str = ""


class PhotoUploadResult(BaseModel):
    uploaded: list[str] = []
    drive_file_ids: list[str] = []
    mega_paths: list[str] = []
    errors: list[str] = []


class InitUploadFile(BaseModel):
    filename: str
    mime_type: str = "image/jpeg"


class UploadSession(BaseModel):
    filename: str
    upload_url: str


class ConfirmUploadsRequest(BaseModel):
    filenames: list[str]
    file_ids: list[str] = []


class MegaSyncResult(BaseModel):
    status: str  # ok | error
    mega_path: str = ""
    files_copied: int = 0
    message: str = ""


class FillFormRequest(BaseModel):
    talent: str          # "female" | male stage name e.g. "MikeMancini"
    legal_name: str
    stage_name: str = ""
    dob: str = ""        # YYYY-MM-DD from date input
    place_of_birth: str = ""
    street_address: str = ""
    city_state_zip: str = ""
    phone: str = ""
    email: str = ""
    id1_type: str = ""
    id1_number: str = ""
    id2_type: str = ""
    id2_number: str = ""
    signature: str = ""
    company_name: str = ""


# ─── Hub-only signing flow (TKT-0150) ────────────────────────────────────────


class SignRequest(BaseModel):
    """Single payload from the iPad form. Drives the new compliance flow:
    captures every field that lives on the legacy Drive PDF templates plus a
    drawn signature image (base64-encoded PNG)."""
    talent_role: str = Field(..., pattern=r"^(female|male)$")
    talent_slug: str
    talent_display: str

    # W-9 (page 1 of legacy template)
    legal_name: str
    business_name: str = ""
    tax_classification: str = Field("individual", pattern=r"^(individual|c_corp|s_corp|partnership|trust_estate|llc|other)$")
    llc_class: str = ""              # 'C' | 'S' | 'P' (only used when tax_classification='llc')
    other_classification: str = ""
    exempt_payee_code: str = ""
    fatca_code: str = ""
    tin_type: str = Field("ssn", pattern=r"^(ssn|ein)$")
    tin: str                          # raw digits, no formatting

    # 2257 Performer Names Disclosure (page 6 of legacy template)
    dob: str                          # YYYY-MM-DD
    place_of_birth: str
    street_address: str
    city_state_zip: str
    phone: str
    email: str
    id1_type: str
    id1_number: str
    id2_type: str = ""
    id2_number: str = ""
    stage_names: str = ""
    professional_names: str = ""
    nicknames_aliases: str = ""
    previous_legal_names: str = ""

    # Drawn signature, sent as a base64 data-URL or raw base64 PNG
    signature_png: str


class SignResult(BaseModel):
    shoot_id: str
    talent_role: str
    talent_slug: str
    signed_at: str
    pdf_local_path: str
    pdf_mega_path: str
    contract_version: str


class SignedSummary(BaseModel):
    """Per-talent summary returned by /shoots/{id}/signed for the UI."""
    talent_role: str
    talent_slug: str
    talent_display: str
    legal_name: str
    signed_at: str
    pdf_mega_path: str


# ─── Drive helpers ────────────────────────────────────────────────────────────


def _get_drive_oauth_token() -> Optional[str]:
    """
    Return a fresh access token derived from vr_oauth_token.json.

    The service account has 0 storage quota, so any file the SA *creates*
    in My Drive fails with 403 storageQuotaExceeded. Photo uploads must use
    the user's OAuth credentials so files are owned by — and consume the
    quota of — the configured Google user. Same pattern as call_sheets.py.
    """
    from api.config import get_settings
    try:
        token_path = get_settings().base_dir / "vr_oauth_token.json"
        if not token_path.exists():
            return None
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
            return json.loads(r.read()).get("access_token")
    except Exception as exc:
        _log.warning("drive oauth token fetch failed: %s", exc)
        return None


def _drive_json(url: str, token: str, method: str = "GET",
                body: Optional[bytes] = None,
                content_type: str = "application/json") -> dict:
    headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _find_or_create_folder(parent_id: str, name: str, token: str) -> str:
    q = (
        f"'{parent_id}' in parents and name={json.dumps(name)} "
        "and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    res = _drive_json(
        "https://www.googleapis.com/drive/v3/files"
        f"?q={urllib.parse.quote(q)}&fields=files(id,name)",
        token,
    )
    existing = (res or {}).get("files") or []
    if existing:
        return existing[0]["id"]
    body = json.dumps({
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }).encode()
    created = _drive_json(
        "https://www.googleapis.com/drive/v3/files",
        token, method="POST", body=body,
    )
    return created["id"]


def _copy_file(file_id: str, dest_folder_id: str, new_name: str, token: str) -> dict:
    body = json.dumps({"name": new_name, "parents": [dest_folder_id]}).encode()
    return _drive_json(
        f"https://www.googleapis.com/drive/v3/files/{file_id}/copy",
        token, method="POST", body=body,
    )


def _list_folder_files(folder_id: str, token: str) -> list[dict]:
    q = f"'{folder_id}' in parents and trashed=false"
    res = _drive_json(
        "https://www.googleapis.com/drive/v3/files"
        f"?q={urllib.parse.quote(q)}&fields=files(id,name,mimeType,webViewLink)&pageSize=1000",
        token,
    )
    return (res or {}).get("files") or []


def _create_resumable_session(folder_id: str, file_name: str, mime_type: str, token: str) -> str:
    """
    Create a Drive resumable-upload session.
    Returns the session URI (upload URL).  The caller — typically the browser —
    can PUT the file body directly to this URL with no Authorization header.
    The URI is valid for ~7 days and is pre-authorized via the service account.
    """
    metadata = json.dumps({"name": file_name, "parents": [folder_id]}).encode()
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/drive/v3/files"
        "?uploadType=resumable&fields=id",
        data=metadata,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": mime_type,
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        location = r.headers.get("Location", "")
    if not location:
        raise RuntimeError(f"Drive did not return a session URI for {file_name}")
    return location


def _upload_to_drive(folder_id: str, file_name: str,
                     file_bytes: bytes, mime_type: str, token: str) -> str:
    """Multipart upload to Drive. Returns new file ID.

    Raises with Drive's actual error reason on failure so the caller can
    surface it to the UI (otherwise urllib's default repr says only
    "HTTP Error 403: Forbidden", hiding the underlying cause).
    """
    boundary = b"ec_boundary_01"
    metadata = json.dumps({"name": file_name, "parents": [folder_id]}).encode()
    body = (
        b"--" + boundary + b"\r\n"
        b"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        + metadata + b"\r\n"
        b"--" + boundary + b"\r\n"
        b"Content-Type: " + mime_type.encode() + b"\r\n\r\n"
        + file_bytes + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/drive/v3/files"
        "?uploadType=multipart&fields=id&supportsAllDrives=true",
        data=body, method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary.decode()}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read()).get("id", "")
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
            err_json = json.loads(err_body)
            reason = (err_json.get("error") or {}).get("message") or err_body[:300]
        except Exception:
            reason = f"HTTP {exc.code}"
        raise RuntimeError(f"Drive {exc.code}: {reason}") from exc


def _format_dob(dob_iso: str) -> str:
    try:
        d = datetime.strptime(dob_iso, "%Y-%m-%d")
        return d.strftime("%b ") + str(d.day) + d.strftime(", %Y")
    except Exception:
        return dob_iso


def _fill_pdf_fields(pdf_bytes: bytes, fields: dict[str, str]) -> bytes:
    """Fill arbitrary text/checkbox fields in a PDF."""
    try:
        import pypdf
        from pypdf.generic import NameObject, create_string_object
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        writer = pypdf.PdfWriter()
        writer.append(reader)
        for page in writer.pages:
            if "/Annots" not in page:
                continue
            for annot in page["/Annots"]:
                obj = annot.get_object()
                field_name = obj.get("/T")
                if field_name not in fields:
                    continue
                value = fields[field_name]
                field_type = str(obj.get("/FT", ""))
                if field_type == "/Btn":
                    name_val = NameObject(value) if value.startswith("/") else NameObject("/Off")
                    obj.update({
                        NameObject("/V"): name_val,
                        NameObject("/AS"): name_val,
                    })
                else:
                    obj.update({
                        NameObject("/V"):  create_string_object(value),
                        NameObject("/DV"): create_string_object(value),
                    })
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except Exception as exc:
        _log.warning("pdf fill failed: %s", exc)
        return pdf_bytes


def _map_form_to_pdf(req: "FillFormRequest", shoot_date_str: str) -> dict[str, str]:
    full_address = f"{req.street_address} {req.city_state_zip}".strip()
    dob_fmt = _format_dob(req.dob) if req.dob else ""
    return {
        "Custom Field 1":    req.legal_name,
        "Custom Field 2":    req.company_name,
        "Custom Checkbox 1": "/Yes",
        "Custom Field 7":    req.street_address,
        "Custom Field 9":    req.city_state_zip,
        "Custom Field 14":   req.legal_name,
        "Custom Field 16":   req.legal_name,
        "Custom Field 17":   req.stage_name,
        "Custom Field 18":   req.legal_name,
        "Custom Field 23":   req.legal_name,
        "Custom Field 24":   req.legal_name,
        "Custom Field 25":   dob_fmt,
        "Custom Field 26":   req.place_of_birth,
        "Custom Field 27":   full_address,
        "Custom Field 28":   req.id1_type,
        "Custom Field 29":   req.id1_number,
        "Custom Field 30":   req.id2_type,
        "Custom Field 31":   req.id2_number,
        "Custom Field 32":   req.phone,
        "Custom Field 33":   req.email,
        "Custom Field 34":   req.stage_name,
        "Custom Field 35":   req.stage_name,
        "Signature 1":       req.signature,
        "Signature 2":       req.signature,
        "Signature 3":       req.signature,
        "Date 1":            shoot_date_str,
        "Date 2":            shoot_date_str,
        "Custom Field 13":   shoot_date_str,
    }


def _fill_pdf_dates(pdf_bytes: bytes, today_str: str) -> bytes:
    try:
        import pypdf
        from pypdf.generic import NameObject, create_string_object
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        writer = pypdf.PdfWriter()
        writer.append(reader)
        for page in writer.pages:
            if "/Annots" not in page:
                continue
            for annot in page["/Annots"]:
                obj = annot.get_object()
                if obj.get("/T") in DATE_FIELDS:
                    obj.update({
                        NameObject("/V"):  create_string_object(today_str),
                        NameObject("/DV"): create_string_object(today_str),
                    })
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except Exception as exc:
        _log.warning("pdf date fill failed: %s", exc)
        return pdf_bytes


def _get_shoot_folder(
    shoot_date: date, female: str, male: str, token: str
) -> Optional[tuple[str, str]]:
    """Return (folder_id, folder_name) if Drive folder already exists."""
    month_name = shoot_date.strftime("%B")
    date_prefix = shoot_date.strftime("%m%d%y") + "-"
    female_slug = female.replace(" ", "").lower()
    male_slug = male.replace(" ", "").lower() if male else ""

    q = (
        f"'{LEGAL_ROOT_FOLDER}' in parents and name='{month_name}' "
        "and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    res = _drive_json(
        "https://www.googleapis.com/drive/v3/files"
        f"?q={urllib.parse.quote(q)}&fields=files(id,name)",
        token,
    )
    month_files = (res or {}).get("files") or []
    if not month_files:
        return None
    month_id = month_files[0]["id"]

    q2 = (
        f"'{month_id}' in parents "
        "and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    res2 = _drive_json(
        "https://www.googleapis.com/drive/v3/files"
        f"?q={urllib.parse.quote(q2)}&fields=files(id,name)&pageSize=1000",
        token,
    )
    for f in (res2 or {}).get("files") or []:
        fname: str = f.get("name", "")
        if not fname.startswith(date_prefix):
            continue
        name_lower = fname.replace("-", "").lower()
        if female_slug and female_slug not in name_lower:
            continue
        if male_slug and male_slug not in name_lower:
            continue
        return f["id"], fname
    return None


def _window() -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=60), today + timedelta(days=30)


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/shoots", response_model=list[ComplianceShoot])
async def list_compliance_shoots(
    user: CurrentUser,
    date: Optional[str] = Query(default=None),
):
    """Return BG shoots for a given date (default: today) with compliance status."""
    target_date_str = date or datetime.now(timezone.utc).date().isoformat()
    target_date = _parse_shoot_date(target_date_str)
    if target_date is None:
        raise HTTPException(status_code=400, detail="Invalid date")

    shoots = _load_shoots_window(target_date, target_date, include_cancelled=False)
    token = _get_drive_token()
    # Bulk-fetch DB-backed signatures so is_complete + pdfs_ready don't depend
    # on Drive folder presence (the Drive proxy false-positives the moment
    # prepare copies blank templates — see TKT-0150).
    signed_by_shoot = list_signed_talents([s.shoot_id for s in shoots])
    results: list[ComplianceShoot] = []

    for shoot in shoots:
        bg_scenes = [sc for sc in shoot.scenes if sc.scene_type.upper() in ("BG", "BGCP")]
        if not bg_scenes:
            continue

        primary = bg_scenes[0]
        scene_id = primary.scene_id or ""
        studio = primary.studio or ""

        folder_url = folder_id = folder_name = None
        photos_count = 0

        # Drive folder lookup is now PURELY for displaying the legacy folder
        # link in the UI. Completion comes from compliance_signatures.
        if token:
            shoot_date_obj = _parse_shoot_date(shoot.shoot_date)
            if shoot_date_obj:
                try:
                    info = _get_shoot_folder(
                        shoot_date_obj, shoot.female_talent, shoot.male_talent, token
                    )
                    if info:
                        folder_id, folder_name = info
                        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
                        files = _list_folder_files(folder_id, token)
                        photos_count = sum(
                            1 for f in files
                            if f.get("name", "").lower().endswith((".jpg", ".jpeg", ".png"))
                        )
                except Exception as exc:
                    _log.debug("compliance folder lookup: %s", exc)

        # Completion: prefer DB-backed signatures (new flow), fall back to the
        # legacy Drive-folder check so shoots completed via the old prepare/
        # fill-form path still show as complete during the cutover. Once the
        # Hub UI is fully rewired, the Drive fallback can be removed.
        signed = signed_by_shoot.get(shoot.shoot_id, [])
        signed_roles = {t.talent_role for t in signed}
        needed_roles = {"female", "male"} if shoot.male_talent else {"female"}
        if signed:
            is_complete = needed_roles.issubset(signed_roles)
            pdfs_ready = True
        else:
            # Legacy fallback — mirror the pre-TKT-0150 logic
            is_complete_legacy = False
            for sc in bg_scenes:
                for asset in sc.assets:
                    if asset.asset_type == "legal_docs_uploaded" and asset.status == "validated":
                        is_complete_legacy = True
            is_complete = is_complete_legacy
            # pdfs_ready ← legacy file-count check
            need_pdfs = 2 if shoot.male_talent else 1
            try:
                if folder_id and token:
                    files_for_pdf = _list_folder_files(folder_id, token)
                    pdfs_ready = sum(
                        1 for f in files_for_pdf
                        if f.get("name", "").lower().endswith(".pdf")
                    ) >= need_pdfs
                else:
                    pdfs_ready = False
            except Exception:
                pdfs_ready = False

        results.append(ComplianceShoot(
            shoot_id=shoot.shoot_id,
            shoot_date=shoot.shoot_date,
            female_talent=shoot.female_talent,
            male_talent=shoot.male_talent or "",
            drive_folder_url=folder_url,
            drive_folder_id=folder_id,
            drive_folder_name=folder_name,
            pdfs_ready=pdfs_ready,
            photos_uploaded=photos_count,
            is_complete=is_complete,
            scene_id=scene_id,
            studio=studio,
        ))

    return results


@router.post("/shoots/{shoot_id}/prepare", response_model=PrepareResult)
async def prepare_compliance(shoot_id: str, user: CurrentUser):
    """
    Ensure Drive legal folder exists, copy PDF templates, and fill
    date fields in the male PDF.
    """
    from_d, to_d = _window()
    shoots = _load_shoots_window(from_d, to_d, include_cancelled=False)
    shoot = next((s for s in shoots if s.shoot_id == shoot_id), None)
    if not shoot:
        raise HTTPException(status_code=404, detail="Shoot not found")

    shoot_date = _parse_shoot_date(shoot.shoot_date)
    if not shoot_date:
        raise HTTPException(status_code=400, detail="Invalid shoot date")

    female = shoot.female_talent.strip()
    male = (shoot.male_talent or "").strip()

    token = _get_drive_rw_token()
    if not token:
        raise HTTPException(status_code=503, detail="Drive credentials unavailable")

    # 1. Month folder
    month_name = shoot_date.strftime("%B")
    month_id = _find_or_create_folder(LEGAL_ROOT_FOLDER, month_name, token)

    # 2. Shoot folder
    date_code = shoot_date.strftime("%m%d%y")
    female_slug = female.replace(" ", "")
    male_slug = male.replace(" ", "")
    folder_name = f"{date_code}-{female_slug}" + (f"-{male_slug}" if male_slug else "")
    folder_id = _find_or_create_folder(month_id, folder_name, token)
    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"

    # 3. Existing files
    existing = _list_folder_files(folder_id, token)
    existing_lower = {f.get("name", "").lower() for f in existing}

    female_pdf_name = f"{female_slug}-{date_code}.pdf"
    male_pdf_name = f"{male_slug}-{date_code}.pdf" if male_slug else ""
    female_pdf_id = male_pdf_id = ""
    male_known = bool(male_slug and (male_slug in MALE_TPLS or male in MALE_TPLS))
    dates_filled = False

    # 4. Female PDF
    if female_pdf_name.lower() not in existing_lower:
        try:
            r = _copy_file(FEMALE_TPL_ID, folder_id, female_pdf_name, token)
            female_pdf_id = r.get("id", "")
        except Exception as exc:
            _log.warning("female PDF copy failed: %s", exc)
    else:
        for f in existing:
            if f.get("name", "").lower() == female_pdf_name.lower():
                female_pdf_id = f.get("id", "")
                break

    # 5. Male PDF (known templates only)
    if male_slug and male_pdf_name:
        male_tpl = MALE_TPLS.get(male_slug) or MALE_TPLS.get(male)
        if male_pdf_name.lower() not in existing_lower and male_tpl:
            try:
                r = _copy_file(male_tpl, folder_id, male_pdf_name, token)
                male_pdf_id = r.get("id", "")
            except Exception as exc:
                _log.warning("male PDF copy failed: %s", exc)
        elif male_pdf_name.lower() in existing_lower:
            for f in existing:
                if f.get("name", "").lower() == male_pdf_name.lower():
                    male_pdf_id = f.get("id", "")
                    break

    # 6. Fill dates in male PDF
    if male_pdf_id:
        try:
            today_str = shoot_date.strftime("%b %-d, %Y")
            dl = urllib.request.Request(
                f"https://www.googleapis.com/drive/v3/files/{male_pdf_id}?alt=media",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(dl, timeout=20) as resp:
                pdf_bytes = resp.read()
            filled = _fill_pdf_dates(pdf_bytes, today_str)
            patch = urllib.request.Request(
                f"https://www.googleapis.com/upload/drive/v3/files/{male_pdf_id}?uploadType=media",
                data=filled, method="PATCH",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/pdf"},
            )
            with urllib.request.urlopen(patch, timeout=30) as r:
                r.read()
            dates_filled = True
        except Exception as exc:
            _log.warning("male date fill failed: %s", exc)

    parts = []
    if female_pdf_id:
        parts.append(f"{female_slug} PDF ready")
    if male_pdf_id:
        parts.append(f"{male_slug} PDF {'+ dates ' if dates_filled else ''}ready")
    elif male_slug and not male_known:
        parts.append(f"⚠ {male_slug} not on file — upload manually")

    return PrepareResult(
        folder_id=folder_id,
        folder_url=folder_url,
        folder_name=folder_name,
        female_pdf_id=female_pdf_id,
        male_pdf_id=male_pdf_id,
        male_known=male_known,
        dates_filled=dates_filled,
        message="; ".join(parts) or "Folder ready",
    )


@router.post("/shoots/{shoot_id}/photos", response_model=PhotoUploadResult)
async def upload_photos(
    shoot_id: str,
    user: CurrentUser,
    files: list[UploadFile] = File(...),
    labels: list[str] = Form(default=[]),
    scene_id: str = Form(default=""),
    studio: str = Form(default=""),
):
    """
    Upload ID / verification photos to the Drive legal folder.
    Also copies to MEGA Legal/ subfolder if scene_id + studio are provided.
    """
    from_d, to_d = _window()
    shoots = _load_shoots_window(from_d, to_d, include_cancelled=False)
    shoot = next((s for s in shoots if s.shoot_id == shoot_id), None)
    if not shoot:
        raise HTTPException(status_code=404, detail="Shoot not found")

    shoot_date = _parse_shoot_date(shoot.shoot_date)
    if not shoot_date:
        raise HTTPException(status_code=400, detail="Invalid shoot date")

    # Photo uploads use the user's OAuth token so files are owned by — and
    # consume the quota of — the configured Google user. Service accounts
    # have 0 storage, so SA-owned multipart uploads to My Drive folders fail
    # with 403 storageQuotaExceeded. Folder lookup still works with either
    # token, so we fall back to the SA token if vr_oauth_token.json is missing.
    upload_token = _get_drive_oauth_token()
    lookup_token = upload_token or _get_drive_rw_token()
    if not lookup_token:
        raise HTTPException(status_code=503, detail="Drive credentials unavailable")
    if not upload_token:
        upload_token = lookup_token

    folder_info = _get_shoot_folder(
        shoot_date, shoot.female_talent, shoot.male_talent, lookup_token
    )
    if not folder_info:
        raise HTTPException(
            status_code=404,
            detail="Drive folder not found — tap Prepare Docs first",
        )
    folder_id, _ = folder_info

    # ── Build (label, content, mime) tuples for every file ───────────────
    # Read all uploads concurrently — multipart bodies are already buffered
    # by Starlette so these awaits are fast memory reads, not network IO.
    async def _read_one(i: int, upload_file: UploadFile):
        label = labels[i] if i < len(labels) else (upload_file.filename or f"photo_{i + 1}.jpg")
        if not any(label.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".mp4", ".mov", ".webm")):
            label += ".jpg"
        content = await upload_file.read()
        mime = upload_file.content_type or "image/jpeg"
        return label, content, mime

    file_tuples = await asyncio.gather(*[_read_one(i, f) for i, f in enumerate(files)])

    # ── Upload to Drive in parallel (thread pool — Drive HTTP is blocking) ─
    async def _drive_one(label: str, content: bytes, mime: str):
        return await asyncio.to_thread(_upload_to_drive, folder_id, label, content, mime, upload_token)

    drive_results = await asyncio.gather(
        *[_drive_one(label, content, mime) for label, content, mime in file_tuples],
        return_exceptions=True,
    )

    uploaded: list[str] = []
    drive_file_ids: list[str] = []
    mega_paths: list[str] = []
    errors: list[str] = []

    for (label, content, _mime), result in zip(file_tuples, drive_results):
        if isinstance(result, Exception):
            _log.warning("photo upload failed %s: %s", label, result)
            errors.append(f"{label}: {result}")
        else:
            uploaded.append(label)
            drive_file_ids.append(result)

    # ── MEGA sync (single rclone call, only when caller requests it) ──────
    if scene_id and studio and uploaded:
        tmp_dir = tempfile.mkdtemp(prefix="compliance_")
        try:
            for (label, content, _mime) in file_tuples:
                if label in uploaded:
                    (Path(tmp_dir) / label).write_bytes(content)
            mega_studio = STUDIO_TO_MEGA.get(studio, studio)
            mega_path = f"mega:/Grail/{mega_studio}/{scene_id}/Legal/"
            try:
                r = await asyncio.to_thread(
                    subprocess.run,
                    [_RCLONE, "--config", _RCLONE_CONF, "copy", tmp_dir, mega_path],
                    capture_output=True, text=True, timeout=120,
                )
                if r.returncode == 0:
                    mega_paths = [f"{mega_path}{n}" for n in uploaded]
                else:
                    errors.append(f"MEGA: {r.stderr[:200]}")
            except Exception as exc:
                errors.append(f"MEGA: {exc}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return PhotoUploadResult(
        uploaded=uploaded,
        drive_file_ids=drive_file_ids,
        mega_paths=mega_paths,
        errors=errors,
    )


@router.post("/shoots/{shoot_id}/mega-sync", response_model=MegaSyncResult)
async def mega_sync(
    shoot_id: str,
    user: CurrentUser,
    scene_id: str = Form(...),
    studio: str = Form(...),
):
    """
    Download every file from the Drive legal folder and push to
    MEGA Grail/{studio}/{scene_id}/Legal/.
    """
    from_d, to_d = _window()
    shoots = _load_shoots_window(from_d, to_d, include_cancelled=False)
    shoot = next((s for s in shoots if s.shoot_id == shoot_id), None)
    if not shoot:
        raise HTTPException(status_code=404, detail="Shoot not found")

    shoot_date = _parse_shoot_date(shoot.shoot_date)
    if not shoot_date:
        raise HTTPException(status_code=400, detail="Invalid shoot date")

    token = _get_drive_rw_token()
    if not token:
        raise HTTPException(status_code=503, detail="Drive credentials unavailable")

    folder_info = _get_shoot_folder(
        shoot_date, shoot.female_talent, shoot.male_talent, token
    )
    if not folder_info:
        raise HTTPException(status_code=404, detail="Drive folder not found")
    folder_id, _ = folder_info

    tmp_dir = tempfile.mkdtemp(prefix="compliance_sync_")
    try:
        files = _list_folder_files(folder_id, token)
        downloaded = 0
        for f in files:
            name = f.get("name", "")
            fid = f.get("id", "")
            if not name or not fid:
                continue
            try:
                dl = urllib.request.Request(
                    f"https://www.googleapis.com/drive/v3/files/{fid}?alt=media",
                    headers={"Authorization": f"Bearer {token}"},
                )
                with urllib.request.urlopen(dl, timeout=30) as resp:
                    (Path(tmp_dir) / name).write_bytes(resp.read())
                downloaded += 1
            except Exception as exc:
                _log.warning("sync download failed %s: %s", name, exc)

        mega_studio = STUDIO_TO_MEGA.get(studio, studio)
        mega_path = f"mega:/Grail/{mega_studio}/{scene_id}/Legal/"
        r = subprocess.run(
            [_RCLONE, "--config", _RCLONE_CONF, "copy", tmp_dir, mega_path],
            capture_output=True, text=True, timeout=300,
        )
        if r.returncode == 0:
            return MegaSyncResult(
                status="ok",
                mega_path=mega_path,
                files_copied=downloaded,
                message=f"Copied {downloaded} file(s) to MEGA",
            )
        return MegaSyncResult(
            status="error",
            mega_path=mega_path,
            message=r.stderr[:300] or "rclone error",
        )
    except Exception as exc:
        return MegaSyncResult(status="error", message=str(exc))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/shoots/{shoot_id}/pdf")
async def get_filled_pdf(
    shoot_id: str,
    user: CurrentUser,
    talent: str = Query(...),
):
    """Serve the agreement PDF for a talent.

    Preferred source: `pdf_local_path` from `compliance_signatures` (written
    by the new /sign flow). Falls back to the legacy Drive folder so the
    existing prepare/fill-form path keeps working until the Hub UI is
    rewired to the new endpoints."""
    from fastapi.responses import Response as FastAPIResponse

    talent_slug = talent.replace(" ", "")

    # 1. New flow — DB-backed local PDF
    pdf_path = (
        get_signed_pdf_path(shoot_id, "female", talent_slug)
        or get_signed_pdf_path(shoot_id, "male", talent_slug)
    )
    if pdf_path:
        p = Path(pdf_path)
        if p.exists():
            return FastAPIResponse(
                content=p.read_bytes(),
                media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename={p.name}"},
            )

    # 2. Legacy fallback — Drive folder (the old fill-form path writes here)
    from_d, to_d = _window()
    shoots = _load_shoots_window(from_d, to_d, include_cancelled=False)
    shoot = next((s for s in shoots if s.shoot_id == shoot_id), None)
    if not shoot:
        raise HTTPException(status_code=404, detail="Shoot not found")

    shoot_date = _parse_shoot_date(shoot.shoot_date)
    if not shoot_date:
        raise HTTPException(status_code=400, detail="Invalid shoot date")

    token = _get_drive_token()
    if not token:
        raise HTTPException(status_code=404, detail="Talent has not signed yet")

    folder_info = _get_shoot_folder(
        shoot_date, shoot.female_talent, shoot.male_talent, token
    )
    if not folder_info:
        raise HTTPException(status_code=404, detail="Talent has not signed yet")
    folder_id, _ = folder_info
    files = _list_folder_files(folder_id, token)
    date_code = shoot_date.strftime("%m%d%y")
    pdf_name = f"{talent_slug}-{date_code}.pdf"
    pdf_file = next(
        (f for f in files if f.get("name", "").lower() == pdf_name.lower()), None
    )
    if not pdf_file:
        raise HTTPException(status_code=404, detail=f"PDF not found: {pdf_name}")

    dl_req = urllib.request.Request(
        f"https://www.googleapis.com/drive/v3/files/{pdf_file['id']}?alt=media",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(dl_req, timeout=30) as resp:
        pdf_bytes = resp.read()
    return FastAPIResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={pdf_name}"},
    )


@router.post("/shoots/{shoot_id}/fill-form", response_model=PrepareResult)
async def fill_form(shoot_id: str, user: CurrentUser, req: FillFormRequest):
    """
    Generate a filled PDF from hub form data and save it to the Drive legal folder.
    Works for female talent (uses female template) and unknown male talent.
    Known male talent should use the prepare endpoint instead.
    """
    from_d, to_d = _window()
    shoots = _load_shoots_window(from_d, to_d, include_cancelled=False)
    shoot = next((s for s in shoots if s.shoot_id == shoot_id), None)
    if not shoot:
        raise HTTPException(status_code=404, detail="Shoot not found")

    shoot_date = _parse_shoot_date(shoot.shoot_date)
    if not shoot_date:
        raise HTTPException(status_code=400, detail="Invalid shoot date")

    token = _get_drive_rw_token()
    if not token:
        raise HTTPException(status_code=503, detail="Drive credentials unavailable")

    # Select template: known males use their stored template; everyone else uses female template
    if req.talent == "female":
        tpl_id = FEMALE_TPL_ID
        talent_name = shoot.female_talent.strip()
    else:
        tpl_id = MALE_TPLS.get(req.talent) or FEMALE_TPL_ID
        talent_name = req.talent

    # Ensure Drive folder exists
    month_name = shoot_date.strftime("%B")
    month_id = _find_or_create_folder(LEGAL_ROOT_FOLDER, month_name, token)
    date_code = shoot_date.strftime("%m%d%y")
    female_slug = shoot.female_talent.strip().replace(" ", "")
    male_slug = (shoot.male_talent or "").strip().replace(" ", "")
    folder_name = f"{date_code}-{female_slug}" + (f"-{male_slug}" if male_slug else "")
    folder_id = _find_or_create_folder(month_id, folder_name, token)
    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"

    # Download template
    dl_req = urllib.request.Request(
        f"https://www.googleapis.com/drive/v3/files/{tpl_id}?alt=media",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(dl_req, timeout=30) as resp:
        pdf_bytes = resp.read()

    # Fill all fields
    date_str = shoot_date.strftime("%b ") + str(shoot_date.day) + shoot_date.strftime(", %Y")
    field_values = _map_form_to_pdf(req, date_str)
    filled = _fill_pdf_fields(pdf_bytes, field_values)

    # Upload or update in Drive folder
    talent_slug = talent_name.replace(" ", "")
    pdf_name = f"{talent_slug}-{date_code}.pdf"
    existing = _list_folder_files(folder_id, token)
    existing_file = next(
        (f for f in existing if f.get("name", "").lower() == pdf_name.lower()), None
    )

    if existing_file:
        patch = urllib.request.Request(
            f"https://www.googleapis.com/upload/drive/v3/files/{existing_file['id']}?uploadType=media",
            data=filled, method="PATCH",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/pdf"},
        )
        with urllib.request.urlopen(patch, timeout=30) as r:
            r.read()
        pdf_id = existing_file["id"]
    else:
        pdf_id = _upload_to_drive(folder_id, pdf_name, filled, "application/pdf", token)

    is_female = req.talent == "female"
    return PrepareResult(
        folder_id=folder_id,
        folder_url=folder_url,
        folder_name=folder_name,
        female_pdf_id=pdf_id if is_female else "",
        male_pdf_id=pdf_id if not is_female else "",
        male_known=req.talent in MALE_TPLS,
        dates_filled=True,
        message=f"{talent_slug} PDF saved to Drive",
    )


# ─── Direct-to-Drive upload endpoints ────────────────────────────────────────
# Instead of routing file bytes through this server, the browser gets a
# pre-authorized Drive resumable-session URL and uploads directly to Google.
# This eliminates the double-hop: Browser→Server→Drive becomes Browser→Drive.

@router.post("/shoots/{shoot_id}/photos/init-uploads", response_model=list[UploadSession])
async def init_photo_uploads(
    shoot_id: str,
    user: CurrentUser,
    files: list[InitUploadFile],
):
    """
    Create Drive resumable-upload sessions for a list of files.
    Returns one upload_url per file; the browser PUTs each file directly
    to that URL (no Authorization header needed — session is pre-authorized).
    """
    from_d, to_d = _window()
    shoots = _load_shoots_window(from_d, to_d, include_cancelled=False)
    shoot = next((s for s in shoots if s.shoot_id == shoot_id), None)
    if not shoot:
        raise HTTPException(status_code=404, detail="Shoot not found")

    shoot_date = _parse_shoot_date(shoot.shoot_date)
    if not shoot_date:
        raise HTTPException(status_code=400, detail="Invalid shoot date")

    token = _get_drive_rw_token()
    if not token:
        raise HTTPException(status_code=503, detail="Drive credentials unavailable")

    folder_info = _get_shoot_folder(
        shoot_date, shoot.female_talent, shoot.male_talent, token
    )
    if not folder_info:
        raise HTTPException(
            status_code=404,
            detail="Drive folder not found — tap Prepare Docs first",
        )
    folder_id, _ = folder_info

    # Create all sessions concurrently (each is a small metadata-only request)
    async def _init_one(f: InitUploadFile) -> UploadSession:
        filename = f.filename
        if not any(filename.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".mp4", ".mov", ".webm")):
            filename += ".jpg"
        upload_url = await asyncio.to_thread(
            _create_resumable_session, folder_id, filename, f.mime_type, token
        )
        return UploadSession(filename=filename, upload_url=upload_url)

    sessions = await asyncio.gather(*[_init_one(f) for f in files], return_exceptions=True)

    results: list[UploadSession] = []
    for f, session in zip(files, sessions):
        if isinstance(session, Exception):
            _log.error("init upload session failed %s: %s", f.filename, session)
            raise HTTPException(status_code=502, detail=f"Could not create session for {f.filename}: {session}")
        results.append(session)  # type: ignore[arg-type]
    return results


@router.post("/shoots/{shoot_id}/photos/confirm-uploads", response_model=PhotoUploadResult)
async def confirm_photo_uploads(
    shoot_id: str,
    user: CurrentUser,
    body: ConfirmUploadsRequest,
):
    """
    Called by the browser after direct Drive uploads complete.
    Records the uploaded filenames so photos_uploaded count stays accurate.
    """
    # Validation: shoot must exist
    from_d, to_d = _window()
    shoots = _load_shoots_window(from_d, to_d, include_cancelled=False)
    shoot = next((s for s in shoots if s.shoot_id == shoot_id), None)
    if not shoot:
        raise HTTPException(status_code=404, detail="Shoot not found")

    return PhotoUploadResult(
        uploaded=body.filenames,
        drive_file_ids=body.file_ids,
        mega_paths=[],
        errors=[],
    )


# ─── Hub-only signing flow (TKT-0150) ────────────────────────────────────────
# These endpoints replace prepare/fill-form. The Hub renders the contract
# verbatim, captures a drawn signature, posts here. We persist to
# compliance_signatures, render our own PDF, push it to MEGA (no Drive).


_SIG_DATA_URL_RE = re.compile(r"^data:image/png;base64,(.+)$", re.IGNORECASE)


def _decode_signature_png(payload: str) -> bytes:
    """Accept either a data: URL or raw base64 PNG, return the PNG bytes."""
    if not payload:
        raise HTTPException(status_code=400, detail="signature_png required")
    m = _SIG_DATA_URL_RE.match(payload)
    raw_b64 = m.group(1) if m else payload
    try:
        b = base64.b64decode(raw_b64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="signature_png is not valid base64")
    if not b.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=400, detail="signature_png must be a PNG")
    return b


def _signature_dir() -> Path:
    """Local on-disk storage for raw signature PNGs (audit trail)."""
    p = Path(get_settings().base_dir) / "compliance_signatures"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _legal_pdf_dir() -> Path:
    """Local on-disk storage for generated agreement PDFs (pre-MEGA push)."""
    p = Path(get_settings().base_dir) / "compliance_pdfs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _push_to_mega(local: Path, remote: str) -> Optional[str]:
    """copyto local → mega path; returns stderr on failure, None on success."""
    try:
        r = subprocess.run(
            [_RCLONE, "--config", _RCLONE_CONF, "copyto", str(local), remote],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0:
            return None
        return (r.stderr or "rclone failed")[:300]
    except Exception as exc:
        return str(exc)


@router.post("/shoots/{shoot_id}/sign", response_model=SignResult)
async def sign_shoot(shoot_id: str, user: CurrentUser, request: Request, body: SignRequest):
    """
    End-to-end Hub signing flow:
      1. Validate shoot + talent role
      2. Save the drawn signature PNG to disk (audit trail)
      3. Render our own agreement PDF embedding the signature
      4. Persist every field + audit metadata to compliance_signatures
      5. Push the PDF to MEGA Grail/{Studio}/{scene_id}/Legal/
      6. Return paths so the UI can link to the saved PDF
    """
    from_d, to_d = _window()
    shoots = _load_shoots_window(from_d, to_d, include_cancelled=False)
    shoot = next((s for s in shoots if s.shoot_id == shoot_id), None)
    if not shoot:
        raise HTTPException(status_code=404, detail="Shoot not found")

    # Pick the BG scene we'll attach this signature to
    bg_scenes = [sc for sc in shoot.scenes if sc.scene_type.upper() in ("BG", "BGCP")]
    if not bg_scenes:
        raise HTTPException(status_code=400, detail="Shoot has no BG/BGCP scene")
    primary = bg_scenes[0]
    scene_id = primary.scene_id or ""
    studio   = primary.studio or ""

    # Cross-check talent identity against the shoot record
    if body.talent_role == "female":
        expected = shoot.female_talent.replace(" ", "")
    else:
        expected = (shoot.male_talent or "").replace(" ", "")
    if not expected:
        raise HTTPException(status_code=400, detail=f"Shoot has no {body.talent_role} talent")
    if body.talent_slug.replace(" ", "").lower() != expected.lower():
        raise HTTPException(
            status_code=400,
            detail=f"talent_slug {body.talent_slug!r} does not match shoot's {body.talent_role}",
        )

    # 1. Save signature image to disk
    png_bytes = _decode_signature_png(body.signature_png)
    sig_path = _signature_dir() / f"{shoot.shoot_date}-{body.talent_slug}-{body.talent_role}.png"
    sig_path.write_bytes(png_bytes)

    # 2. Render PDF
    shoot_date_obj = _parse_shoot_date(shoot.shoot_date)
    if not shoot_date_obj:
        raise HTTPException(status_code=400, detail="Invalid shoot date")
    signed_at_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pdf_name = f"{body.talent_slug}-{shoot_date_obj.strftime('%m%d%y')}.pdf"
    pdf_path = _legal_pdf_dir() / shoot.shoot_date / pdf_name
    render_agreement_pdf(
        talent_display=body.talent_display,
        talent_role=body.talent_role,
        legal_name=body.legal_name,
        business_name=body.business_name,
        tax_classification=body.tax_classification,
        llc_class=body.llc_class,
        other_classification=body.other_classification,
        exempt_payee_code=body.exempt_payee_code,
        fatca_code=body.fatca_code,
        tin_type=body.tin_type,
        tin=body.tin,
        dob=body.dob,
        place_of_birth=body.place_of_birth,
        street_address=body.street_address,
        city_state_zip=body.city_state_zip,
        phone=body.phone,
        email=body.email,
        id1_type=body.id1_type,
        id1_number=body.id1_number,
        id2_type=body.id2_type,
        id2_number=body.id2_number,
        stage_names=body.stage_names,
        professional_names=body.professional_names,
        nicknames_aliases=body.nicknames_aliases,
        previous_legal_names=body.previous_legal_names,
        signature_png_bytes=png_bytes,
        shoot_date=shoot_date_obj,
        signed_at_iso=signed_at_iso,
        output_path=pdf_path,
    )

    # 3. Push to MEGA
    mega_studio = STUDIO_TO_MEGA.get(studio, studio)
    mega_remote = f"mega:/Grail/{mega_studio}/{scene_id}/Legal/{pdf_name}"
    mega_err: Optional[str] = None
    if scene_id:
        mega_err = _push_to_mega(pdf_path, mega_remote)
        if mega_err:
            _log.warning("MEGA push failed for %s: %s", pdf_name, mega_err)
    else:
        _log.warning("Skipping MEGA push: no scene_id for %s", shoot_id)
        mega_remote = ""

    # 4. Persist
    upsert_signature(
        shoot_id=shoot.shoot_id,
        shoot_date=shoot.shoot_date,
        scene_id=scene_id,
        studio=studio,
        talent_role=body.talent_role,
        talent_slug=body.talent_slug,
        talent_display=body.talent_display,
        legal_name=body.legal_name,
        business_name=body.business_name,
        tax_classification=body.tax_classification,
        llc_class=body.llc_class,
        other_classification=body.other_classification,
        exempt_payee_code=body.exempt_payee_code,
        fatca_code=body.fatca_code,
        tin_type=body.tin_type,
        tin=body.tin,
        dob=body.dob,
        place_of_birth=body.place_of_birth,
        street_address=body.street_address,
        city_state_zip=body.city_state_zip,
        phone=body.phone,
        email=body.email,
        id1_type=body.id1_type,
        id1_number=body.id1_number,
        id2_type=body.id2_type,
        id2_number=body.id2_number,
        stage_names=body.stage_names,
        professional_names=body.professional_names,
        nicknames_aliases=body.nicknames_aliases,
        previous_legal_names=body.previous_legal_names,
        signature_image_path=str(sig_path.relative_to(get_settings().base_dir)),
        signed_ip=request.client.host if request.client else "",
        signed_user_agent=request.headers.get("user-agent", "")[:300],
        signed_by_user=getattr(user, "email", "") or "",
        pdf_local_path=str(pdf_path),
        pdf_mega_path=mega_remote if not mega_err else "",
    )

    return SignResult(
        shoot_id=shoot.shoot_id,
        talent_role=body.talent_role,
        talent_slug=body.talent_slug,
        signed_at=signed_at_iso,
        pdf_local_path=str(pdf_path),
        pdf_mega_path=mega_remote if not mega_err else "",
        contract_version=contract_version(),
    )


@router.get("/shoots/{shoot_id}/signed", response_model=list[SignedSummary])
async def get_signed_summary(shoot_id: str, user: CurrentUser):
    """Return one row per talent who has completed the in-Hub agreement flow."""
    by_shoot = list_signed_talents([shoot_id])
    talents = by_shoot.get(shoot_id, [])
    return [
        SignedSummary(
            talent_role=t.talent_role,
            talent_slug=t.talent_slug,
            talent_display=t.talent_display,
            legal_name=t.legal_name,
            signed_at=t.signed_at,
            pdf_mega_path=t.pdf_mega_path,
        )
        for t in talents
    ]
