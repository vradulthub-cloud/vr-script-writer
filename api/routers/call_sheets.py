"""
Call Sheets API router.

Reads the Budgets Google Sheet to get shoot dates and talent,
then generates Google Doc call sheets by copying a template.

Routes:
  GET  /api/call-sheets/tabs     — list available budget tabs
  GET  /api/call-sheets/dates    — get shoot dates with talent info
  POST /api/call-sheets/generate — generate a Google Doc call sheet
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.auth import CurrentUser
from api.config import get_settings

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/call-sheets", tags=["call-sheets"])

# ---------------------------------------------------------------------------
# Constants (matching call_sheet.py exactly)
# ---------------------------------------------------------------------------

TEMPLATE_DOC_ID = "1hIkvlNheFVJuxz35Dz6CuQ6-ZKNQ6Z-FR0b_ifXwEQc"
CALL_SHEETS_ROOT = "1BAYolVWIEMvlypQlEWSPa3bhIzV8CRyv"
MONTH_FOLDER_IDS = {
    "January":  "1-WmXs8TrZadpvNEL6aD0RRlnf-thGgPL",
    "February": "1our9efnyHghQsFCAYFJ8pvef1XIgqUzm",
    "March":    "1M9etju2A85ewGQ2rwXAcNc7yTjHcLUL1",
    "April":    "1Fj3aS9uO-7THiLbP1TlqVsQOPiW_YA7A",
}
STUDIO_WEBSITES = {
    "VRBangers":     "vrbangers.com",
    "FuckPassVR":    "fuckpassvr.com",
    "VRHush":        "vrhush.com",
    "VRAllure":      "vrallure.com",
    "NaughtyJOI":    "naughtyjoi.com",
    "VRSpy":         "vrspy.com",
    "VRConk":        "vrconk.com",
    "WankzVR":       "wankzvr.com",
    "BaDoinkVR":     "badoinkvr.com",
    "NaughtyAmerica":"naughtyamerica.com",
    "MilfVR":        "milfvr.com",
    "VRCosplayX":    "vrcosplayx.com",
}
SKIP_BUDGET_TABS = {"Cancellations", "Flights / Notes", "Template"}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ShootScene(BaseModel):
    date_raw: str
    studio: str
    type: str
    female: str
    male: str
    agency: str
    male_agency: str


class ShootDate(BaseModel):
    date_key: str      # "2026-04-15"
    date_display: str  # "4/15/2026"
    scenes: list[ShootScene]


class GenerateRequest(BaseModel):
    date_key: str
    door_code: str = "1322"
    tab_name: str | None = None


class GenerateResult(BaseModel):
    doc_id: str
    doc_url: str
    title: str


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

def _service_account_creds():
    """Service account creds for reading Sheets."""
    from google.oauth2.service_account import Credentials
    settings = get_settings()
    return Credentials.from_service_account_file(
        str(settings.service_account_file),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/documents",
        ],
    )


def _oauth_creds():
    """
    OAuth user creds from vr_oauth_token.json — used for Drive/Docs writes
    so files are owned by the configured Google user, not the service account.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    settings = get_settings()
    token_path = settings.base_dir / "vr_oauth_token.json"

    if not token_path.exists():
        raise HTTPException(
            status_code=503,
            detail="vr_oauth_token.json not found. Re-run the OAuth setup to generate it.",
        )

    with open(token_path) as f:
        tok = json.load(f)

    creds = Credentials(
        token=tok.get("token"),
        refresh_token=tok["refresh_token"],
        token_uri=tok.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=tok["client_id"],
        client_secret=tok["client_secret"],
    )
    if not creds.valid:
        creds.refresh(Request())
        tok["token"] = creds.token
        with open(token_path, "w") as f:
            json.dump(tok, f, indent=2)
    return creds


