"""
Apply v3 block-per-comp chrome to the Comp Planning Google Sheet.

Creates (or refreshes) FPVR Index / VRH Index / VRA Index / NJOI Index tabs with:
  - 8-column layout for the block-per-comp design
  - Studio accent stripe in column A (always visible — frozen)
  - Hidden gridlines
  - Column widths tuned for the block layout

Data is written by the Hub API (one block per comp on save).
This script only sets up the visual chrome — safe to re-run.

Usage:
  cd /Users/andrewninn/Scripts && python3 redesign_comp_sheet.py
"""

from __future__ import annotations

import os
import sys

import gspread
from google.oauth2.service_account import Credentials

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SA_PATH = os.path.join(SCRIPTS_DIR, "service_account.json")
SHEET_ID = "1i6W4eZ8Bva3HvVmhpAVgjeHwfqbARkwBZ38aUhriaGs"

# v3 column layout (0-indexed for batchUpdate)
# A=0  accent stripe (narrow, always visible)
# B=1  Comp ID (title rows) / Scene # (scene rows)
# C=2  empty (title rows) / Scene ID — monospace (scene rows)
# D=3  Comp Title (title rows) / Scene Title (scene rows)
# E=4  "Vol. X · STATUS" (title rows) / Performers (scene rows)
# F=5  MEGA link (scene rows)
# G=6  SLR link (scene rows)
# H=7  Notes (scene rows)
COL_WIDTHS = [15, 95, 120, 280, 165, 225, 100, 185]
NUM_COLS = len(COL_WIDTHS)

STUDIO_TABS = [
    ("FPVR Index", {"r": 0.231, "g": 0.510, "b": 0.965}),  # blue
    ("VRH Index",  {"r": 0.545, "g": 0.361, "b": 0.965}),  # purple
    ("VRA Index",  {"r": 0.925, "g": 0.282, "b": 0.600}),  # pink
    ("NJOI Index", {"r": 0.976, "g": 0.451, "b": 0.086}),  # orange
]


def _rgb(r: float, g: float, b: float) -> dict:
    return {"red": r, "green": g, "blue": b}


def ensure_tab(sh: gspread.Spreadsheet, name: str) -> gspread.Worksheet:
    try:
        ws = sh.worksheet(name)
        print(f"  ✓ existing: {name}")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=name, rows=3000, cols=NUM_COLS)
        print(f"  + created:  {name}")
    return ws


def apply_chrome(sh: gspread.Spreadsheet, ws: gspread.Worksheet, accent: dict) -> None:
    sid = ws.id
    accent_rgb = _rgb(accent["r"], accent["g"], accent["b"])
    requests: list[dict] = []

    # Sheet-level: hide gridlines, freeze col A
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sid,
                "gridProperties": {
                    "hideGridlines": True,
                    "frozenRowCount": 0,
                    "frozenColumnCount": 1,
                },
            },
            "fields": "gridProperties(hideGridlines,frozenRowCount,frozenColumnCount)",
        }
    })

    # Column widths
    for col_idx, px in enumerate(COL_WIDTHS):
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS",
                          "startIndex": col_idx, "endIndex": col_idx + 1},
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        })

    # Col A — solid studio accent fill (entire column, no text)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": accent_rgb,
                }
            },
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # Cols B-H — default body style
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startColumnIndex": 1, "endColumnIndex": NUM_COLS},
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {"fontSize": 10, "fontFamily": "Arial"},
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "CLIP",
                    "padding": {"top": 3, "bottom": 3, "left": 8, "right": 6},
                }
            },
            "fields": "userEnteredFormat(textFormat,verticalAlignment,wrapStrategy,padding)",
        }
    })

    sh.batch_update({"requests": requests})
    print("  ✓ chrome applied")


def main() -> int:
    creds = Credentials.from_service_account_file(
        SA_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    print(f"Opened: {sh.title} ({SHEET_ID})\n")

    for tab_name, accent in STUDIO_TABS:
        print(f"[{tab_name}]")
        ws = ensure_tab(sh, tab_name)
        apply_chrome(sh, ws, accent)
        print()

    print(f"Done → https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
