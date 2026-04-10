#!/usr/bin/env python3
"""
create_legend.py
================
Creates (or refreshes) a "Legend" tab at the front of the spreadsheet,
explaining all colors, rank tiers, scoring rules, and workflow.

Usage:
    python3 /Users/andrewninn/Scripts/create_legend.py
"""

from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread

SPREADSHEET_ID       = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = Path(__file__).parent / "service_account.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

LEGEND_TITLE = "📋 Legend"


# ── Color helpers ──────────────────────────────────────────────────────────────

def rgb(r, g, b):
    return {"red": r / 255, "green": g / 255, "blue": b / 255}

def white():
    return rgb(255, 255, 255)

def black():
    return rgb(30, 30, 30)

# Palette — matches beautify_sheet.py
NAVY        = rgb(26,  35, 126)
GREEN_HDR   = rgb(27,  94,  32)
PURPLE      = rgb(74,  20, 140)

RANK_GREAT  = rgb(255, 196,   0)   # gold
RANK_GOOD   = rgb( 52, 168,  83)   # green
RANK_MOD    = rgb( 66, 133, 244)   # blue
RANK_UNK    = rgb(200, 200, 200)   # grey

AGE_18      = rgb(229,  57,  53)   # red
AGE_19_NOPE = rgb(245, 124,   0)   # orange
AGE_19_OK   = rgb(251, 192,  45)   # amber

BOOKED      = rgb(224, 247, 250)   # light teal
NEG_NOTE    = rgb(255, 243, 224)   # light amber (caution)
NEG_TEXT    = rgb(230,  81,   0)   # orange text

SECTION_BG  = rgb( 40,  53, 147)   # indigo — section header bars
ROW_ALT     = rgb(245, 247, 250)   # very light grey alternating


# ── Sheet content definition ───────────────────────────────────────────────────
# Each entry: (col_A_text, swatch_color_or_None, col_C_description, row_style)
# row_style: "title" | "section" | "data" | "data_alt" | "blank"

