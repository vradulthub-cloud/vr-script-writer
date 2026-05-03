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

    # Per-scene script lookup — each scene's own female + studio
    scene_scripts: list[dict] = []
    for scene in scenes_data:
        female = scene.get("female", "")
        studio = scene.get("studio", "")
        script = get_script(female, studio) if female and studio else {}
        scene_scripts.append({**scene, "script": script})

    dt = scene_scripts[0].get("date_dt") or datetime.strptime(body.date_key, "%Y-%m-%d")

    # Unique talent: females first, then males not already listed
    all_females = list(dict.fromkeys(
        s.get("female", "") for s in scene_scripts if s.get("female", "")
    ))
    all_males = list(dict.fromkeys(
        s.get("male", "") for s in scene_scripts if s.get("male", "")
    ))
    talent_list = all_females + [m for m in all_males if m not in all_females]

    model1 = talent_list[0] if len(talent_list) > 0 else ""
    model2 = talent_list[1] if len(talent_list) > 1 else ""
    model3 = talent_list[2] if len(talent_list) > 2 else ""

    # Unique studios (preserving scene order)
    studio_parts = list(dict.fromkeys(
        s.get("studio", "") for s in scene_scripts if s.get("studio", "")
    ))

    female_agency = next((s.get("agency", "") for s in scene_scripts if s.get("agency", "")), "")
    male_agency   = next((s.get("male_agency", "") for s in scene_scripts if s.get("male_agency", "")), "")

    talent_parts = [p for p in talent_list if p]
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

    repl: dict[str, str] = {
        "{{Date}}":            date_display,
        "{{Studio Name}}":     " / ".join(studio_parts),
        "{{Model 1}}":         model1,
        "{{Model 2}}":         model2,
        "{{Model 3}}":         f" / {model3}" if model3 else "",
        "{{Female Agency}}":   female_agency or "[Agency pending]",
        "1322":                body.door_code,
        "7078":                body.door_code,
    }

    # Per-scene: type, studio website, script theme/text
    for i, ss in enumerate(scene_scripts):
        idx = i + 1
        sc = ss["script"]
        repl[f"{{{{Scene Type {idx}}}}}"] = ss.get("type", "")
        repl[f"{{{{Studio Website {idx}}}}}"] = web(ss.get("studio", ""))
        repl[f"{{{{Script Theme {idx}}}}}"] = sc.get("theme") or "[Title pending]"
        repl[f"{{{{Script Text {idx}}}}}"] = sc.get("plot") or pending

    # Clear unused scene slots so raw {{…}} placeholders don't leak into the doc
    for idx in range(len(scene_scripts) + 1, 6):
        repl[f"{{{{Scene Type {idx}}}}}"] = ""
        repl[f"{{{{Studio Website {idx}}}}}"] = ""
        repl[f"{{{{Script Theme {idx}}}}}"] = ""
        repl[f"{{{{Script Text {idx}}}}}"] = ""

    # Wardrobe: single-scene keeps it simple; multi-scene labels each block
    if len(scene_scripts) == 1:
        sc = scene_scripts[0]["script"]
        repl["{{Female Wardrobe}}"] = _wrap_wardrobe(sc.get("wardrobe_female", ""))
        repl["{{Male Wardrobe}}"]   = _wrap_wardrobe(sc.get("wardrobe_male", ""))
    else:
        f_parts: list[str] = []
        m_parts: list[str] = []
        for ss in scene_scripts:
            sc = ss["script"]
            scene_label = f"{ss.get('studio', '')} {ss.get('type', '')} — {ss.get('female', '')}"
            fw = sc.get("wardrobe_female", "")
            mw = sc.get("wardrobe_male", "")
            if fw:
                f_parts.append(f"[ {scene_label} ]\n{fw}")
            if mw:
                male_label = f"{ss.get('studio', '')} {ss.get('type', '')}"
                m_parts.append(f"[ {male_label} ]\n{mw}")
        repl["{{Female Wardrobe}}"] = _wrap_wardrobe("\n\n".join(f_parts)) if f_parts else "[Wardrobe pending]"
        repl["{{Male Wardrobe}}"]   = _wrap_wardrobe("\n\n".join(m_parts)) if m_parts else "[Wardrobe pending]"

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

    # Independent male talent — copy into each independent male's folder
    copied_males: set[str] = set()
    for ss in scene_scripts:
        male = ss.get("male", "")
        m_agency = ss.get("male_agency", "")
        if male and m_agency and m_agency.lower() == "independent" and male not in copied_males:
            copied_males.add(male)
            male_folder_id = get_or_create_folder(month_folder_id, male)
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
