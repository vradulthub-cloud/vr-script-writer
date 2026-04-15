"""
call_sheet.py - Generates Google Doc call sheets from template.
"""
import os, re
from datetime import datetime
import gspread
from googleapiclient.discovery import build as _gapi_build

TEMPLATE_DOC_ID  = "1hIkvlNheFVJuxz35Dz6CuQ6-ZKNQ6Z-FR0b_ifXwEQc"
CALL_SHEETS_ROOT = "1BAYolVWIEMvlypQlEWSPa3bhIzV8CRyv"
BUDGETS_SHEET_ID = "1bM1G49p2KK9WY3WfjzPixrWUw8KBiDGKR-0jKw5QUVc"
MONTH_FOLDER_IDS = {
    "January":  "1-WmXs8TrZadpvNEL6aD0RRlnf-thGgPL",
    "February": "1our9efnyHghQsFCAYFJ8pvef1XIgqUzm",
    "March":    "1M9etju2A85ewGQ2rwXAcNc7yTjHcLUL1",
    "April":    "1Fj3aS9uO-7THiLbP1TlqVsQOPiW_YA7A",
}
STUDIO_WEBSITES = {
    "VRBangers":"vrbangers.com","FuckPassVR":"fuckpassvr.com",
    "VRHush":"vrhush.com","VRAllure":"vrallure.com",
    "NaughtyJOI":"naughtyjoi.com","VRSpy":"vrspy.com",
    "VRConk":"vrconk.com","WankzVR":"wankzvr.com",
    "BaDoinkVR":"badoinkvr.com","NaughtyAmerica":"naughtyamerica.com",
    "MilfVR":"milfvr.com","VRCosplayX":"vrcosplayx.com",
}
SA_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]
SKIP_BUDGET_TABS = {"Cancellations","Flights / Notes","Template"}

def _get_creds():
    """Service account creds — used for gspread (Sheets) access."""
    from google.oauth2.service_account import Credentials
    try:
        import streamlit as st
        return Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]),scopes=SA_SCOPES)
    except Exception:
        svc=os.path.join(os.path.dirname(__file__),"service_account.json")
        return Credentials.from_service_account_file(svc,scopes=SA_SCOPES)

