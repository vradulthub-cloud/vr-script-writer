"""
fix_column_structure.py

For every agency tab EXCEPT OC Models:
  1. Deletes the "Shoot Types" column if present
  2. Moves "Available For" to be immediately after "Location" (to match OC Models)
  3. Ensures "Notes" column is the last column before any blank cols

Then re-runs formatting replication from OC Models.

Usage:
    python3 /Users/andrewninn/Scripts/fix_column_structure.py
"""

import os
import time
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID = '1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw'
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'service_account.json')
SOURCE_TAB = 'OC Models'
HEADER_ROW_IDX = 2  # 0-indexed (row 3 in sheet)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

# Expected column order matching OC Models (after fixes)
EXPECTED_HEADERS = [
    'Name', 'Age', 'AVG Rate', 'Rank', 'Location',
    'Available For', 'Height', 'Weight', 'Measurements',
    'Hair', 'Eyes', 'Natural Breasts', 'Tattoos', 'Shoe Size', 'Notes'
]


def get_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)


def get_all_sheets(service):
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    return meta['sheets']


def get_sheet_headers(service, sheet_title):
    """Returns list of (col_index, header_text) for row 3."""
    range_name = f"'{sheet_title}'!A3:Z3"
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name
    ).execute()
    values = result.get('values', [[]])[0]
    return {v.strip(): i for i, v in enumerate(values) if v.strip()}


def delete_column(service, sheet_id, col_index):
    """Delete a single column by 0-based index."""
    return {
        'deleteDimension': {
            'range': {
                'sheetId': sheet_id,
                'dimension': 'COLUMNS',
                'startIndex': col_index,
                'endIndex': col_index + 1,
            }
        }
    }


def move_column(service, sheet_id, from_index, to_index):
    """Move a column from from_index to to_index (0-based)."""
    return {
        'moveDimension': {
            'source': {
                'sheetId': sheet_id,
                'dimension': 'COLUMNS',
                'startIndex': from_index,
                'endIndex': from_index + 1,
            },
            'destinationIndex': to_index
        }
    }


def fix_tab(service, sheet_title, sheet_id):
    print(f"\n  [{sheet_title}]")
    headers = get_sheet_headers(service, sheet_title)
    print(f"    Current headers: {list(headers.keys())}")

    requests = []

    # ── Step 1: Delete "Shoot Types" if present ─────────────────────────────
    shoot_types_variants = ['Shoot Types', 'Shoot Type', 'ShootTypes']
    deleted_col = None
    for variant in shoot_types_variants:
        if variant in headers:
            col_idx = headers[variant]
            print(f"    → Deleting '{variant}' at col {col_idx}")
            requests.append(delete_column(service, sheet_id, col_idx))
            deleted_col = col_idx
            break

    # Execute deletion first so column indices are correct for next step
    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={'requests': requests}
        ).execute()
        time.sleep(1)
        requests = []
        # Refresh headers after deletion
        headers = get_sheet_headers(service, sheet_title)
        print(f"    Headers after deletion: {list(headers.keys())}")

    # ── Step 2: Move "Available For" to right after "Location" ──────────────
    if 'Available For' in headers and 'Location' in headers:
        avail_idx = headers['Available For']
        loc_idx = headers['Location']
        target_idx = loc_idx + 1

        if avail_idx != target_idx:
            print(f"    → Moving 'Available For' from col {avail_idx} to col {target_idx}")
            requests.append(move_column(service, sheet_id, avail_idx, target_idx))
        else:
            print(f"    ✓ 'Available For' already at correct position (col {avail_idx})")
    else:
        missing = []
        if 'Available For' not in headers:
            missing.append('Available For')
        if 'Location' not in headers:
            missing.append('Location')
        print(f"    ⚠ Missing columns: {missing} — skipping reorder")

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={'requests': requests}
        ).execute()
        time.sleep(1)

    # ── Step 3: Verify final order ───────────────────────────────────────────
    final_headers = get_sheet_headers(service, sheet_title)
    print(f"    Final headers:   {list(final_headers.keys())}")


