#!/usr/bin/env python3
"""
add_enhancements.py
===================
Adds the following to all agency tabs:
  1. Title bar (row 1) updated to HYPERLINK using the website URL from row 2
  2. "Status" column appended — dropdown: Active / On Break / Retired / Do Not Book
  3. "Bookings" formula column — extracts count from Dates Booked
  4. "Last Booked Date" formula column — extracts date from Dates Booked
  5. Stale model conditional format — light purple row when booked before but 12+ months ago

Usage:
    python3 /Users/andrewninn/Scripts/add_enhancements.py
"""

import os, re
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread

SPREADSHEET_ID       = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SKIP_TABS  = {'📋 Legend', '🔍 Search', 'Export', '📊 Dashboard'}
HEADER_ROW = 2   # 0-indexed row 3
DATA_START = 3   # 0-indexed row 4


def rgb(r, g, b):
    return {"red": r / 255, "green": g / 255, "blue": b / 255}


NAVY   = rgb(26, 35, 126)
WHITE  = rgb(255, 255, 255)
TEAL   = rgb(0, 150, 136)
PURPLE = rgb(74, 20, 140)


def col_letter(idx):
    """0-based column index → A1 letter (e.g. 0→A, 25→Z, 26→AA)"""
    result = ""
    n = idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def col_header_fmt(sheet_id, col_idx, bg_color):
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": HEADER_ROW, "endRowIndex": HEADER_ROW + 1,
                "startColumnIndex": col_idx, "endColumnIndex": col_idx + 1,
            },
            "cell": {"userEnteredFormat": {
                "backgroundColor": bg_color,
                "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
        }
    }


def col_width(sheet_id, col_idx, px):
    return {
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": col_idx, "endIndex": col_idx + 1},
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    }


