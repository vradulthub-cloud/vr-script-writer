#!/usr/bin/env python3
"""
detect_duplicates.py
====================
Scans all agency tabs for the same model name appearing on multiple tabs
and prints a report. Optionally writes results to the 'Export' tab.

Usage:
    python3 /Users/andrewninn/Scripts/detect_duplicates.py
"""

import os, re
from collections import defaultdict
from google.oauth2.service_account import Credentials
import gspread

SPREADSHEET_ID       = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SKIP_TABS  = {'📋 Legend', '🔍 Search', 'Export', '📊 Dashboard'}
HEADER_ROW = 2
DATA_START = 3


def normalize(name: str) -> str:
    """Lower-case, strip punctuation/whitespace for fuzzy matching."""
    name = re.sub(r'=HYPERLINK\("[^"]*",\s*"([^"]*)"\)', r'\1', name, flags=re.IGNORECASE)
    return re.sub(r'[^a-z0-9]', '', name.lower().strip())


def main():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc    = gspread.authorize(creds)
    ss    = gc.open_by_key(SPREADSHEET_ID)

    # name_key → list of (display_name, agency)
    name_map: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for ws in ss.worksheets():
        if ws.title in SKIP_TABS:
            continue
        data = ws.get_all_values()
        if len(data) <= DATA_START:
            continue
        headers = [h.strip() for h in data[HEADER_ROW]]
        col     = {h: i for i, h in enumerate(headers) if h}
        if "Name" not in col:
            continue
        name_idx = col["Name"]

        for row in data[DATA_START:]:
            raw = row[name_idx].strip() if name_idx < len(row) else ""
            if not raw:
                continue
            display = re.sub(r'=HYPERLINK\("[^"]*",\s*"([^"]*)"\)', r'\1',
                             raw, flags=re.IGNORECASE).strip()
            key = normalize(raw)
            if key:
                name_map[key].append((display, ws.title))

    duplicates = {k: v for k, v in name_map.items() if len(v) > 1}

    # De-duplicate entries that are exact same agency (shouldn't happen, but guard)
    cleaned = {}
    for k, entries in duplicates.items():
        seen = set()
        unique = []
        for display, agency in entries:
            if agency not in seen:
                seen.add(agency)
                unique.append((display, agency))
        if len(unique) > 1:
            cleaned[k] = unique

    print(f"\n{'='*60}")
    print(f"DUPLICATE MODEL REPORT  —  {len(cleaned)} cross-agency duplicates")
    print(f"{'='*60}\n")

    if not cleaned:
        print("No duplicates found. All model names appear to be unique across agencies.\n")
        return

    for key, entries in sorted(cleaned.items(), key=lambda x: x[0]):
        display_name = entries[0][0]
        agencies     = [a for _, a in entries]
        print(f"  {display_name}")
        for _, agency in entries:
            print(f"      → {agency}")
        print()

    print(f"Total: {len(cleaned)} models signed with multiple agencies.\n")

    # ── Write to Export tab ────────────────────────────────────────────────────
    export_ws = next((w for w in ss.worksheets() if w.title == "Export"), None)
    if export_ws:
        rows = [["Duplicate Model Report", "", ""],
                ["Model Name", "Agency 1", "Agency 2+"]]
        for key, entries in sorted(cleaned.items()):
            display_name = entries[0][0]
            agencies     = [a for _, a in entries]
            rows.append([display_name] + agencies)
        export_ws.clear()
        export_ws.update(rows, "A1", value_input_option="RAW")
        print(f"Results also written to 'Export' tab ({len(cleaned)} rows).")


if __name__ == "__main__":
    main()