def get_source_formatting(service):
    """Fetch all formatting from OC Models."""
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID,
        includeGridData=True,
        ranges=[f"'{SOURCE_TAB}'!A1:Z5"]
    ).execute()

    source_sheet = None
    for sheet in spreadsheet['sheets']:
        if sheet['properties']['title'] == SOURCE_TAB:
            source_sheet = sheet
            break

    props = source_sheet['properties']
    grid_props = props.get('gridProperties', {})
    data = source_sheet.get('data', [])
    grid_data = data[0] if data else {}

    col_widths = [c.get('pixelSize', 100) for c in grid_data.get('columnMetadata', [])]
    row_heights = [r.get('pixelSize', 21) for r in grid_data.get('rowMetadata', [])]
    frozen_rows = grid_props.get('frozenRowCount', 0)
    frozen_cols = grid_props.get('frozenColumnCount', 0)

    header_formats = []
    if data:
        rows = data[0].get('rowData', [])
        if len(rows) > HEADER_ROW_IDX:
            for cell in rows[HEADER_ROW_IDX].get('values', []):
                user_fmt = cell.get('userEnteredFormat', {})
                eff_fmt = cell.get('effectiveFormat', {})
                header_formats.append(user_fmt if user_fmt else eff_fmt)

    return {
        'col_widths': col_widths,
        'row_heights': row_heights,
        'frozen_rows': frozen_rows,
        'frozen_cols': frozen_cols,
        'header_formats': header_formats,
    }


def build_format_requests(sheet_id, source_fmt, target_col_count, target_row_count):
    requests = []

    # Frozen rows/cols
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

    # Column widths
    for col_idx, width in enumerate(source_fmt['col_widths']):
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

    # Row heights
    for row_idx, height in enumerate(source_fmt['row_heights']):
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

    # Header cell formats
    for col_idx, fmt in enumerate(source_fmt['header_formats']):
        if not fmt or col_idx >= target_col_count:
            break
        requests.append({
            'repeatCell': {
                'range': {
                    'sheetId': sheet_id,
                    'startRowIndex': HEADER_ROW_IDX,
                    'endRowIndex': HEADER_ROW_IDX + 1,
                    'startColumnIndex': col_idx,
                    'endColumnIndex': col_idx + 1,
                },
                'cell': {'userEnteredFormat': fmt},
                'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy,borders,padding)'
            }
        })

    return requests


def main():
    print("Connecting to Sheets API...")
    service = get_service()

    all_sheets = get_all_sheets(service)
    target_sheets = [s for s in all_sheets if s['properties']['title'] != SOURCE_TAB]

    # ── Phase 1: Fix column structure on all tabs ────────────────────────────
    print("\n═══ Phase 1: Fixing column structure ═══")
    for sheet in target_sheets:
        fix_tab(service, sheet['properties']['title'], sheet['properties']['sheetId'])

    # ── Phase 2: Re-apply formatting from OC Models ──────────────────────────
    print("\n═══ Phase 2: Replicating formatting from OC Models ═══")
    source_fmt = get_source_formatting(service)
    print(f"  Columns: {len(source_fmt['col_widths'])}, Rows: {len(source_fmt['row_heights'])}, Header cells: {len(source_fmt['header_formats'])}")

    # Re-fetch sheet metadata (column counts may have changed after deletions)
    all_sheets = get_all_sheets(service)
    target_sheets = [s for s in all_sheets if s['properties']['title'] != SOURCE_TAB]

    all_requests = []
    for sheet in target_sheets:
        title = sheet['properties']['title']
        sheet_id = sheet['properties']['sheetId']
        grid = sheet['properties'].get('gridProperties', {})
        col_count = grid.get('columnCount', 26)
        row_count = grid.get('rowCount', 1000)
        reqs = build_format_requests(sheet_id, source_fmt,
                                     min(len(source_fmt['col_widths']), col_count),
                                     min(len(source_fmt['row_heights']), row_count))
        all_requests.extend(reqs)
        print(f"  Queued {len(reqs):3d} requests for: {title}")

    print(f"\n  Sending {len(all_requests)} total requests...")
    BATCH = 400
    for i in range(0, len(all_requests), BATCH):
        batch = all_requests[i:i + BATCH]
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={'requests': batch}
        ).execute()
        print(f"  Sent {i+1}–{min(i+BATCH, len(all_requests))}")

    print("\nAll done. Open the sheet to verify.")


if __name__ == '__main__':
    main()