def _drive_docs():
    """Return (drive_service, docs_service) using OAuth creds."""
    from googleapiclient.discovery import build as gapi_build
    creds = _oauth_creds()
    return (
        gapi_build("drive", "v3", credentials=creds),
        gapi_build("docs",  "v1", credentials=creds),
    )


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> Optional[datetime]:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s.strip())
    if m:
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return datetime(y, mo, d)
        except ValueError:
            pass
    return None


def _fmt_date(dt: datetime) -> str:
    return f"{dt.month}/{dt.day}/{dt.year}"


def _escape_q(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/tabs")
async def list_budget_tabs(user: CurrentUser) -> list[str]:
    """List available budget tabs from the Budgets sheet."""
    import gspread
    settings = get_settings()
    gc = gspread.authorize(_service_account_creds())
    sh = gc.open_by_key(settings.budgets_sheet_id)
    return [ws.title for ws in sh.worksheets() if ws.title not in SKIP_BUDGET_TABS]


@router.get("/dates")
async def get_shoot_dates(
    user: CurrentUser,
    tab: Optional[str] = Query(default=None),
) -> list[ShootDate]:
    """
    Get shoot dates with talent/studio info from the Budgets sheet.

    Returns dates sorted newest-first. Optional tab filter.
    """
    import gspread
    settings = get_settings()
    gc = gspread.authorize(_service_account_creds())
    sh = gc.open_by_key(settings.budgets_sheet_id)

    results: dict[str, ShootDate] = {}

    for ws in sh.worksheets():
        if ws.title in SKIP_BUDGET_TABS:
            continue
        if tab and ws.title != tab:
            continue
        for row in ws.get_all_values()[1:]:
            if not row or not row[0].strip():
                continue
            if len(row) <= 4 or not row[4].strip():
                continue
            dt = _parse_date(row[0].strip())
            if not dt:
                continue
            key = dt.strftime("%Y-%m-%d")
            scene = ShootScene(
                date_raw=row[0].strip(),
                studio=row[1].strip() if len(row) > 1 else "",
                type=row[3].strip() if len(row) > 3 else "",
                female=row[4].strip() if len(row) > 4 else "",
                male=row[5].strip() if len(row) > 5 else "",
                agency=row[8].strip() if len(row) > 8 else "",
                male_agency=row[11].strip() if len(row) > 11 else "",
            )
            if key not in results:
                results[key] = ShootDate(
                    date_key=key,
                    date_display=_fmt_date(dt),
                    scenes=[],
                )
            results[key].scenes.append(scene)

    return sorted(results.values(), key=lambda x: x.date_key, reverse=True)


@router.post("/generate", response_model=GenerateResult)
async def generate_call_sheet(body: GenerateRequest, user: CurrentUser):
    """
    Generate a Google Doc call sheet for a given shoot date.

    Copies the template Doc, fills in script data from the database, and
    places the result in the correct Drive folder (month → agency).
    """
    import gspread
    from api.database import get_db

    settings = get_settings()
    gc = gspread.authorize(_service_account_creds())
    sh = gc.open_by_key(settings.budgets_sheet_id)

    # Gather scenes for this date from the sheet
    scenes_data: list[dict] = []
    for ws in sh.worksheets():
        if ws.title in SKIP_BUDGET_TABS:
            continue
        if body.tab_name and ws.title != body.tab_name:
            continue
        for row in ws.get_all_values()[1:]:
            if not row or not row[0].strip():
                continue
            dt = _parse_date(row[0].strip())
            if not dt:
                continue
            if dt.strftime("%Y-%m-%d") != body.date_key:
                continue
            if len(row) > 4 and row[4].strip():
                scenes_data.append({
                    "date_dt":    dt,
                    "studio":     row[1].strip() if len(row) > 1 else "",
                    "type":       row[3].strip() if len(row) > 3 else "",
                    "female":     row[4].strip() if len(row) > 4 else "",
                    "male":       row[5].strip() if len(row) > 5 else "",
                    "agency":     row[8].strip() if len(row) > 8 else "",
                    "male_agency":row[11].strip() if len(row) > 11 else "",
                })

    if not scenes_data:
        raise HTTPException(status_code=404, detail=f"No scenes found for {body.date_key}")

    # Script data from SQLite
    def get_script(female: str, studio: str) -> dict:
        with get_db() as conn:
            row = conn.execute(
                "SELECT theme, plot, wardrobe_f, wardrobe_m FROM scripts "
                "WHERE LOWER(female)=? AND LOWER(studio)=? ORDER BY id DESC LIMIT 1",
                (female.lower(), studio.lower()),
            ).fetchone()
        if row:
            d = dict(row)
            return {
                "theme":           d.get("theme", ""),
                "plot":            d.get("plot", ""),
                "wardrobe_female": d.get("wardrobe_f", ""),
                "wardrobe_male":   d.get("wardrobe_m", ""),
            }
        return {"theme": "", "plot": "", "wardrobe_female": "", "wardrobe_male": ""}

    # Sort scenes: BG first, then specialty types
    order = {"BG": 0, "GG": 1, "BGG": 2, "BGCP": 2, "JOI": 8, "Solo": 9}
    scenes_data.sort(key=lambda s: order.get(s.get("type", ""), 5))

    s1 = scenes_data[0] if len(scenes_data) > 0 else {}
    s2 = scenes_data[1] if len(scenes_data) > 1 else {}
    s3 = scenes_data[2] if len(scenes_data) > 2 else {}

    dt = s1.get("date_dt") or datetime.strptime(body.date_key, "%Y-%m-%d")
    model1 = s1.get("female", "")
    model2 = s1.get("male", "")
    if not model2 and s2 and s2.get("female", "") != model1:
        model2 = s2.get("female", "")
    model3 = s3.get("female", "") if s3 and s3.get("female", "") not in (model1, model2) else ""

    studio1 = s1.get("studio", "")
    studio2 = s2.get("studio", "") if s2 else ""
    type1 = s1.get("type", "BG")
    type2 = s2.get("type", "") if s2 else ""

    sc1 = get_script(model1, studio1) if model1 and studio1 else {}
    sc2 = get_script(model1, studio2) if model1 and studio2 else {}

    female_agency = next((s.get("agency", "") for s in scenes_data if s.get("agency", "")), "")
    male_agency   = next((s.get("male_agency", "") for s in scenes_data if s.get("male_agency", "")), "")

    talent_parts = [p for p in [model1, model2, model3] if p]
    studio_parts = list(dict.fromkeys(s for s in [studio1, studio2] if s))
    date_display = _fmt_date(dt)

    doc_title = (
        f"{date_display} - {' / '.join(studio_parts)} Call Sheet"
        f" - {' / '.join(talent_parts)} - Las Vegas"
    )

    def web(s: str) -> str:
        return STUDIO_WEBSITES.get(s, s.lower().replace(" ", "") + ".com")

    pending = "[Script not yet generated]"

    def _wrap_wardrobe(text: str) -> str:
        if not text or text.startswith("["):
            return text or "[Wardrobe pending]"
        prefix = "** Approximate Wardrobe Request.\n\n"
        suffix = (
            "\n\n** Please bring one or two additional outfits you feel sexy in "
            "just in case we have to do a plot change on set."
        )
        return f"{prefix}{text}{suffix}"

    repl = {
        "{{Date}}":            date_display,
        "{{Studio Name}}":     " / ".join(studio_parts),
        "{{Model 1}}":         model1,
        "{{Model 2}}":         model2,
        "{{Model 3}}":         f" / {model3}" if model3 else "",
        "{{Scene Type 1}}":    type1,
        "{{Scene Type 2}}":    type2,
        "{{Studio Website 1}}":web(studio1),
        "{{Studio Website 2}}":web(studio2) if studio2 else "",
        "{{Script Theme 1}}":  sc1.get("theme") or "[Title pending]",
        "{{Script Theme 2}}":  sc2.get("theme") or ("[Title pending]" if s2 else ""),
        "{{Script Text 1}}":   sc1.get("plot") or pending,
        "{{Script Text 2}}":   sc2.get("plot") or (pending if s2 else ""),
        "{{Female Wardrobe}}": _wrap_wardrobe(sc1.get("wardrobe_female", "")),
        "{{Male Wardrobe}}":   _wrap_wardrobe(sc1.get("wardrobe_male", "")),
        "{{Female Agency}}":   female_agency or "[Agency pending]",
        "1322":                body.door_code,
        "7078":                body.door_code,
    }

    # Drive / Docs via OAuth creds
    try:
        drive, docs = _drive_docs()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Google API unavailable: {exc}")

    # Month folder
    month = dt.strftime("%B")
    if month in MONTH_FOLDER_IDS:
        month_folder_id = MONTH_FOLDER_IDS[month]
    else:
        month_label = dt.strftime("%B '") + dt.strftime("%y")
        q = (
            f"name='{_escape_q(month_label)}' and '{CALL_SHEETS_ROOT}' in parents "
            "and mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        res = drive.files().list(q=q, fields="files(id)").execute()
        if res.get("files"):
            month_folder_id = res["files"][0]["id"]
        else:
            month_folder_id = drive.files().create(
                body={
                    "name": month_label,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [CALL_SHEETS_ROOT],
                },
                fields="id",
            ).execute()["id"]

    def get_or_create_folder(parent: str, name: str) -> str:
        q = (
            f"name='{_escape_q(name)}' and '{parent}' in parents "
            "and mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        res = drive.files().list(q=q, fields="files(id)").execute()
        if res.get("files"):
            return res["files"][0]["id"]
        return drive.files().create(
            body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]},
            fields="id",
        ).execute()["id"]

    agency_folder_name = (
        female_agency
        if female_agency and female_agency.lower() not in ("", "independent")
        else model1
    )
    folder_id = get_or_create_folder(month_folder_id, agency_folder_name)

    # Trash any existing call sheet for this date in this folder
    q_old = (
        f"name contains '{_escape_q(date_display)}' and name contains 'Call Sheet'"
        f" and '{folder_id}' in parents"
        " and mimeType='application/vnd.google-apps.document' and trashed=false"
    )
    for old in drive.files().list(q=q_old, fields="files(id)").execute().get("files", []):
        drive.files().update(fileId=old["id"], body={"trashed": True}).execute()

    # Copy template
    copied = drive.files().copy(
        fileId=TEMPLATE_DOC_ID,
        body={"name": doc_title, "parents": [folder_id]},
        fields="id,webViewLink",
    ).execute()

    doc_id  = copied["id"]
    doc_url = copied.get("webViewLink", f"https://docs.google.com/document/d/{doc_id}/edit")

    # Replace template placeholders
    docs.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [
                {
                    "replaceAllText": {
                        "containsText": {"text": ph, "matchCase": True},
                        "replaceText": val,
                    }
                }
                for ph, val in repl.items()
            ]
        },
    ).execute()

    # Independent male talent — also copy into their own folder
    if model2 and male_agency and male_agency.lower() == "independent":
        male_folder_id = get_or_create_folder(month_folder_id, model2)
        q_male = (
            f"name contains '{_escape_q(date_display)}' and name contains 'Call Sheet'"
            f" and '{male_folder_id}' in parents"
            " and mimeType='application/vnd.google-apps.document' and trashed=false"
        )
        for old in drive.files().list(q=q_male, fields="files(id)").execute().get("files", []):
            drive.files().update(fileId=old["id"], body={"trashed": True}).execute()
        drive.files().copy(
            fileId=doc_id,
            body={"name": doc_title, "parents": [male_folder_id]},
            fields="id",
        ).execute()

    _log.info("Call sheet generated: %s → %s", doc_title, doc_url)
    return GenerateResult(doc_id=doc_id, doc_url=doc_url, title=doc_title)
