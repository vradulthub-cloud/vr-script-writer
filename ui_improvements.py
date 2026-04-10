#!/usr/bin/env python3
"""
ui_improvements.py
==================
Comprehensive UI polish across all tabs:
  - ALL tabs:       hide gridlines
  - Agency tabs:    unhide row 1 (agency name), format as navy title bar,
                    freeze rows 1-3 (title + header)
  - Search tab:     freeze rows 1-3, make search input row taller
  - Legend tab:     no extra changes beyond gridlines

Usage:
    python3 /Users/andrewninn/Scripts/ui_improvements.py
"""

import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID       = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SEARCH_TAB = "🔍 Search"
LEGEND_TAB = "📋 Legend"
SKIP_TABS  = {SEARCH_TAB, LEGEND_TAB, "Export", "📊 Dashboard"}

def rgb(r, g, b):
    return {"red": r/255, "green": g/255, "blue": b/255}

NAVY      = rgb(26, 35, 126)
NAVY_DARK = rgb(13, 17, 63)
WHITE     = rgb(255, 255, 255)


def hide_gridlines(sheet_id):
    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"hideGridlines": True},
            },
            "fields": "gridProperties.hideGridlines",
        }
    }


def set_freeze(sheet_id, rows, cols=None):
    props  = {"frozenRowCount": rows}
    fields = "gridProperties.frozenRowCount"
    if cols is not None:          # include 0 explicitly to clear freeze
        props["frozenColumnCount"] = cols
        fields += ",gridProperties.frozenColumnCount"
    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": props,
            },
            "fields": fields,
        }
    }


def set_row_height(sheet_id, start, end, px):
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId":    sheet_id,
                "dimension":  "ROWS",
                "startIndex": start,
                "endIndex":   end,
            },
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    }


def unhide_rows(sheet_id, start, end):
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId":    sheet_id,
                "dimension":  "ROWS",
                "startIndex": start,
                "endIndex":   end,
            },
            "properties": {"hiddenByUser": False},
            "fields": "hiddenByUser",
        }
    }


def unmerge_range(sheet_id, r1, c1, r2, c2):
    return {
        "unmergeCells": {
            "range": {
                "sheetId":          sheet_id,
                "startRowIndex":    r1,
                "endRowIndex":      r2,
                "startColumnIndex": c1,
                "endColumnIndex":   c2,
            }
        }
    }


def merge_range(sheet_id, r1, c1, r2, c2):
    return {
        "mergeCells": {
            "range": {
                "sheetId":          sheet_id,
                "startRowIndex":    r1,
                "endRowIndex":      r2,
                "startColumnIndex": c1,
                "endColumnIndex":   c2,
            },
            "mergeType": "MERGE_ALL",
        }
    }


def format_title_bar(sheet_id, r1, c1, r2, c2, value=None):
    cell = {
        "userEnteredFormat": {
            "backgroundColor": NAVY,
            "textFormat": {
                "foregroundColor": WHITE,
                "bold": True,
                "fontSize": 11,
            },
            "horizontalAlignment": "CENTER",
            "verticalAlignment":   "MIDDLE",
        }
    }
    if value is not None:
        cell["userEnteredValue"] = {"stringValue": value}
    fields = "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)"
    if value is not None:
        fields += ",userEnteredValue"
    return {
        "repeatCell": {
            "range": {
                "sheetId":          sheet_id,
                "startRowIndex":    r1,
                "endRowIndex":      r2,
                "startColumnIndex": c1,
                "endColumnIndex":   c2,
            },
            "cell": cell,
            "fields": fields,
        }
    }


def main():
    creds   = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)

    full_meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets    = full_meta["sheets"]

    requests = []

    for sheet in sheets:
        props      = sheet["properties"]
        sheet_id   = props["sheetId"]
        sheet_name = props["title"]

        print(f"  Processing: {sheet_name}")

        # Hide gridlines on every tab
        requests.append(hide_gridlines(sheet_id))

        # ── Search tab ─────────────────────────────────────────────────────────
        if sheet_name == SEARCH_TAB:
            # Freeze rows 1-3 (title + spacer + search box)
            requests.append(set_freeze(sheet_id, rows=3))
            # Make search input row (row 3, index 2) taller
            requests.append(set_row_height(sheet_id, 2, 3, 40))
            continue

        # ── Legend tab ─────────────────────────────────────────────────────────
        if sheet_name in SKIP_TABS:
            continue  # gridlines already added above

        # ── Agency tabs ────────────────────────────────────────────────────────

        # Get row 1 content (agency name) and row 3 headers (to know column count)
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{sheet_name}'!A1:Z3"
        ).execute()
        rows = result.get("values", [])

        agency_name = sheet_name  # always use the tab title — cell content is unreliable

        headers    = rows[2] if len(rows) >= 3 else []
        num_cols   = max(len(headers), 8)  # at least 8 columns wide

        # Two-step: must drop freeze first (committed), then merge+restore.
        try:
            # Step 1: unhide row 1, set height, drop column freeze
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": [
                    unhide_rows(sheet_id, 0, 1),
                    set_row_height(sheet_id, 0, 1, 32),
                    set_freeze(sheet_id, rows=0, cols=0),  # explicitly clears both
                ]}
            ).execute()
            # Step 2: unmerge, merge, format, restore freeze
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": [
                    unmerge_range(sheet_id, 0, 0, 1, num_cols),
                    merge_range(sheet_id, 0, 0, 1, num_cols),
                    format_title_bar(sheet_id, 0, 0, 1, num_cols, value=agency_name),
                    set_freeze(sheet_id, rows=3),  # no col freeze — row 1 is merged across all cols
                ]}
            ).execute()
            print(f"    Title bar applied: {sheet_name}")
        except Exception as e:
            print(f"    ERROR on {sheet_name}: {e}")

    if not requests:
        print("No requests to send.")
        return

    print(f"\nSending {len(requests)} formatting requests...")
    chunk_size = 50
    for i in range(0, len(requests), chunk_size):
        chunk = requests[i:i + chunk_size]
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": chunk}
            ).execute()
            print(f"  Chunk {i // chunk_size + 1}: {len(chunk)} requests OK")
        except Exception as e:
            print(f"  ERROR chunk {i // chunk_size + 1}: {e}")

    print("\nDone! Reload the spreadsheet to see all changes.")


if __name__ == "__main__":
    main()
