"""
replicate_formatting.py

Reads the exact formatting from the OC Models tab (column widths, row heights,
header background colors, font styles, frozen rows) and replicates it across
all other agency tabs in the Model Booking List.

Usage:
    python3 /Users/andrewninn/Scripts/replicate_formatting.py

The script uses the Sheets API batchUpdate to apply formatting in bulk.
"""

import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID = '1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw'
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'service_account.json')
SOURCE_TAB = 'OC Models'
HEADER_ROW = 2   # 0-indexed row 2 = sheet row 3

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]


def get_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)


def get_spreadsheet(service):
    # Fetch rows 1-5 across all columns to capture column/row metadata and header formats
    return service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID,
        includeGridData=True,
        ranges=[f"'{SOURCE_TAB}'!A1:Z5"]
    ).execute()


def get_all_sheets(service):
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    return meta['sheets']


def extract_source_formatting(spreadsheet):
    """Extract column widths, row heights, and header cell formats from OC Models."""
    source_sheet = None
    for sheet in spreadsheet['sheets']:
        if sheet['properties']['title'] == SOURCE_TAB:
            source_sheet = sheet
            break

    if not source_sheet:
        raise ValueError(f"Source tab '{SOURCE_TAB}' not found")

    props = source_sheet['properties']
    grid_props = props.get('gridProperties', {})

    # columnMetadata and rowMetadata live inside data[0] (GridData), not the sheet root
    data = source_sheet.get('data', [])
    grid_data = data[0] if data else {}

    # Column widths
    col_metadata = grid_data.get('columnMetadata', [])
    col_widths = []
    for col in col_metadata:
        col_widths.append(col.get('pixelSize', 100))

    # Row heights
    row_metadata = grid_data.get('rowMetadata', [])
    row_heights = []
    for row in row_metadata:
        row_heights.append(row.get('pixelSize', 21))

    # Frozen rows/cols
    frozen_rows = grid_props.get('frozenRowCount', 0)
    frozen_cols = grid_props.get('frozenColumnCount', 0)

    # Header cell formats from row 3 (0-indexed row 2)
    header_formats = []
    if data:
        rows = data[0].get('rowData', [])
        if len(rows) > HEADER_ROW:
            header_row = rows[HEADER_ROW]
            for cell in header_row.get('values', []):
                fmt = cell.get('effectiveFormat', {})
                user_fmt = cell.get('userEnteredFormat', {})
                header_formats.append(user_fmt if user_fmt else fmt)

    # Data row format (row 4, 0-indexed row 3) — for alternating row colors etc.
    data_row_format = None
    if data:
        rows = data[0].get('rowData', [])
        if len(rows) > HEADER_ROW + 1:
            data_row = rows[HEADER_ROW + 1]
            cells = data_row.get('values', [])
            if cells:
                fmt = cells[0].get('userEnteredFormat', {})
                data_row_format = fmt

    return {
        'col_widths': col_widths,
        'row_heights': row_heights,
        'frozen_rows': frozen_rows,
        'frozen_cols': frozen_cols,
        'header_formats': header_formats,
        'data_row_format': data_row_format,
        'source_sheet_id': props['sheetId'],
    }


def build_requests_for_sheet(sheet_id, source_fmt, target_col_count, target_row_count):
    """Build a list of batchUpdate requests to apply source formatting to target sheet."""
    requests = []

    # ── 1. Frozen rows/cols ──────────────────────────────────────────────────
    requests.append({
        'updateSheetProperties': {
            'properties': {
                'sheetId': sheet_id,
                'gridProperties': {
                    'frozenRowCount': source_fmt['frozen_rows'],
                    'frozenColumnCount': source_fmt['frozen_cols'],
                }
            },
            'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'
        }
    })

    # ── 2. Column widths ─────────────────────────────────────────────────────
    col_widths = source_fmt['col_widths']
    for col_idx, width in enumerate(col_widths):
        if col_idx >= target_col_count:
            break
        if width > 0:
            requests.append({
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': col_idx,
                        'endIndex': col_idx + 1,
                    },
                    'properties': {'pixelSize': width},
                    'fields': 'pixelSize'
                }
            })

    # ── 3. Row heights ───────────────────────────────────────────────────────
    row_heights = source_fmt['row_heights']
    for row_idx, height in enumerate(row_heights):
        if row_idx >= target_row_count:
            break
        if height > 0:
            requests.append({
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'ROWS',
                        'startIndex': row_idx,
                        'endIndex': row_idx + 1,
                    },
                    'properties': {'pixelSize': height},
                    'fields': 'pixelSize'
                }
            })

    # ── 4. Header row cell formats ───────────────────────────────────────────
    header_formats = source_fmt['header_formats']
    for col_idx, fmt in enumerate(header_formats):
        if not fmt:
            continue
        if col_idx >= target_col_count:
            break
        requests.append({
            'repeatCell': {
                'range': {
                    'sheetId': sheet_id,
                    'startRowIndex': HEADER_ROW,
                    'endRowIndex': HEADER_ROW + 1,
                    'startColumnIndex': col_idx,
                    'endColumnIndex': col_idx + 1,
                },
                'cell': {'userEnteredFormat': fmt},
                'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy,borders,padding)'
            }
        })

    return requests


def main():
    print("Connecting to Google Sheets API...")
    service = get_service()

    print(f"Fetching source formatting from '{SOURCE_TAB}'...")
    spreadsheet = get_spreadsheet(service)
    source_fmt = extract_source_formatting(spreadsheet)

    print(f"  Column widths captured: {len(source_fmt['col_widths'])} columns")
    print(f"  Row heights captured:   {len(source_fmt['row_heights'])} rows")
    print(f"  Header formats:         {len(source_fmt['header_formats'])} cells")
    print(f"  Frozen rows: {source_fmt['frozen_rows']}, Frozen cols: {source_fmt['frozen_cols']}")
    print()

    # Get all sheets metadata
    all_sheets = get_all_sheets(service)

    # Filter to all tabs except the source
    target_sheets = [
        s for s in all_sheets
        if s['properties']['title'] != SOURCE_TAB
    ]

    print(f"Found {len(target_sheets)} target tab(s) to update:\n")
    for s in target_sheets:
        print(f"  • {s['properties']['title']}")
    print()

    all_requests = []
    for sheet in target_sheets:
        title = sheet['properties']['title']
        sheet_id = sheet['properties']['sheetId']
        grid = sheet['properties'].get('gridProperties', {})
        row_count = grid.get('rowCount', 1000)
        col_count = grid.get('columnCount', 26)

        target_cols = min(len(source_fmt['col_widths']), col_count)
        target_rows = min(len(source_fmt['row_heights']), row_count)

        reqs = build_requests_for_sheet(sheet_id, source_fmt, target_cols, target_rows)
        all_requests.extend(reqs)
        print(f"  Queued {len(reqs):3d} formatting requests for: {title}")

    print(f"\nSending {len(all_requests)} total requests in batches...")

    # Sheets API batchUpdate limit is 500 requests per call
    BATCH_SIZE = 400
    for i in range(0, len(all_requests), BATCH_SIZE):
        batch = all_requests[i:i + BATCH_SIZE]
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={'requests': batch}
        ).execute()
        end = min(i + BATCH_SIZE, len(all_requests))
        print(f"  Sent requests {i + 1}–{end}")

    print("\nDone! Formatting has been replicated to all agency tabs.")
    print("Open the sheet to verify the results.")


if __name__ == '__main__':
    main()