ROWS = [
    # Title
    ("📋  BOOKING SHEET LEGEND", None,
     "Reference guide — how ranks, colors, and scoring work",
     "title"),
    ("", None, "", "blank"),

    # ── Rank Tiers ──
    ("RANK TIERS", None, "", "section"),
    ("Great",    RANK_GREAT, "Top-tier talent. High platform reach, strong booking history, great on-set. Prioritise these.",     "data"),
    ("Good",     RANK_GOOD,  "Solid performer. Proven or well-known. Ready to book with standard vetting.",                       "data_alt"),
    ("Moderate", RANK_MOD,   "Some platform presence or prior bookings. Worth considering for select shoots.",                     "data"),
    ("Unknown",  RANK_UNK,   "No data, unavailable, or a no-go (age/notes override). Research before approaching.",               "data_alt"),
    ("", None, "", "blank"),

    # ── Row Highlight Colors ──
    ("ROW HIGHLIGHT COLORS", None, "", "section"),
    ("Red row",          AGE_18,      "Age 18 — Absolute no-go. Do not book under any circumstances.",                                             "data"),
    ("Orange row",       AGE_19_NOPE, "Age 19, no verified platform scenes or prior bookings. Treat as no-go until confirmed.",                    "data_alt"),
    ("Amber row",        AGE_19_OK,   "Age 19, has verified scenes on SLR / VRPorn / POVR. Review scenes & confirm age docs before booking.",      "data"),
    ("⚠️  Amber/orange text", NEG_NOTE, "Notes flag attitude or direction problems (moody, bad attitude, struggles, etc.). Proceed with caution.", "data_alt"),
    ("Teal + Bold",      BOOKED,      "Model we have personally booked before. Tabs are sorted so most-recently-booked appear first.",             "data"),
    ("", None, "", "blank"),

    # ── Cell Notes ──
    ("CELL NOTES  (hover over Name)", None, "", "section"),
    ("🚫 on Name cell", None, "Age 18 warning — includes prior booking history and absolute no-go confirmation.",                  "data"),
    ("⚠️  on Name cell", None, "Age 19 warning — shows our booking history, verified platform scenes, and recommended action.",   "data_alt"),
    ("", None, "", "blank"),

    # ── Scoring Rubric ──
    ("SCORING RUBRIC", None, "Max ~19 pts. Tiers: Great ≥9  ·  Good ≥5  ·  Moderate ≥1  ·  Unknown = 0", "section"),
    ("VRP Views",       None, "≥ 1M = 3 pts   ·   ≥ 500K = 2 pts   ·   ≥ 100K = 1 pt",         "data"),
    ("POVR Views",      None, "≥ 1M = 3 pts   ·   ≥ 500K = 2 pts   ·   ≥ 100K = 1 pt",         "data_alt"),
    ("VRP Followers",   None, "≥ 2,000 = 2 pts   ·   ≥ 500 = 1 pt",                             "data"),
    ("SLR Followers",   None, "≥ 500 = 1 pt",                                                    "data_alt"),
    ("SLR Scenes",      None, "≥ 10 scenes = 2 pts   ·   ≥ 5 scenes = 1 pt",                    "data"),
    ("Bookings (us)",   None, "≥ 5 shoots = 3 pts   ·   ≥ 3 = 2 pts   ·   ≥ 1 = 1 pt",         "data_alt"),
    ("Recency bonus",   None, "Booked ≤ 6 months ago = 2 pts   ·   ≤ 12 months = 1 pt",         "data"),
    ("AVG Rate",        None, "$1,500 – $2,500 = 1 pt   ·   Over $2,500 = no bonus (too premium for routine bookings)", "data_alt"),
    ("Available For",   None, "≥ 12 acts listed = 1 pt  (versatility bonus)",                   "data"),
    ("Notes",           None, "Positive note (great on-set) = +1 pt   ·   Negative note (attitude/direction) = −2 pts   ·   Unavailable → Unknown", "data_alt"),
    ("", None, "", "blank"),

    # ── Age Overrides ──
    ("AGE OVERRIDES", None, "Applied after base scoring — override or cap the computed tier", "section"),
    ("Age 18",              None, "Forced to Unknown. Absolute no-go regardless of platform data or booking history.",   "data"),
    ("Age 19  —  no data",  None, "Forced to Unknown. No verified scenes and no prior bookings with us.",                "data_alt"),
    ("Age 19  —  < 3 bookings", None, "Score capped at Good. Cannot earn Great until further vetted.",                  "data"),
    ("Age 19  —  ≥ 3 bookings", None, "+1 trusted return bonus. No tier cap — trusted talent, age docs confirmed.",     "data_alt"),
    ("", None, "", "blank"),

    # ── Hussie Models ──
    ("HUSSIE MODELS NOTE", None, "", "section"),
    ("Notes column", None,
     "In the Hussie tab the Notes column contains the internal contact name at the agency ('Riley' or 'Alex'). "
     "This is an agency-routing note, not a model review, and does not affect scoring.",
     "data"),
    ("", None, "", "blank"),

    # ── Last Booked Date format ──
    ("LAST BOOKED DATE FORMAT", None, "", "section"),
    ("Format",   None, "Mon YYYY  —  e.g. 'Feb 2026'  means most recent shoot was in Feb 2026", "data"),
    ("Bookings", None, "The Bookings column holds the total shoot count as a plain integer (e.g. 3)", "data_alt"),
    ("Sorting",  None, "Each tab is sorted by Last Booked Date descending — most recently booked models appear at the top", "data"),
    ("", None, "", "blank"),

    # ── Scripts ──
    ("SCRIPTS  (run from Terminal)", None, "", "section"),
    ("python3 run_all.py",               None, "⭐ Master script — runs all steps below in the correct order. Recommended for a full refresh.", "data"),
    ("python3 compute_rank.py",          None, "Re-scores all models and writes Rank column. Run after updating platform data or bookings.",    "data_alt"),
    ("python3 beautify_sheet.py",        None, "Re-applies all formatting, colors, banding, filters, and sort across all agency tabs.",         "data"),
    ("python3 ui_improvements.py",       None, "Refreshes title bars, gridline settings, and row freezes.",                                     "data_alt"),
    ("python3 add_enhancements.py",      None, "Adds/refreshes Bookings & Last Booked Date columns and stale conditional format.",              "data"),
    ("python3 backfill_dates_booked.py", None, "Fills empty Last Booked Date cells using scene history from the master scenes doc.",            "data_alt"),
    ("python3 create_search_tab.py",     None, "Rebuilds the 🔍 Search tab layout.",                                                            "data"),
    ("python3 create_dashboard.py",      None, "Rebuilds the 📊 Dashboard with live stats, top 15, stale targets, and never-booked list.",     "data_alt"),
    ("python3 detect_duplicates.py",     None, "Finds models signed with multiple agencies and writes results to the Export tab.",              "data"),
    ("python3 create_legend.py",         None, "Recreates this Legend tab.",                                                                    "data_alt"),
    ("python3 add_age_notes.py",         None, "Refreshes hover notes on under-20 models. Run after age data changes.",                        "data"),
    ("python3 add_profile_links.py",     None, "Adds HYPERLINK formula to Name column (SLR → VRPorn → POVR → Agency site).",                  "data_alt"),
]


# ── Formatting helpers ─────────────────────────────────────────────────────────

