#!/usr/bin/env python3
"""
create_search_tab.py
====================
Creates (or refreshes) the '🔍 Search' tab with layout and instructions.
The dynamic search logic is handled by Apps Script (injected separately).

Usage:
    python3 /Users/andrewninn/Scripts/create_search_tab.py
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

TAB_TITLE = "🔍 Search"

def rgb(r, g, b):
    return {"red": r/255, "green": g/255, "blue": b/255}

def fmt(bg, fg, bold=False, size=10, align="LEFT", valign="MIDDLE", wrap="CLIP"):
    return {
        "backgroundColor": bg,
        "textFormat": {"foregroundColor": fg, "bold": bold, "fontSize": size},
        "horizontalAlignment": align,
        "verticalAlignment": valign,
        "wrapStrategy": wrap,
    }

def repeat(sheet_id, r1, c1, r2, c2, cell_fmt):
    return {"repeatCell": {
        "range": {"sheetId": sheet_id, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "cell": {"userEnteredFormat": cell_fmt},
        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
    }}

def merge(sheet_id, r1, c1, r2, c2):
    return {"mergeCells": {
        "range": {"sheetId": sheet_id, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "mergeType": "MERGE_ALL",
    }}

def col_width(sheet_id, col, px):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                  "startIndex": col, "endIndex": col+1},
        "properties": {"pixelSize": px}, "fields": "pixelSize",
    }}

def row_height(sheet_id, r1, r2, px):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sheet_id, "dimension": "ROWS",
                  "startIndex": r1, "endIndex": r2},
        "properties": {"pixelSize": px}, "fields": "pixelSize",
    }}

def border(sheet_id, r1, c1, r2, c2, color):
    style = {"style": "SOLID", "color": color}
    return {"updateBorders": {
        "range": {"sheetId": sheet_id, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "top": style, "bottom": style, "left": style, "right": style,
    }}

NAVY      = rgb(26, 35, 126)
NAVY_DARK = rgb(13, 17, 63)
WHITE     = rgb(255, 255, 255)
GREY      = rgb(245, 247, 250)
DARK      = rgb(30, 30, 30)
TEAL      = rgb(0, 150, 136)
BORDER    = rgb(180, 200, 215)

NUM_COLS = 27   # Agency col + 26 agency tab cols (incl. SLR Views, OnlyFans, Twitter, Instagram)


def main():
    creds   = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc      = gspread.authorize(creds)
    service = build("sheets", "v4", credentials=creds)
    ss      = gc.open_by_key(SPREADSHEET_ID)

    # ── Get or create tab ────────────────────────────────────────────────────
    existing = {ws.title: ws for ws in ss.worksheets()}
    if TAB_TITLE in existing:
        ws = existing[TAB_TITLE]
        ws.clear()
        ws.resize(rows=500, cols=NUM_COLS)
        print(f"Cleared existing '{TAB_TITLE}' tab.")
    else:
        ws = ss.add_worksheet(title=TAB_TITLE, rows=500, cols=NUM_COLS)
        print(f"Created '{TAB_TITLE}' tab.")

    sheet_id = ws.id

    # Move to second position (after Legend)
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "index": 1},
            "fields": "index",
        }}]}
    ).execute()

    # ── Write static cell values ──────────────────────────────────────────────
    # Row 9 = permanent column header (matches Agency + agency tab column order)
    HEADER_ROW = [
        "Agency", "Name", "Age", "AVG Rate", "Rank", "Location",
        "Available For", "Height", "Weight", "Measurements", "Hair", "Eyes",
        "Natural Breasts", "Tattoos", "Shoe Size", "Notes",
        "SLR Followers", "SLR Scenes", "SLR Views",
        "VRP Followers", "VRP Views", "POVR Views",
        "OnlyFans", "Twitter", "Instagram",
        "Bookings", "Last Booked Date",
        "SLR Profile", "VRP Profile",
    ]
    ws.update([
        ["🔍  MODEL SEARCH"],
        [""],
        ["Search name:"],
        [""],
        ["Type a name to search all agency tabs — results appear below."],
        [""],
        ["Results appear below automatically as you type."],
        ["To export: use the  🔍 Search Tools  menu → Export Results to CSV"],
        HEADER_ROW,
    ], "A1", value_input_option="RAW")

    # ── Formatting requests ───────────────────────────────────────────────────
    reqs = []

    # Column widths — col 0 = label (also "Agency" in results), col 1 = Name/input
    # These match the agency tab column order (Agency prepended by Apps Script)
    col_widths = [
        (0,  140),  # Agency
        (1,  195),  # Name  (also the search input box spans B3:D3)
        (2,   44),  # Age
        (3,   82),  # AVG Rate
        (4,   92),  # Rank
        (5,   72),  # Location
        (6,  290),  # Available For
        (7,   72),  # Height
        (8,   62),  # Weight
        (9,  108),  # Measurements
        (10,  78),  # Hair
        (11,  68),  # Eyes
        (12,  98),  # Natural Breasts
        (13,  72),  # Tattoos
        (14,  70),  # Shoe Size
        (15, 275),  # Notes
        (16,  88),  # SLR Followers
        (17,  72),  # SLR Scenes
        (18,  80),  # SLR Views
        (19,  88),  # VRP Followers
        (20,  80),  # VRP Views
        (21,  80),  # POVR Views
        (22,  88),  # OnlyFans
        (23,  80),  # Twitter
        (24,  80),  # Instagram
        (25,  72),  # Bookings
        (26, 110),  # Last Booked Date
    ]
    for col, px in col_widths:
        reqs.append(col_width(sheet_id, col, px))

    # Row 1: title bar — tall, navy, full width (LEFT aligned so text is visible at any zoom)
    reqs.append(row_height(sheet_id, 0, 1, 44))
    reqs.append(merge(sheet_id, 0, 0, 1, NUM_COLS))
    reqs.append(repeat(sheet_id, 0, 0, 1, NUM_COLS,
        fmt(NAVY, WHITE, bold=True, size=14, align="LEFT")))

    # Row 2: subtitle bar — dark navy, full width
    reqs.append(row_height(sheet_id, 1, 2, 16))
    reqs.append(merge(sheet_id, 1, 0, 2, NUM_COLS))
    reqs.append(repeat(sheet_id, 1, 0, 2, NUM_COLS,
        fmt(NAVY_DARK, rgb(180, 190, 220), bold=False, size=8, align="LEFT")))

    # Row 3: "Search name:" label + input box
    reqs.append(row_height(sheet_id, 2, 3, 36))
    # Full row background
    reqs.append(repeat(sheet_id, 2, 0, 3, NUM_COLS,
        fmt(GREY, DARK, bold=False, size=9)))
    # Label cell A3
    reqs.append(repeat(sheet_id, 2, 0, 3, 1,
        fmt(GREY, DARK, bold=True, size=11, align="RIGHT", valign="MIDDLE")))
    # Input cells B3:D3 — white box with teal border
    reqs.append(merge(sheet_id, 2, 1, 3, 4))
    reqs.append(repeat(sheet_id, 2, 1, 3, 4,
        fmt(WHITE, DARK, bold=False, size=12, valign="MIDDLE")))
    reqs.append(border(sheet_id, 2, 1, 3, 4, TEAL))

    # Row 4: spacer
    reqs.append(row_height(sheet_id, 3, 4, 6))
    reqs.append(repeat(sheet_id, 3, 0, 4, NUM_COLS, fmt(WHITE, WHITE)))

    # Row 5: status message row — full width
    reqs.append(row_height(sheet_id, 4, 5, 26))
    reqs.append(merge(sheet_id, 4, 0, 5, NUM_COLS))
    reqs.append(repeat(sheet_id, 4, 0, 5, NUM_COLS,
        fmt(rgb(232, 245, 233), rgb(27, 94, 32), bold=False, size=10, align="LEFT")))

    # Row 6: spacer
    reqs.append(row_height(sheet_id, 5, 6, 6))
    reqs.append(repeat(sheet_id, 5, 0, 6, NUM_COLS, fmt(WHITE, WHITE)))

    # Rows 7-8: instruction text — full width, left aligned
    reqs.append(row_height(sheet_id, 6, 8, 20))
    for r in (6, 7):
        reqs.append(merge(sheet_id, r, 0, r + 1, NUM_COLS))
        reqs.append(repeat(sheet_id, r, 0, r + 1, NUM_COLS,
            fmt(rgb(248, 249, 255), rgb(90, 90, 120), bold=False, size=9,
                align="LEFT")))

    # Row 9: permanent column header row — navy, white bold (always visible)
    reqs.append(row_height(sheet_id, 8, 9, 24))
    reqs.append(repeat(sheet_id, 8, 0, 9, NUM_COLS,
        fmt(NAVY, WHITE, bold=True, size=9, align="LEFT", valign="MIDDLE", wrap="CLIP")))

    # Row 10+: results area — white
    reqs.append(repeat(sheet_id, 9, 0, 500, NUM_COLS,
        fmt(WHITE, DARK, size=9)))

    # Hide gridlines
    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sheet_id,
                       "gridProperties": {"hideGridlines": True}},
        "fields": "gridProperties.hideGridlines",
    }})

    # Freeze rows 1-9 (title + search box + status + instructions + column header)
    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sheet_id,
                       "gridProperties": {"frozenRowCount": 9}},
        "fields": "gridProperties.frozenRowCount",
    }})

    # Send
    chunk = 50
    for i in range(0, len(reqs), chunk):
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"requests": reqs[i:i+chunk]}
        ).execute()

    print(f"Search tab formatted. Now inject the Apps Script to enable live search.")


if __name__ == "__main__":
    main()
