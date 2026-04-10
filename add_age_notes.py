#!/usr/bin/env python3
"""
add_age_notes.py
================
Adds a cell note to the Name cell of every model under 20, summarising
why the row is flagged and what action to take.

  Age 18, not booked       → 🚫 Absolute no-go note
  Age 18, booked before    → 🚫 No-go — note prior shoot history
  Age 19, booked before    → ⚠️  We've shot them — review before rebooking
  Age 19, no book/platform → ⚠️  No verified scenes — treat as no-go
  Age 19, has platform     → ⚠️  Has verified scenes on [X] — review before booking

Notes are always overwritten on re-run so they stay current.
Models 20+ have any existing age-warning note cleared.

Usage:
    python3 /Users/andrewninn/Scripts/add_age_notes.py
    python3 /Users/andrewninn/Scripts/add_age_notes.py --tab "East Coast Talent"
    python3 /Users/andrewninn/Scripts/add_age_notes.py --dry-run
"""

import argparse
import logging
import re
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID       = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = Path(__file__).parent / "service_account.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW     = 3
DATA_START_ROW = 4

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def parse_age(val: str) -> int | None:
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None


def platform_summary(row: dict) -> list[str]:
    """Return list of platform names that have data for this model."""
    found = []
    if row.get("SLR Followers", "").strip():
        found.append("SLR")
    if row.get("VRP Views", "").strip():
        found.append("VRPorn")
    if row.get("POVR Views", "").strip():
        found.append("POVR")
    return found


def build_note(age: int, platforms: list[str], dates_booked: str) -> str | None:
    """Return the note text for this model, or None if no note needed."""
    booked = dates_booked.strip()
    if age == 18:
        if booked:
            return (
                "🚫 AGE WARNING — 18 years old\n"
                f"Previously booked: {booked}\n"
                "Absolute no-go. Do not rebook regardless of prior history."
            )
        return (
            "🚫 AGE WARNING — 18 years old\n"
            "Absolute no-go. Do not book regardless of experience."
        )
    if age == 19:
        parts = []
        if booked:
            parts.append(f"Previously booked: {booked}")
        if platforms:
            parts.append(f"Verified scenes on: {', '.join(platforms)}")

        if booked and platforms:
            plat_str = ", ".join(platforms)
            return (
                f"⚠️ AGE WARNING — 19 years old\n"
                f"Previously booked: {booked}\n"
                f"Verified scenes on: {plat_str}\n"
                f"Known talent — confirm age docs are on file before rebooking."
            )
        if booked:
            return (
                f"⚠️ AGE WARNING — 19 years old\n"
                f"Previously booked: {booked}\n"
                f"No platform data found. Confirm age docs are on file before rebooking."
            )
        if platforms:
            plat_str = ", ".join(platforms)
            return (
                f"⚠️ AGE WARNING — 19 years old\n"
                f"Has verified scenes on: {plat_str}\n"
                f"Not yet booked by us — confirm age docs and review scenes before booking."
            )
        return (
            "⚠️ AGE WARNING — 19 years old\n"
            "No prior bookings and no verified scenes on SLR, VRPorn, or POVR.\n"
            "Treat as no-go until experience and age docs are confirmed."
        )
    return None


def col_index_to_a1(idx: int) -> str:
    result = ""
    n = idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def process_tab(service, ws, sheet_id: int, dry_run: bool) -> int:
    all_rows = ws.get_all_values()
    if len(all_rows) < HEADER_ROW:
        return 0

    headers  = [h.strip() for h in all_rows[HEADER_ROW - 1]]
    col_map  = {h: i for i, h in enumerate(headers) if h}
    name_col = col_map.get("Name", 0)
    age_col  = col_map.get("Age")

    if age_col is None:
        log.warning("  No Age column — skipping")
        return 0

    name_letter = col_index_to_a1(name_col)
    updates = []

    for row_i, row in enumerate(all_rows[DATA_START_ROW - 1:], start=DATA_START_ROW):
        if len(row) <= name_col:
            continue
        name = row[name_col].strip()
        if not name:
            continue

        age_val = row[age_col].strip() if len(row) > age_col else ""
        age     = parse_age(age_val)

        row_dict     = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
        platforms    = platform_summary(row_dict)
        dates_booked = row_dict.get("Dates Booked", "").strip()

        note = build_note(age, platforms, dates_booked) if age is not None else None

        if note:
            log.info(f"    {name} (age {age}): {note.splitlines()[0]}")
        elif age is not None and age < 20:
            pass  # caught above

        updates.append({
            "range": {
                "sheetId":          sheet_id,
                "startRowIndex":    row_i - 1,
                "endRowIndex":      row_i,
                "startColumnIndex": name_col,
                "endColumnIndex":   name_col + 1,
            },
            "rows": [{
                "values": [{
                    "note": note if note else ""   # empty string clears the note
                }]
            }],
            "fields": "note",
        })

    if updates and not dry_run:
        # Chunk to avoid request size limits
        chunk_size = 200
        for i in range(0, len(updates), chunk_size):
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": [{"updateCells": u} for u in updates[i:i+chunk_size]]}
            ).execute()

    flagged = sum(1 for u in updates if u["rows"][0]["values"][0]["note"])
    return flagged


def main():
    parser = argparse.ArgumentParser(description="Add age-warning notes to under-20 models")
    parser.add_argument("--tab",     help="Process only this tab")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    creds   = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc      = gspread.authorize(creds)
    service = build("sheets", "v4", credentials=creds)
    ss      = gc.open_by_key(SPREADSHEET_ID)

    # Get sheet IDs
    meta = service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID,
        fields="sheets.properties"
    ).execute()
    sheet_id_map = {s["properties"]["title"]: s["properties"]["sheetId"]
                    for s in meta["sheets"]}

    total = 0
    for ws in ss.worksheets():
        if args.tab and ws.title != args.tab:
            continue
        sheet_id = sheet_id_map.get(ws.title)
        if sheet_id is None:
            continue

        log.info(f"\n[{ws.title}]")
        n = process_tab(service, ws, sheet_id, args.dry_run)
        log.info(f"  → {n} age-warning notes {'would be ' if args.dry_run else ''}written")
        total += n

    log.info(f"\nTotal: {total} notes {'(dry run)' if args.dry_run else 'written'}")


if __name__ == "__main__":
    main()