def main():
    creds   = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc      = gspread.authorize(creds)
    service = build("sheets", "v4", credentials=creds)
    ss      = gc.open_by_key(SPREADSHEET_ID)

    for ws in ss.worksheets():
        name = ws.title
        if name in SKIP_TABS:
            continue

        print(f"\n── {name} ──")
        sheet_id = ws.id

        data = ws.get_all_values()
        if len(data) < 4:
            print("  [SKIP] Not enough rows")
            continue

        # Row 2 (0-indexed 1): website URL — scan all cells for http
        website_url = ""
        if len(data) > 1:
            for cell in data[1]:
                val = str(cell).strip()
                if val.startswith("http://") or val.startswith("https://"):
                    website_url = val
                    break

        # Row 3 (0-indexed 2): column headers
        headers = [h.strip() for h in data[HEADER_ROW]]
        col_map = {h: i for i, h in enumerate(headers) if h}

        if "Name" not in col_map:
            print("  [SKIP] No Name column")
            continue

        reqs = []

        # ── 1. Title bar → HYPERLINK ──────────────────────────────────────────
        if website_url and (website_url.startswith("http://") or website_url.startswith("https://")):
            safe_url  = website_url.replace('"', "")
            safe_name = name.replace('"', "")
            formula = f'=HYPERLINK("{safe_url}","{safe_name}")'
            # Write formula to A1 (top-left of the merged title cell)
            reqs.append({
                "updateCells": {
                    "rows": [{"values": [{"userEnteredValue": {"formulaValue": formula}}]}],
                    "fields": "userEnteredValue",
                    "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
                }
            })
            # Keep text white + bold + not underlined (override default link style)
            num_cols = max(len(headers), 8)
            reqs.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0, "endRowIndex": 1,
                        "startColumnIndex": 0, "endColumnIndex": num_cols,
                    },
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": NAVY,
                        "textFormat": {
                            "foregroundColor": WHITE,
                            "bold": True,
                            "fontSize": 11,
                            "underline": False,
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }},
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
                }
            })
            print(f"  Hyperlink → {safe_url}")
        else:
            print(f"  No valid URL in row 2 (found: '{website_url[:40] if website_url else ''}')")

        # ── 2. Determine new column positions ─────────────────────────────────
        existing  = set(headers)
        last_idx  = max(len(headers) - 1, 0)

        status_idx      = col_map.get("Status",          last_idx + 1)
        bookings_idx    = col_map.get("Bookings",        last_idx + (1 if "Status"          not in existing else 0) + (1 if "Status" not in existing else 0))
        last_booked_idx = col_map.get("Last Booked Date", last_idx + (1 if "Status" not in existing else 0) + (1 if "Bookings" not in existing else 0) + (1 if "Status" not in existing else 0))

        # Recalculate cleanly
        offset = last_idx + 1
        if "Status" not in existing:
            status_idx = offset
            offset += 1
        if "Bookings" not in existing:
            bookings_idx = offset
            offset += 1
        if "Last Booked Date" not in existing:
            last_booked_idx = offset

        dates_col = col_letter(col_map.get("Dates Booked", 6))
        first_row  = DATA_START + 1  # 1-indexed first data row

        # ── 3. Status column header + validation ──────────────────────────────
        if "Status" not in existing:
            reqs.append({
                "updateCells": {
                    "rows": [{"values": [{"userEnteredValue": {"stringValue": "Status"}}]}],
                    "fields": "userEnteredValue",
                    "start": {"sheetId": sheet_id, "rowIndex": HEADER_ROW, "columnIndex": status_idx},
                }
            })
            reqs.append(col_header_fmt(sheet_id, status_idx, TEAL))
            reqs.append(col_width(sheet_id, status_idx, 105))
            reqs.append({
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": DATA_START, "endRowIndex": 1000,
                        "startColumnIndex": status_idx, "endColumnIndex": status_idx + 1,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [
                                {"userEnteredValue": "Active"},
                                {"userEnteredValue": "On Break"},
                                {"userEnteredValue": "Retired"},
                                {"userEnteredValue": "Do Not Book"},
                            ]
                        },
                        "showCustomUi": True,
                        "strict": False,
                    }
                }
            })

        # ── 4. Bookings + Last Booked Date headers ────────────────────────────
        for col_idx, hdr_text in [(bookings_idx, "Bookings"), (last_booked_idx, "Last Booked Date")]:
            if hdr_text not in existing:
                reqs.append({
                    "updateCells": {
                        "rows": [{"values": [{"userEnteredValue": {"stringValue": hdr_text}}]}],
                        "fields": "userEnteredValue",
                        "start": {"sheetId": sheet_id, "rowIndex": HEADER_ROW, "columnIndex": col_idx},
                    }
                })
                reqs.append(col_header_fmt(sheet_id, col_idx, PURPLE))
                reqs.append(col_width(sheet_id, col_idx, 82 if hdr_text == "Bookings" else 110))

        # ── 5. Stale conditional format ───────────────────────────────────────
        lbd_letter = col_letter(last_booked_idx)
        last_used  = max(col_map.values()) + 3   # cover new cols
        stale_formula = (
            f"=AND(${lbd_letter}{first_row}<>\"\","
            f"${lbd_letter}{first_row}<EDATE(TODAY(),-12))"
        )
        reqs.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sheet_id,
                        "startRowIndex": DATA_START, "endRowIndex": 1000,
                        "startColumnIndex": 0, "endColumnIndex": last_used,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": stale_formula}],
                        },
                        "format": {
                            "backgroundColor": rgb(243, 229, 245),  # light purple
                            "textFormat": {"foregroundColor": rgb(74, 20, 140), "italic": True},
                        },
                    },
                },
                "index": 97,
            }
        })

        # Send header / format / validation requests
        if reqs:
            chunk = 50
            for i in range(0, len(reqs), chunk):
                service.spreadsheets().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body={"requests": reqs[i:i + chunk]}
                ).execute()
            print(f"  Headers, validation & stale flag applied.")

        # ── 6. Write formula cells ─────────────────────────────────────────────
        formula_reqs = []
        for row_idx in range(DATA_START, len(data)):
            row = data[row_idx]
            if not any(row):
                continue
            r = row_idx + 1  # 1-indexed

            dc = f"{dates_col}{r}"   # e.g. G4

            if "Bookings" not in existing:
                bf = f'=IFERROR(VALUE(LEFT(TRIM({dc}),FIND("x",TRIM({dc}))-1)),"")'
                formula_reqs.append({
                    "updateCells": {
                        "rows": [{"values": [{"userEnteredValue": {"formulaValue": bf}}]}],
                        "fields": "userEnteredValue",
                        "start": {"sheetId": sheet_id, "rowIndex": row_idx, "columnIndex": bookings_idx},
                    }
                })

            if "Last Booked Date" not in existing:
                # Parse "Nx · Mon YYYY" → DATE(year, month_num, 1)
                # The middle dot is U+00B7 (·)
                lf = (
                    f'=IFERROR(DATE('
                    f'VALUE(RIGHT(TRIM({dc}),4)),'
                    f'MATCH(LEFT(TRIM(MID({dc},FIND("\u00b7",{dc})+2,100)),3),'
                    f'{{"Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"}},0),'
                    f'1),"")'
                )
                formula_reqs.append({
                    "updateCells": {
                        "rows": [{"values": [{"userEnteredValue": {"formulaValue": lf}}]}],
                        "fields": "userEnteredValue",
                        "start": {"sheetId": sheet_id, "rowIndex": row_idx, "columnIndex": last_booked_idx},
                    }
                })

        if formula_reqs:
            chunk = 100
            for i in range(0, len(formula_reqs), chunk):
                service.spreadsheets().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body={"requests": formula_reqs[i:i + chunk]}
                ).execute()
            print(f"  Formulas written for {len(formula_reqs) // (2 if 'Bookings' not in existing and 'Last Booked Date' not in existing else 1)} data rows.")

    print("\n✅ All enhancements applied.")


if __name__ == "__main__":
    main()
