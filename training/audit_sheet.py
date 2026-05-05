"""
Audit the Scripts Sheet for data drift.

Read-only — never modifies the sheet. Prints a per-tab summary plus the
specific row coordinates of every partial / orphan / drifted entry so a
human reviewer can decide whether each is a real issue or expected
(upcoming shoots, header dividers, etc.).

Run with:  python3 training/audit_sheet.py
"""
from __future__ import annotations

import argparse
import re
import sys
from calendar import month_name
from collections import Counter, defaultdict
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials


SCRIPTS_SHEET_ID = "1cY-8zNHLmD-oWdyEa2Mt3VY3nsFXHLEeZx0n42uf3ZQ"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

COL_DATE       = 0
COL_STUDIO     = 1
COL_LOCATION   = 2
COL_SCENE_TYPE = 3
COL_FEMALE     = 4
COL_MALE       = 5
COL_THEME      = 6
COL_WARDROBE_F = 7
COL_WARDROBE_M = 8
COL_PLOT       = 9
COL_TITLE      = 10
COL_PROPS      = 11
COL_STATUS     = 12

CANONICAL_STUDIOS = {"FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"}
CANONICAL_SCENE_TYPES = {"BG", "BGCP", "SOLO", "JOI"}

MONTH_TAB_RE = re.compile(
    r"^(" + "|".join(month_name[1:]) + r")\s+\d{4}$",
    re.IGNORECASE,
)


def classify_row(row: list[str]) -> tuple[str, list[str]]:
    """
    Return (category, notes).

    Categories:
      complete        — has studio + female + plot + theme
      planned         — has studio + female but no plot (upcoming shoot)
      partial         — has studio but no female (very incomplete)
      empty           — every column blank or whitespace-only
      drift           — has data but values don't match canonical sets
    """
    padded = row + [""] * (13 - len(row))
    studio       = padded[COL_STUDIO].strip()
    scene_type   = padded[COL_SCENE_TYPE].strip()
    female       = padded[COL_FEMALE].strip()
    plot         = padded[COL_PLOT].strip()
    theme        = padded[COL_THEME].strip()

    notes: list[str] = []

    # Drift checks (warn but don't reclassify)
    if studio and studio not in CANONICAL_STUDIOS:
        notes.append(f"studio={studio!r}")
    if scene_type and scene_type.upper() not in CANONICAL_SCENE_TYPES:
        notes.append(f"scene_type={scene_type!r}")

    # Empty: nothing in any field
    if not any(c.strip() for c in padded):
        return "empty", notes

    # Complete: all four pieces of training-worthy data
    if studio and female and plot and theme:
        return "complete", notes

    # Planned: studio + female set, plot empty (upcoming shoot)
    if studio and female and not plot:
        return "planned", notes

    # Partial: has *something* but missing studio or female
    if studio and not female:
        return "partial-no-female", notes
    if female and not studio:
        return "partial-no-studio", notes

    return "partial-other", notes


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--service-account",
        type=Path,
        default=Path.home() / "Scripts" / "service_account.json",
    )
    args = p.parse_args()

    if not args.service_account.exists():
        print(f"ERROR: service account file not found at {args.service_account}", file=sys.stderr)
        return 1

    creds = Credentials.from_service_account_file(str(args.service_account), scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SCRIPTS_SHEET_ID)

    all_titles = [ws.title for ws in sh.worksheets()]
    month_tabs = [t for t in all_titles if MONTH_TAB_RE.match(t)]

    print(f"Scripts Sheet — {len(month_tabs)} monthly tabs found\n")
    print(f"{'Tab':<20} {'rows':>5} {'complete':>9} {'planned':>8} {'partial':>8} {'empty':>6} {'drift':>6}")
    print("-" * 70)

    overall = Counter()
    drift_rows: list[tuple[str, int, str, list[str]]] = []
    partial_rows: list[tuple[str, int, str, list[str]]] = []

    for tab_name in month_tabs:
        ws = sh.worksheet(tab_name)
        rows = ws.get_all_values()[1:]  # skip header

        per_tab = Counter()
        for row_idx, row in enumerate(rows, start=2):
            category, notes = classify_row(row)
            per_tab[category] += 1
            overall[category] += 1
            if notes:
                drift_rows.append((tab_name, row_idx, category, notes))
            if category.startswith("partial"):
                padded = row + [""] * (13 - len(row))
                summary = f"studio={padded[COL_STUDIO]!r} female={padded[COL_FEMALE]!r}"
                partial_rows.append((tab_name, row_idx, category, [summary]))

        partial_total = sum(v for k, v in per_tab.items() if k.startswith("partial"))
        print(
            f"{tab_name:<20} {len(rows):>5d} "
            f"{per_tab['complete']:>9d} {per_tab['planned']:>8d} "
            f"{partial_total:>8d} {per_tab['empty']:>6d} "
            f"{sum(1 for t,_,_,_ in drift_rows if t==tab_name):>6d}"
        )

    print("-" * 70)
    print(
        f"{'TOTAL':<20} {sum(overall.values()):>5d} "
        f"{overall['complete']:>9d} {overall['planned']:>8d} "
        f"{overall['partial-no-female']+overall['partial-no-studio']+overall['partial-other']:>8d} "
        f"{overall['empty']:>6d} {len(drift_rows):>6d}"
    )

    if partial_rows:
        print("\n--- Partial rows (review and either complete or delete) ---")
        for tab, row, cat, notes in partial_rows:
            print(f"  {tab} row {row:3d}  [{cat}]  {notes[0]}")

    if drift_rows:
        print("\n--- Drift rows (non-canonical studio/scene_type values) ---")
        for tab, row, cat, notes in drift_rows:
            print(f"  {tab} row {row:3d}  [{cat}]  {', '.join(notes)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
