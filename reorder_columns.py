#!/usr/bin/env python3
"""
reorder_columns.py
==================
Reorders columns in every tab of the Model Booking List to:

  Name | Age | Location | AVG Rate | Rank | Notes | Dates Booked | Available For | [Stats Group]

Adds a "Dates Booked" column if it doesn't exist.
After this runs, re-run beautify_sheet.py to re-apply header colors / widths / groups.

Usage:
    python3 /Users/andrewninn/Scripts/reorder_columns.py
"""

import os
import time
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID       = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW     = 3   # 1-indexed
HEADER_ROW_IDX = 2   # 0-indexed

# Desired final visible order (left of stats group)
TARGET_ORDER = [
    "Name", "Age", "Location", "AVG Rate", "Rank",
    "Notes", "Dates Booked", "Available For",
]

# Stats columns come after — their relative order doesn't change
STATS_COLS = ["Height", "Weight", "Measurements", "Hair", "Eyes",
              "Natural Breasts", "Tattoos", "Shoe Size",
              "SLR Followers", "SLR Scenes", "VRP Followers", "VRP Views", "POVR Views"]


def get_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def get_gspread():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def read_headers(service, sheet_title):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{sheet_title}'!A{HEADER_ROW}:Z{HEADER_ROW}"
    ).execute()
    return [str(h).strip() for h in result.get("values", [[]])[0]]


def compute_moves(headers, target_order):
    """
    Returns list of (src_idx, dst_idx, api_dest) tuples.
    api_dest is what to pass to the Sheets API moveDimension.
    - Moving left  (src > dst): api_dest = dst
    - Moving right (src < dst): api_dest = dst + 1
    Tracking list is updated after each move so subsequent moves see
    the post-move column positions.
    """
    current = list(headers)
    moves   = []

    for desired_pos, col_name in enumerate(target_order):
        if col_name not in current:
            continue  # will be inserted separately (Dates Booked) or doesn't exist

        src = current.index(col_name)
        if src == desired_pos:
            continue  # already in place

        api_dest = desired_pos if src > desired_pos else desired_pos + 1
        moves.append((src, desired_pos, api_dest))

        # Update tracking
        col = current.pop(src)
        current.insert(desired_pos, col)

    return moves, current


def req_move(sheet_id, src_idx, api_dest):
    return {
        "moveDimension": {
            "source": {
                "sheetId":    sheet_id,
                "dimension":  "COLUMNS",
                "startIndex": src_idx,
                "endIndex":   src_idx + 1,
            },
            "destinationIndex": api_dest,
        }
    }


def req_insert_column(sheet_id, col_idx):
    return {
        "insertDimension": {
            "range": {
                "sheetId":    sheet_id,
                "dimension":  "COLUMNS",
                "startIndex": col_idx,
                "endIndex":   col_idx + 1,
            },
            "inheritFromBefore": False,
        }
    }


def main():
    service = get_service()
    gc      = get_gspread()
    ss      = gc.open_by_key(SPREADSHEET_ID)

    meta   = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets = meta["sheets"]

    for sheet_info in sheets:
        props      = sheet_info["properties"]
        sheet_id   = props["sheetId"]
        sheet_name = props["title"]

        headers = read_headers(service, sheet_name)
        if not headers:
            print(f"  [SKIP] {sheet_name}: no headers")
            continue

        print(f"\n[{sheet_name}]")
        print(f"  Current: {headers}")

        # ── Step 1: move existing columns into target order ──────────────────
        # Only include columns that actually exist in this tab.
        # If Dates Booked doesn't exist yet, it's excluded — Available For will
        # land at position 6, then the insert shifts it to 7 automatically.
        # If Dates Booked already exists, it's included so Available For is
        # placed correctly after it.
        moves_target = [c for c in TARGET_ORDER if c in headers]
        moves, tracking = compute_moves(headers, moves_target)

        if moves:
            move_reqs = []
            # Each move must be applied sequentially (later moves depend on earlier ones)
            # We send each move individually to avoid index drift issues
            for src, dst, api_dest in moves:
                print(f"  Move '{headers[src] if src < len(headers) else '?'}' from {src} → {dst}  (api_dest={api_dest})")
                service.spreadsheets().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body={"requests": [req_move(sheet_id, src, api_dest)]}
                ).execute()
                # Refresh headers after each move for accurate tracking
                headers = read_headers(service, sheet_name)
                time.sleep(1.5)  # stay under 60 write requests/min
        else:
            print("  No column moves needed.")

        # ── Step 2: add "Dates Booked" if missing ────────────────────────────
        headers = read_headers(service, sheet_name)
        if "Dates Booked" not in headers:
            # Find Notes and Available For positions, insert between them
            if "Notes" in headers and "Available For" in headers:
                notes_idx  = headers.index("Notes")
                avail_idx  = headers.index("Available For")
                insert_at  = notes_idx + 1  # right after Notes
                print(f"  Adding 'Dates Booked' at column {insert_at}")
                service.spreadsheets().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body={"requests": [req_insert_column(sheet_id, insert_at)]}
                ).execute()
                time.sleep(1.5)
                # Write header value
                ws = ss.worksheet(sheet_name)
                from gspread.utils import rowcol_to_a1
                cell = rowcol_to_a1(HEADER_ROW, insert_at + 1)  # 1-indexed
                ws.update([["Dates Booked"]], cell)
                time.sleep(1.5)
                print(f"  'Dates Booked' header written at {cell}")
            else:
                print("  WARNING: couldn't find Notes/Available For to anchor Dates Booked insertion")
        else:
            print("  'Dates Booked' already exists.")

        # ── Final state ──────────────────────────────────────────────────────
        headers = read_headers(service, sheet_name)
        print(f"  Final:   {headers}")

    print("\n\nDone! Now run: python3 beautify_sheet.py")


if __name__ == "__main__":
    main()
