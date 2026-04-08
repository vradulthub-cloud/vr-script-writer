"""
sheets_integration.py
Handles all reading/writing to the 2026 Scripts Google Sheet.

Sheet ID: 1cY-8zNHLmD-oWdyEa2Mt3VY3nsFXHLEeZx0n42uf3ZQ
Columns:  A=Date  B=Studio  C=Location  D=Scene  E=Female  F=Male
          G=Theme  H=WardrobeF  I=WardrobeM  J=Plot  K=Title  L=Props  M=Status
"""

import os
import re
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread

SHEET_ID = "1cY-8zNHLmD-oWdyEa2Mt3VY3nsFXHLEeZx0n42uf3ZQ"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Tabs that are NOT shoot month tabs
SKIP_TABS = {"Cancellations", "Script Locker", "Template"}

# Column indices (0-based)
COL_DATE     = 0   # A
COL_STUDIO   = 1   # B
COL_LOCATION = 2   # C
COL_SCENE    = 3   # D
COL_FEMALE   = 4   # E
COL_MALE     = 5   # F
COL_THEME    = 6   # G
COL_WARD_F   = 7   # H
COL_WARD_M   = 8   # I
COL_PLOT     = 9   # J
COL_TITLE    = 10  # K  (scene release title)
COL_PROPS    = 11  # L
COL_STATUS   = 12  # M  (REGEN/DONE flag — added by this integration)

# Status values
STATUS_REGEN = "REGEN"
STATUS_DONE  = "DONE"


_cached_client = None
_cached_at = 0

def _get_client():
    global _cached_client, _cached_at
    import time
    now = time.time()
    if _cached_client and (now - _cached_at) < 1800:
        return _cached_client
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    _cached_client = gspread.authorize(creds)
    _cached_at = now
    return _cached_client


def get_spreadsheet():
    return _get_client().open_by_key(SHEET_ID)


def month_tabs(sh=None):
    """Return all shoot-month worksheets (skip Cancellations, Script Locker, Template)."""
    if sh is None:
        sh = get_spreadsheet()
    return [ws for ws in sh.worksheets() if ws.title not in SKIP_TABS]


def current_month_tab(sh=None):
    """Return the worksheet for the current calendar month."""
    if sh is None:
        sh = get_spreadsheet()
    month_name = datetime.now().strftime("%B %Y")   # e.g. "March 2026"
    for ws in sh.worksheets():
        if ws.title == month_name:
            return ws
    return None


def _pad(row, length):
    """Extend a row list to at least `length` elements."""
    return row + [""] * (length - len(row))


def rows_needing_scripts(ws, include_regen=True):
    """
    Return list of (row_index_1based, row_data_dict) for rows that:
      - Have Studio + Female filled in
      - AND either Plot is empty OR Status == 'REGEN'
    Skips the header row (row 1).
    """
    all_rows = ws.get_all_values()
    results = []
    for i, row in enumerate(all_rows[1:], start=2):  # 1-indexed, skip header
        row = _pad(row, COL_STATUS + 1)
        studio  = row[COL_STUDIO].strip()
        female  = row[COL_FEMALE].strip()
        plot    = row[COL_PLOT].strip()
        status  = row[COL_STATUS].strip().upper()

        if not studio or not female:
            continue

        needs = (not plot) or (include_regen and status == STATUS_REGEN)
        if needs:
            results.append((i, {
                "studio":      studio,
                "location":    row[COL_LOCATION].strip(),
                "scene_type":  row[COL_SCENE].strip(),
                "female":      female,
                "male":        row[COL_MALE].strip(),
                "has_plot":    bool(plot),
                "status":      status,
                "row_index":   i,
            }))
    return results


def write_script(ws, row_index, theme, plot, wardrobe_female, wardrobe_male,
                 shoot_location="", set_design="", props=""):
    """Write generated script fields to the correct row."""
    # Append production notes at bottom of plot
    production_notes = []
    if shoot_location:
        production_notes.append(f"📍 Shoot Location: {shoot_location}")
    if set_design:
        production_notes.append(f"🎨 Set Design: {set_design}")
    if props:
        production_notes.append(f"📦 Props: {props}")

    full_plot = plot
    if production_notes:
        full_plot = plot.rstrip() + "\n\n——\n" + "\n".join(production_notes)

    updates = {
        f"G{row_index}": theme,
        f"H{row_index}": wardrobe_female,
        f"I{row_index}": wardrobe_male,
        f"J{row_index}": full_plot,
        f"K{row_index}": STATUS_DONE,
    }
    for cell, value in updates.items():
        ws.update(cell, [[value]])


