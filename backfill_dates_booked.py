#!/usr/bin/env python3
"""
backfill_dates_booked.py
========================
For models whose "Dates Booked" cell is empty in the agency booking sheet
but who appear in the master scenes doc, backfills:
    "{count}x · {Mon} {YYYY}"
using total scene count and most recent scene date from the master doc.

Usage:
    python3 /Users/andrewninn/Scripts/backfill_dates_booked.py
"""

import os, re
from collections import defaultdict
from datetime import datetime, date
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread

MASTER_ID            = "1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk"
BOOKING_ID           = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SKIP_BOOKING = {'📋 Legend', '🔍 Search', 'Export', '📊 Dashboard'}
HEADER_ROW   = 2
DATA_START   = 3
STUDIO_TABS  = ['FPVR', 'VRH', 'VRA', 'BJN', 'NNJOI', 'XPVR']


def normalize(name: str) -> str:
    name = re.sub(r'=HYPERLINK\("[^"]*",\s*"([^"]*)"\)', r'\1', name, flags=re.IGNORECASE)
    return re.sub(r'[^a-z0-9]', '', name.lower().strip())


def parse_date(val: str) -> date | None:
    """Parse date strings like '2024/03/15', '3/15/2024', '2024-03-15'."""
    val = val.strip()
    for fmt in ('%Y/%m/%d', '%m/%d/%Y', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            pass
    return None


def main():
    creds   = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc      = gspread.authorize(creds)
    service = build("sheets", "v4", credentials=creds)

    # ── Step 1: Build name → [(date, studio)] from master doc ────────────────
    print("Reading master scenes doc…")
    master_ss   = gc.open_by_key(MASTER_ID)

    # name_key → list of (date, studio)
    model_scenes: dict[str, list[tuple]] = defaultdict(list)

    for tab_name in STUDIO_TABS:
        ws   = master_ss.worksheet(tab_name)
        rows = ws.get_all_values()
        if not rows:
            continue
        headers = [h.strip().lower() for h in rows[0]]
        ps_idx   = next((i for i, h in enumerate(headers) if 'pornstar' in h), None)
        date_idx = next((i for i, h in enumerate(headers) if 'date' in h and 'release' in h), None)
        if ps_idx is None:
            continue

        for row in rows[1:]:
            cell = row[ps_idx].strip() if ps_idx < len(row) else ""
            if not cell:
                continue
            d = None
            if date_idx is not None and date_idx < len(row):
                d = parse_date(row[date_idx])

            for name in cell.split(','):
                name = name.strip()
                if not name:
                    continue
                key = normalize(name)
                model_scenes[key].append((d, tab_name))

    print(f"  {len(model_scenes)} performers in master doc.")

    # ── Step 2: Walk booking sheet, find rows where Dates Booked is empty ────
    print("Reading booking sheet…")
    booking_ss = gc.open_by_key(BOOKING_ID)

    updates = []   # (sheet_id, row_idx, col_idx, new_value)

    for ws in booking_ss.worksheets():
        if ws.title in SKIP_BOOKING:
            continue
        data = ws.get_all_values()
        if len(data) <= DATA_START:
            continue
        headers  = [h.strip() for h in data[HEADER_ROW]]
        col_map  = {h: i for i, h in enumerate(headers) if h}
        if "Name" not in col_map:
            continue

        name_idx  = col_map["Name"]
        dates_idx = col_map.get("Dates Booked")
        if dates_idx is None:
            continue

        for r_idx, row in enumerate(data[DATA_START:], start=DATA_START):
            raw = row[name_idx].strip() if name_idx < len(row) else ""
            if not raw:
                continue

            # Only update if Dates Booked is currently empty
            current_dates = row[dates_idx].strip() if dates_idx < len(row) else ""
            if current_dates:
                continue  # already has data — don't overwrite

            key = normalize(raw)
            if key not in model_scenes:
                continue

            scenes = model_scenes[key]
            count  = len(scenes)
            dates_only = [d for d, _ in scenes if d is not None]

            if not dates_only:
                new_val = f"{count}x"
            else:
                most_recent = max(dates_only)
                new_val = f"{count}x · {most_recent.strftime('%b %Y')}"

            # Build per-studio breakdown for the report
            studio_detail = defaultdict(list)
            for d, studio in scenes:
                studio_detail[studio].append(d)

            display = re.sub(r'=HYPERLINK\("[^"]*",\s*"([^"]*)"\)', r'\1',
                             raw, flags=re.IGNORECASE).strip()
            updates.append({
                "sheet_id":    ws.id,
                "sheet_name":  ws.title,
                "row_idx":     r_idx,
                "col_idx":     dates_idx,
                "value":       new_val,
                "model":       display,
                "studio_detail": dict(studio_detail),
            })

    if not updates:
        print("\nNo updates needed.")
        return

    # ── Print detailed report ──────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"BACKFILL REPORT — {len(updates)} models")
    print(f"{'='*65}")
    for u in sorted(updates, key=lambda x: x["model"]):
        print(f"\n  {u['model']}  ({u['sheet_name']})")
        print(f"      Dates Booked → '{u['value']}'")
        for studio, dates in sorted(u["studio_detail"].items()):
            dated = sorted([d for d in dates if d], reverse=True)
            date_strs = [d.strftime('%b %d, %Y') for d in dated]
            undated = len([d for d in dates if d is None])
            line = f"      {studio}: {len(dates)} scene(s)"
            if date_strs:
                line += f"  —  {', '.join(date_strs)}"
            if undated:
                line += f"  (+{undated} undated)"
            print(line)

    print(f"\n{len(updates)} cells to update. Writing…")

    reqs = []
    for u in updates:
        reqs.append({
            "updateCells": {
                "rows": [{"values": [{"userEnteredValue": {"stringValue": u["value"]}}]}],
                "fields": "userEnteredValue",
                "start": {
                    "sheetId":     u["sheet_id"],
                    "rowIndex":    u["row_idx"],
                    "columnIndex": u["col_idx"],
                },
            }
        })

    chunk = 50
    for i in range(0, len(reqs), chunk):
        service.spreadsheets().batchUpdate(
            spreadsheetId=BOOKING_ID,
            body={"requests": reqs[i:i+chunk]}
        ).execute()

    print(f"\n✅ Backfilled {len(updates)} 'Dates Booked' cells from master scenes doc.")
    print("Re-run create_dashboard.py to refresh the dashboard stats.")


if __name__ == "__main__":
    main()