def cell_fmt(bg, fg, bold=False, size=10, align="LEFT", valign="MIDDLE"):
    return {
        "backgroundColor": bg,
        "textFormat": {
            "foregroundColor": fg,
            "bold":            bold,
            "fontSize":        size,
        },
        "horizontalAlignment": align,
        "verticalAlignment":   valign,
        "wrapStrategy": "WRAP",
    }


def repeat_cell(sheet_id, row, col, fmt, end_col=None):
    return {
        "repeatCell": {
            "range": {
                "sheetId":          sheet_id,
                "startRowIndex":    row,
                "endRowIndex":      row + 1,
                "startColumnIndex": col,
                "endColumnIndex":   end_col if end_col else col + 1,
            },
            "cell": {"userEnteredFormat": fmt},
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
        }
    }


def merge(sheet_id, row, start_col, end_col):
    return {
        "mergeCells": {
            "range": {
                "sheetId":          sheet_id,
                "startRowIndex":    row,
                "endRowIndex":      row + 1,
                "startColumnIndex": start_col,
                "endColumnIndex":   end_col,
            },
            "mergeType": "MERGE_ALL",
        }
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    creds   = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc      = gspread.authorize(creds)
    service = build("sheets", "v4", credentials=creds)
    ss      = gc.open_by_key(SPREADSHEET_ID)

    # ── 1. Get or create the Legend tab ──────────────────────────────────────
    existing = {ws.title: ws for ws in ss.worksheets()}
    if LEGEND_TITLE in existing:
        ws = existing[LEGEND_TITLE]
        ws.clear()
        print(f"Cleared existing '{LEGEND_TITLE}' tab.")
    else:
        ws = ss.add_worksheet(title=LEGEND_TITLE, rows=100, cols=4)
        print(f"Created new '{LEGEND_TITLE}' tab.")

    # Move to first position
    sheet_id = ws.id
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "index": 0},
            "fields": "index",
        }}]}
    ).execute()

    # ── 2. Write cell values ──────────────────────────────────────────────────
    values = []
    for label, _swatch, desc, _style in ROWS:
        values.append([label, "", desc])   # col A, B (swatch), C

    ws.update(values, "A1", value_input_option="RAW")

    # ── 3. Apply formatting ───────────────────────────────────────────────────
    requests = []

    # Column widths: A=240, B=28 (swatch), C=700
    for col_idx, width in [(0, 240), (1, 28), (2, 700)]:
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                          "startIndex": col_idx, "endIndex": col_idx + 1},
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        })

    # Row heights — title row taller, data rows 28px so wrapping text shows
    requests.append({
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS",
                      "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 36},
            "fields": "pixelSize",
        }
    })
    requests.append({
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS",
                      "startIndex": 1, "endIndex": len(ROWS)},
            "properties": {"pixelSize": 28},
            "fields": "pixelSize",
        }
    })

    # Freeze header row
    requests.append({
        "updateSheetProperties": {
            "properties": {"sheetId": sheet_id,
                           "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }
    })

    for row_idx, (label, swatch, desc, style) in enumerate(ROWS):
        if style == "title":
            # Merge A–C, navy bg, white bold
            requests.append(merge(sheet_id, row_idx, 0, 3))
            requests.append(repeat_cell(sheet_id, row_idx, 0,
                cell_fmt(NAVY, white(), bold=True, size=13, align="CENTER"), end_col=3))

        elif style == "section":
            # Merge A–C, indigo bg, white bold
            requests.append(merge(sheet_id, row_idx, 0, 3))
            requests.append(repeat_cell(sheet_id, row_idx, 0,
                cell_fmt(SECTION_BG, white(), bold=True, size=10, align="LEFT"), end_col=3))

        elif style in ("data", "data_alt"):
            row_bg = white() if style == "data" else ROW_ALT

            # Col A — label
            requests.append(repeat_cell(sheet_id, row_idx, 0,
                cell_fmt(row_bg, black(), bold=True, size=9)))

            # Col B — color swatch (filled with swatch color, empty text)
            swatch_bg = swatch if swatch else row_bg
            requests.append(repeat_cell(sheet_id, row_idx, 1,
                cell_fmt(swatch_bg, swatch_bg)))   # bg = fg so no text shows

            # Col C — description
            requests.append(repeat_cell(sheet_id, row_idx, 2,
                cell_fmt(row_bg, black(), bold=False, size=9)))

        elif style == "blank":
            requests.append(repeat_cell(sheet_id, row_idx, 0,
                cell_fmt(white(), white()), end_col=3))

    # ── 4. Send all formatting ────────────────────────────────────────────────
    chunk = 100
    total = len(requests)
    for i in range(0, total, chunk):
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"requests": requests[i:i+chunk]}
        ).execute()
        print(f"  Formatted rows {i}–{min(i+chunk, total)-1}")

    print(f"\nDone! '{LEGEND_TITLE}' tab created with {len(ROWS)} rows.")


if __name__ == "__main__":
    main()
