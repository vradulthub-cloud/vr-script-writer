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

import io
import json
import logging
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from api.auth import CurrentUser
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


# ─── Drive helpers ────────────────────────────────────────────────────────────

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


def _upload_to_drive(folder_id: str, file_name: str,
                     file_bytes: bytes, mime_type: str, token: str) -> str:
    """Multipart upload to Drive. Returns new file ID."""
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
        "?uploadType=multipart&fields=id",
        data=body, method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary.decode()}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("id", "")


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
    results: list[ComplianceShoot] = []

    for shoot in shoots:
        bg_scenes = [sc for sc in shoot.scenes if sc.scene_type.upper() in ("BG", "BGCP")]
        if not bg_scenes:
            continue

        primary = bg_scenes[0]
        scene_id = primary.scene_id or ""
        studio = primary.studio or ""

        folder_url = folder_id = folder_name = None
        pdfs_ready = False
        photos_count = 0
        is_complete = False

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
                        pdf_count = sum(1 for f in files if f.get("name", "").lower().endswith(".pdf"))
                        jpg_count = sum(1 for f in files if f.get("name", "").lower().endswith((".jpg", ".jpeg", ".png")))
                        need_pdfs = 2 if shoot.male_talent else 1
                        pdfs_ready = pdf_count >= need_pdfs
                        photos_count = jpg_count
                except Exception as exc:
                    _log.debug("compliance folder lookup: %s", exc)

        for sc in bg_scenes:
            for asset in sc.assets:
                if asset.asset_type == "legal_docs_uploaded" and asset.status == "validated":
                    is_complete = True

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

    uploaded: list[str] = []
    drive_file_ids: list[str] = []
    mega_paths: list[str] = []
    errors: list[str] = []

    tmp_dir: Optional[str] = None
    if scene_id and studio:
        tmp_dir = tempfile.mkdtemp(prefix="compliance_")

    try:
        for i, upload_file in enumerate(files):
            label = labels[i] if i < len(labels) else (upload_file.filename or f"photo_{i + 1}.jpg")
            if not any(label.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png")):
                label += ".jpg"
            try:
                content = await upload_file.read()
                mime = upload_file.content_type or "image/jpeg"
                fid = _upload_to_drive(folder_id, label, content, mime, token)
                uploaded.append(label)
                drive_file_ids.append(fid)
                if tmp_dir:
                    (Path(tmp_dir) / label).write_bytes(content)
            except Exception as exc:
                _log.warning("photo upload failed %s: %s", label, exc)
                errors.append(f"{label}: {exc}")

        # MEGA upload
        if tmp_dir and scene_id and studio and uploaded:
            mega_studio = STUDIO_TO_MEGA.get(studio, studio)
            mega_path = f"mega:/Grail/{mega_studio}/{scene_id}/Legal/"
            try:
                r = subprocess.run(
                    ["rclone", "copy", tmp_dir, mega_path],
                    capture_output=True, text=True, timeout=120,
                )
                if r.returncode == 0:
                    mega_paths = [f"{mega_path}{n}" for n in uploaded]
                else:
                    errors.append(f"MEGA: {r.stderr[:200]}")
            except Exception as exc:
                errors.append(f"MEGA: {exc}")
    finally:
        if tmp_dir:
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
            ["rclone", "copy", tmp_dir, mega_path],
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
    """Serve the filled PDF for a talent from their Drive legal folder."""
    from fastapi.responses import Response as FastAPIResponse

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
        raise HTTPException(status_code=503, detail="Drive credentials unavailable")

    folder_info = _get_shoot_folder(
        shoot_date, shoot.female_talent, shoot.male_talent, token
    )
    if not folder_info:
        raise HTTPException(status_code=404, detail="Drive folder not found — run Prepare first")
    folder_id, _ = folder_info

    files = _list_folder_files(folder_id, token)
    talent_slug = talent.replace(" ", "")
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