def mark_row_for_regen(ws, row_index):
    ws.update(f"K{row_index}", [[STATUS_REGEN]])


def mark_talent_for_regen(talent_name):
    """Mark all rows matching a talent name across all month tabs."""
    sh = get_spreadsheet()
    marked = []
    name_norm = talent_name.strip().lower()
    for ws in month_tabs(sh):
        rows = ws.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            row = _pad(row, COL_FEMALE + 1)
            if row[COL_FEMALE].strip().lower() == name_norm:
                mark_row_for_regen(ws, i)
                marked.append((ws.title, i, row[COL_FEMALE].strip()))
    return marked


def mark_all_for_regen(tab_name=None):
    """Mark all rows (with Studio+Female) for regeneration."""
    sh = get_spreadsheet()
    tabs = [ws for ws in month_tabs(sh) if (tab_name is None or ws.title == tab_name)]
    marked = []
    for ws in tabs:
        rows = ws.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            row = _pad(row, COL_FEMALE + 1)
            if row[COL_STUDIO].strip() and row[COL_FEMALE].strip():
                mark_row_for_regen(ws, i)
                marked.append((ws.title, i))
    return marked


def find_row_for_shoot(female_name, studio=None, tab_name=None):
    """
    Find the first row matching a female model name.
    Returns (worksheet, row_index) or (None, None).
    """
    sh = get_spreadsheet()
    name_norm = female_name.strip().lower()
    tabs = month_tabs(sh) if tab_name is None else [sh.worksheet(tab_name)]
    for ws in tabs:
        if tab_name is None and studio is None:
            # Prefer current month first
            cur = current_month_tab(sh)
            if cur:
                tabs_ordered = [cur] + [t for t in tabs if t.title != cur.title]
                tabs = tabs_ordered
                break
    for ws in tabs:
        rows = ws.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            row = _pad(row, COL_FEMALE + 1)
            if row[COL_FEMALE].strip().lower() == name_norm:
                if studio is None or row[COL_STUDIO].strip().lower() in studio.lower():
                    return ws, i
    return None, None


def parse_script_text(text):
    """
    Parse the structured text output from Claude into a dict of fields.
    Expected markers (case-insensitive):
      THEME:, PLOT:, SHOOT LOCATION:, SET DESIGN:, PROPS:,
      WARDROBE — FEMALE: / WARDROBE - FEMALE:, WARDROBE — MALE: / WARDROBE - MALE:
    """
    # Normalize dashes/em-dashes
    text = text.replace("—", "-").replace("\u2014", "-")

    patterns = [
        ("theme",           r"(?:^|\n)\*{0,2}THEME[:\*]{1,3}\s*(.+?)(?=\n\*{0,2}(?:PLOT|SHOOT|SET|PROPS|WARDROBE)|$)"),
        ("plot",            r"(?:^|\n)\*{0,2}PLOT[:\*]{1,3}\s*([\s\S]+?)(?=\n\*{0,2}(?:SHOOT|SET|PROPS|WARDROBE)|$)"),
        ("shoot_location",  r"(?:^|\n)\*{0,2}SHOOT\s*LOCATION[:\*]{1,3}\s*(.+?)(?=\n\*{0,2}(?:SET|PROPS|WARDROBE)|$)"),
        ("set_design",      r"(?:^|\n)\*{0,2}SET\s*DESIGN[:\*]{1,3}\s*([\s\S]+?)(?=\n\*{0,2}(?:PROPS|WARDROBE)|$)"),
        ("props",           r"(?:^|\n)\*{0,2}PROPS?(?:\s*RECOMMENDATIONS?)?[:\*]{1,3}\s*([\s\S]+?)(?=\n\*{0,2}WARDROBE|$)"),
        ("wardrobe_female", r"(?:^|\n)\*{0,2}WARDROBE\s*[-–—]\s*FEMALE[:\*]{1,3}\s*([\s\S]+?)(?=\n\*{0,2}WARDROBE\s*[-–—]\s*MALE|$)"),
        ("wardrobe_male",   r"(?:^|\n)\*{0,2}WARDROBE\s*[-–—]\s*MALE[:\*]{1,3}\s*([\s\S]+?)(?=$|\Z)"),
    ]

    result = {}
    for key, pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        result[key] = m.group(1).strip() if m else ""

    return result