def _get_user_creds():
    """OAuth user creds — used for Drive/Docs so files are owned by the user."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    # Try Streamlit secrets first
    try:
        import streamlit as st
        tok = dict(st.secrets["oauth_token"])
        creds = Credentials(
            token=tok.get("token"),
            refresh_token=tok["refresh_token"],
            token_uri=tok.get("token_uri","https://oauth2.googleapis.com/token"),
            client_id=tok["client_id"],
            client_secret=tok["client_secret"],
        )
        if not creds.valid:
            creds.refresh(Request())
        return creds
    except Exception:
        pass
    # Fall back to local token file
    token_path = os.path.join(os.path.dirname(__file__), "vr_oauth_token.json")
    import json
    tok = json.load(open(token_path))
    # Do NOT pass scopes — the refresh token already carries them.
    # Passing scopes causes invalid_scope errors on refresh.
    creds = Credentials(
        token=tok.get("token"),
        refresh_token=tok["refresh_token"],
        token_uri=tok.get("token_uri","https://oauth2.googleapis.com/token"),
        client_id=tok["client_id"],
        client_secret=tok["client_secret"],
    )
    if not creds.valid:
        creds.refresh(Request())
        # Save refreshed token
        tok["token"] = creds.token
        json.dump(tok, open(token_path,"w"), indent=2)
    return creds

def _services():
    c=_get_user_creds()
    return _gapi_build("drive","v3",credentials=c),_gapi_build("docs","v1",credentials=c)

def _parse_date(s):
    m=re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$',s.strip())
    if m:
        mo,d,y=int(m.group(1)),int(m.group(2)),int(m.group(3))
        if y<100: y+=2000
        try: return datetime(y,mo,d)
        except ValueError: pass
    return None

def _fmt_date(dt):
    """Returns e.g. '4/13/2026' matching existing call sheet naming convention."""
    return f"{dt.month}/{dt.day}/{dt.year}"

def _month_label(dt):
    return dt.strftime("%B '")+dt.strftime("%y")

def get_budget_tabs():
    gc=gspread.authorize(_get_creds())
    return [ws.title for ws in gc.open_by_key(BUDGETS_SHEET_ID).worksheets() if ws.title not in SKIP_BUDGET_TABS]

def get_shoot_dates(tab_name=None):
    gc=gspread.authorize(_get_creds())
    sh=gc.open_by_key(BUDGETS_SHEET_ID)
    results={}
    for ws in sh.worksheets():
        if ws.title in SKIP_BUDGET_TABS: continue
        if tab_name and ws.title!=tab_name: continue
        for row in ws.get_all_values()[1:]:
            if not row or not row[0].strip(): continue
            if len(row)<=4 or not row[4].strip(): continue
            dt=_parse_date(row[0].strip())
            if not dt: continue
            key=dt.strftime("%Y-%m-%d")
            results.setdefault(key,[]).append({
                "date_raw":row[0].strip(),"date_dt":dt,
                "studio":row[1].strip() if len(row)>1 else "",
                "type":row[3].strip() if len(row)>3 else "",
                "female":row[4].strip() if len(row)>4 else "",
                "male":row[5].strip() if len(row)>5 else "",
                "agency":row[8].strip() if len(row)>8 else "",
                "male_agency":row[11].strip() if len(row)>11 else "",
            })
    return results

_script_cache = {}
_script_cache_loaded = False

def _load_script_cache():
    global _script_cache, _script_cache_loaded
    if _script_cache_loaded:
        return
    from sheets_integration import get_spreadsheet,month_tabs,_pad,COL_STUDIO,COL_FEMALE,COL_THEME,COL_WARD_F,COL_WARD_M,COL_PLOT
    try:
        sh=get_spreadsheet()
        for ws in month_tabs(sh):
            for row in ws.get_all_values()[1:]:
                row=_pad(row,15)
                female=row[COL_FEMALE].strip().lower()
                studio=row[COL_STUDIO].strip().lower()
                if female and studio:
                    _script_cache[(female,studio)]={
                        "theme":row[COL_THEME].strip(),"plot":row[COL_PLOT].strip(),
                        "wardrobe_female":row[COL_WARD_F].strip(),"wardrobe_male":row[COL_WARD_M].strip()
                    }
        _script_cache_loaded=True
    except Exception:
        pass

def reload_script_cache():
    """Force a fresh load of script data from Sheets. Call before generating call sheets."""
    global _script_cache, _script_cache_loaded
    _script_cache = {}
    _script_cache_loaded = False
    _load_script_cache()

def get_script_for_scene(female,studio):
    _load_script_cache()
    return _script_cache.get((female.strip().lower(),studio.strip().lower()),
                             {"theme":"","plot":"","wardrobe_female":"","wardrobe_male":""})

def _escape_drive_q(s):
    """Escape single quotes in Drive API query string values."""
    return s.replace("\\", "\\\\").replace("'", "\\'")

def _get_or_create_month_folder(drive,dt):
    month=dt.strftime("%B")
    if month in MONTH_FOLDER_IDS: return MONTH_FOLDER_IDS[month]
    label=_month_label(dt)
    q=f"name='{_escape_drive_q(label)}' and '{CALL_SHEETS_ROOT}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res=drive.files().list(q=q,fields="files(id)").execute()
    if res.get("files"): return res["files"][0]["id"]
    return drive.files().create(body={"name":label,"mimeType":"application/vnd.google-apps.folder","parents":[CALL_SHEETS_ROOT]},fields="id").execute()["id"]

def _get_or_create_agency_folder(drive,month_folder_id,agency_name):
    """Get or create an agency subfolder within the month folder."""
    q=f"name='{_escape_drive_q(agency_name)}' and '{month_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res=drive.files().list(q=q,fields="files(id)").execute()
    if res.get("files"): return res["files"][0]["id"]
    return drive.files().create(body={"name":agency_name,"mimeType":"application/vnd.google-apps.folder","parents":[month_folder_id]},fields="id").execute()["id"]

def generate_call_sheet(date_key,scenes,door_code="1322"):
    drive,docs=_services()
    order={"BG":0,"GG":1,"BGG":2,"BGCP":2,"JOI":8,"Solo":9}
    scenes=sorted(scenes,key=lambda s:order.get(s.get("type",""),5))
    s1=scenes[0] if len(scenes)>0 else {}
    s2=scenes[1] if len(scenes)>1 else {}
    s3=scenes[2] if len(scenes)>2 else {}
    dt=s1.get("date_dt") or datetime.strptime(date_key,"%Y-%m-%d")
    model1=s1.get("female",""); model2=s1.get("male","")
    if not model2 and s2 and s2.get("female","")!=model1: model2=s2.get("female","")
    model3=s3.get("female","") if s3 and s3.get("female","") not in (model1,model2) else ""
    studio1=s1.get("studio",""); studio2=s2.get("studio","") if s2 else ""
    type1=s1.get("type","BG"); type2=s2.get("type","") if s2 else ""
    sc1=get_script_for_scene(model1,studio1) if model1 and studio1 else {}
    sc2=get_script_for_scene(model1,studio2) if model1 and studio2 else {}
    # Agency — pull from the first scene that has data
    female_agency=next((s.get("agency","") for s in scenes if s.get("agency","")),  "")
    male_agency=next((s.get("male_agency","") for s in scenes if s.get("male_agency","")), "")
    talent_parts=[p for p in [model1,model2,model3] if p]
    studio_parts=list(dict.fromkeys(s for s in [studio1,studio2] if s))
    date_display=_fmt_date(dt)
    doc_title=f"{date_display} - {' / '.join(studio_parts)} Call Sheet - {' / '.join(talent_parts)} - Las Vegas"
    def web(s): return STUDIO_WEBSITES.get(s,s.lower().replace(" ","")+".com")
    pending="[Script not yet generated - run Batch Generate first]"
    repl={
        "{{Date}}":date_display,"{{Studio Name}}":" / ".join(studio_parts),
        "{{Model 1}}":model1,"{{Model 2}}":model2,
        "{{Model 3}}":f" / {model3}" if model3 else "",
        "{{Scene Type 1}}":type1,"{{Scene Type 2}}":type2,
        "{{Studio Website 1}}":web(studio1),
        "{{Studio Website 2}}":web(studio2) if studio2 else "",
        "{{Script Theme 1}}":sc1.get("theme") or "[Title pending]",
        "{{Script Theme 2}}":sc2.get("theme") or ("[Title pending]" if s2 else ""),
        "{{Script Text 1}}":sc1.get("plot") or pending,
        "{{Script Text 2}}":sc2.get("plot") or (pending if s2 else ""),
        "{{Female Wardrobe}}":sc1.get("wardrobe_female") or "[Wardrobe pending]",
        "{{Male Wardrobe}}":sc1.get("wardrobe_male") or "[Wardrobe pending]",
        "{{Female Agency}}":female_agency or "[Agency pending]",
        "1322":door_code,"7078":door_code,
    }
    month_folder_id=_get_or_create_month_folder(drive,dt)
    # Agency folder name: use female agency if set, otherwise the female model's name
    agency_folder_name=female_agency if female_agency and female_agency.lower() not in ("","independent") else model1
    folder_id=_get_or_create_agency_folder(drive,month_folder_id,agency_folder_name)

    # Check for existing call sheet with same date in this folder — delete old ones
    # Match by date prefix so renamed talent/studios still get caught
    date_prefix=_escape_drive_q(date_display)
    existing_q=f"name contains '{date_prefix}' and name contains 'Call Sheet' and '{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
    existing=drive.files().list(q=existing_q,fields="files(id,name)").execute().get("files",[])
    for old in existing:
        drive.files().update(fileId=old["id"],body={"trashed":True}).execute()

    copied=drive.files().copy(fileId=TEMPLATE_DOC_ID,body={"name":doc_title,"parents":[folder_id]},fields="id,webViewLink").execute()
    doc_id=copied["id"]
    doc_url=copied.get("webViewLink",f"https://docs.google.com/document/d/{doc_id}/edit")
    docs.documents().batchUpdate(documentId=doc_id,body={"requests":[{"replaceAllText":{"containsText":{"text":ph,"matchCase":True},"replaceText":val}} for ph,val in repl.items()]}).execute()
    # If male talent is independent, copy the call sheet into their own folder too
    if model2 and male_agency and male_agency.lower()=="independent":
        male_folder_id=_get_or_create_agency_folder(drive,month_folder_id,model2)
        # Trash any existing call sheet for this date in the male folder
        male_existing_q=f"name contains '{date_prefix}' and name contains 'Call Sheet' and '{male_folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
        male_existing=drive.files().list(q=male_existing_q,fields="files(id)").execute().get("files",[])
        for old in male_existing:
            drive.files().update(fileId=old["id"],body={"trashed":True}).execute()
        drive.files().copy(fileId=doc_id,body={"name":doc_title,"parents":[male_folder_id]},fields="id").execute()
    return {"doc_id":doc_id,"doc_url":doc_url,"title":doc_title}
