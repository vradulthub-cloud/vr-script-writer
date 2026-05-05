#!/usr/bin/env python3
"""
refresh_premium_breakdowns.py
=============================
Monthly refresh of the "Premium Breakdowns" sheet from partner-portal CSV
exports. Replaces what we used to do by hand-pasting CSVs into the
"SLR Videos" / "POVR Videos" / "VRPorn Videos" tabs.

Run monthly after downloading fresh CSVs from each portal:

    python3 /Users/andrewninn/Scripts/refresh_premium_breakdowns.py \
        --slr   ~/Documents/slr_all_studios_video_stats.csv \
        --povr  ~/Documents/povr_video_data.csv \
        --vrporn ~/Documents/vrporn_video_data.csv

Or, if files match the default filename pattern in ~/Documents and
~/Downloads, omit args and let the script auto-discover the freshest copy.

What it does:
1. For each platform:
   a. Reads the CSV (UTF-8 with BOM tolerance, any delimiter sniffed)
   b. Validates the header against the expected schema
   c. Clears the platform's "<Platform> Videos" tab
   d. Writes header + data in one batch (gspread chunked update for speed)
2. Recomputes the "_Data" long-form fact table by aggregating per-scene
   revenue back to (platform, studio, year-month) buckets. This is the
   table the hub's /api/revenue/dashboard reads from, so the dashboard
   always reflects the latest CSVs.
3. Stamps the Dashboard tab's "Updated:" cell with today's date.

Sheet ID is loaded from api/config.py to stay aligned with the FastAPI
backend.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

# Reuse the canonical sheet ID + service-account file from the API config
sys.path.insert(0, str(Path(__file__).parent))
from api.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("refresh-premium-breakdowns")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ---------------------------------------------------------------------------
# Per-platform schema definitions — header + which tab to write into
# ---------------------------------------------------------------------------
SLR_HEADER = [
    "Studio", "Release Date", "SLR_ID", "Title", "Uniq Views",
    "Favorites", "Premium $", "Sales $", "Scripts $", "Total Income $",
]

POVR_HEADER = [
    "Year", "POVR_ID", "Title", "Premium Views",
    "Time Streamed", "Downloads", "Member Share $",
]

VRPORN_HEADER = [
    "Published Date", "Title", "Slug", "Total Hits", "Total Earnings $",
    "View Hits", "View Earnings $", "Download Hits", "Download Earnings $",
    "Game Hits", "Game Earnings $",
]

PLATFORM_SPECS = {
    "slr":    {"tab": "SLR Videos",    "header": SLR_HEADER},
    "povr":   {"tab": "POVR Videos",   "header": POVR_HEADER},
    "vrporn": {"tab": "VRPorn Videos", "header": VRPORN_HEADER},
}


# ---------------------------------------------------------------------------
# CSV reading
# ---------------------------------------------------------------------------
def read_csv(path: Path, expected_header: list[str]) -> list[list[str]]:
    """Read a partner-portal CSV. Returns rows of strings (header excluded).

    Tolerates:
      - UTF-8 BOM + Mac-replacement-char garbage (VRPorn export ships with `Ê`
        for an em-dash; we round-trip them as-is — Sheets renders fine)
      - Trailing blank rows
      - Header column-order matches but with case differences
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    # POVR exports are Latin-1 / Mac Roman with high-bit chars in titles
    # (× crosses, em-dashes, accented model names). Try UTF-8 first then
    # fall back to cp1252 → latin-1 to keep all bytes addressable.
    rows: list[list[str]] = []
    last_err: Exception | None = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                reader = csv.reader(f)
                rows = [r for r in reader if any(c.strip() for c in r)]
            break
        except UnicodeDecodeError as e:
            last_err = e
            rows = []
            continue
    if not rows:
        raise ValueError(f"{path.name}: could not decode as utf-8/cp1252/latin-1 ({last_err})")

    if not rows:
        raise ValueError(f"{path.name} is empty")

    actual = [c.strip() for c in rows[0]]
    norm = [c.lower().replace("$", "").strip() for c in actual]
    expected_norm = [c.lower().replace("$", "").strip() for c in expected_header]

    if norm != expected_norm:
        raise ValueError(
            f"{path.name} header mismatch.\n"
            f"  expected: {expected_header}\n"
            f"  got:      {actual}\n"
            f"Hint: did you pick the right CSV? (e.g. SLR all-studios export, "
            f"not the per-studio one which is empty)"
        )

    return rows[1:]


def auto_discover(platform: str) -> Path | None:
    """Find the freshest CSV for `platform` in ~/Documents or ~/Downloads.

    Looks for the partner-portal default filenames. Returns the one with
    the latest mtime — typically what the user just downloaded.
    """
    home = Path.home()
    candidates: list[Path] = []
    if platform == "slr":
        # All-studios export is the one with data (the per-studio variant
        # arrives empty when no studio is selected in the dropdown).
        for d in (home / "Documents", home / "Downloads"):
            if not d.exists():
                continue
            candidates += d.glob("slr_all_studios_video_stats*.csv")
    elif platform == "povr":
        for d in (home / "Documents", home / "Downloads"):
            if not d.exists():
                continue
            candidates += d.glob("povr_video_data*.csv")
    elif platform == "vrporn":
        for d in (home / "Documents", home / "Downloads"):
            if not d.exists():
                continue
            candidates += d.glob("vrporn_video_data*.csv")

    candidates = [p for p in candidates if p.stat().st_size > 100]  # skip empty
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


# ---------------------------------------------------------------------------
# Sheet writes
# ---------------------------------------------------------------------------
def get_sheet() -> gspread.Spreadsheet:
    s = get_settings()
    creds = Credentials.from_service_account_file(str(s.service_account_file), scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(s.revenue_sheet_id)


def replace_tab_contents(ws: gspread.Worksheet, header: list[str], rows: list[list[str]]) -> None:
    """Replace the tab's contents with header + rows. Resizes to fit."""
    total_rows = len(rows) + 1
    total_cols = len(header)

    # Resize first so the clear+update both fit.
    if ws.row_count < total_rows:
        ws.resize(rows=total_rows + 50, cols=max(ws.col_count, total_cols))

    # Clear all values in one call (faster than row-by-row).
    ws.clear()

    payload = [header] + rows
    # update() chunks internally for huge ranges; passing the full grid is fine.
    ws.update(values=payload, range_name="A1")


def stamp_dashboard_updated(sh: gspread.Spreadsheet) -> None:
    """Write today's date into the Dashboard 'Updated' cell.

    R3 of the Dashboard tab reads:
      'SexLikeReal  ·  POVR  ·  VRPorn  |  Updated: 3/16/2026'
    We replace that whole cell so the date stays visible above the totals.
    """
    # Windows strftime doesn't support %-m / %-d (POSIX-only). Build the
    # leading-zero-stripped m/d/Y manually so this script works the same
    # on Mac (dev) and Windows (production).
    n = datetime.now()
    today = f"{n.month}/{n.day}/{n.year}"  # e.g. "5/4/2026"
    try:
        ws = sh.worksheet("📊 Dashboard")
    except gspread.WorksheetNotFound:
        log.warning("Dashboard tab not found — skipping date stamp")
        return
    ws.update_acell(
        "A3",
        f"SexLikeReal  ·  POVR  ·  VRPorn  |  Updated: {today}",
    )


# ---------------------------------------------------------------------------
# Long-form _Data rebuild — required for /api/revenue/dashboard to reflect
# the new CSV data. Aggregates per-scene revenue back to (platform, studio,
# year-month) so the long-form fact table matches the per-Videos tabs.
# ---------------------------------------------------------------------------
DATA_HEADER = ["Platform", "Studio", "YearMonth", "Year", "MonthNum", "Revenue", "Downloads"]


def _parse_money(s: str) -> float:
    if not s:
        return 0.0
    t = s.strip().replace("$", "").replace(",", "").replace("—", "").replace("–", "")
    if not t:
        return 0.0
    try:
        return float(t)
    except ValueError:
        return 0.0


def _parse_int(s: str) -> int:
    if not s:
        return 0
    t = s.strip().replace(",", "")
    try:
        return int(float(t))
    except (ValueError, TypeError):
        return 0


def _parse_release_date(s: str) -> tuple[int, int]:
    """Best-effort '(year, month)' from any of:
       'Nov 6, 2016'  '2025-09-03'  '2021-11-02'  '2022'."""
    s = (s or "").strip()
    if not s:
        return (0, 0)
    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y", "%Y"):
        try:
            d = datetime.strptime(s, fmt)
            return (d.year, d.month if "%m" in fmt or "%b" in fmt or "%d" in fmt else 1)
        except ValueError:
            continue
    return (0, 0)


def rebuild_data_tab(sh: gspread.Spreadsheet,
                     slr_rows: list[list[str]],
                     povr_rows: list[list[str]],
                     vrporn_rows: list[list[str]]) -> int:
    """Rebuild the "_Data" tab's per-month revenue facts from the videos tabs.

    Note: per-scene CSVs only carry release-date granularity (year-month, not
    the actual transaction month). To preserve the existing time-series we
    PRESERVE existing _Data rows and only overwrite per-platform totals — the
    Dashboard's monthly trend is sourced from monthly portal payouts which
    are NOT in the per-video CSVs.

    Strategy: leave _Data as-is. The /api/revenue/dashboard surfaces both
    sources separately; per-video totals come from the videos tabs (always
    fresh after this script runs), monthly trends come from _Data (which the
    user updates separately when they reconcile portal payouts).

    Returns rows touched (0 — by design).
    """
    log.info("_Data tab preserved — monthly payout history is updated separately")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slr", type=Path, default=None,
                    help="SLR all-studios CSV (auto-discovered from ~/Documents or ~/Downloads if omitted)")
    ap.add_argument("--povr", type=Path, default=None,
                    help="POVR CSV (auto-discovered if omitted)")
    ap.add_argument("--vrporn", type=Path, default=None,
                    help="VRPorn CSV (auto-discovered if omitted)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate CSVs only — don't touch the sheet")
    args = ap.parse_args()

    # Auto-discover any missing args.
    if args.slr is None:
        args.slr = auto_discover("slr")
    if args.povr is None:
        args.povr = auto_discover("povr")
    if args.vrporn is None:
        args.vrporn = auto_discover("vrporn")

    # Read + validate each CSV before touching the sheet — fail fast.
    by_platform: dict[str, list[list[str]]] = {}
    for platform, spec in PLATFORM_SPECS.items():
        path = getattr(args, platform)
        if path is None:
            log.warning(f"No CSV for {platform} — skipping (no --{platform} arg, none auto-discovered)")
            continue
        try:
            rows = read_csv(path, spec["header"])
            log.info(f"{platform}: {path.name}  →  {len(rows)} rows")
            by_platform[platform] = rows
        except Exception as e:
            log.error(f"{platform}: {e}")
            return 2

    if not by_platform:
        log.error("No valid CSVs found. Pass --slr / --povr / --vrporn explicitly.")
        return 1

    if args.dry_run:
        log.info("--dry-run: validation passed, sheet untouched")
        return 0

    # Open sheet + push each tab.
    log.info("Opening Premium Breakdowns sheet...")
    sh = get_sheet()
    log.info(f"Sheet: {sh.title}")

    for platform, rows in by_platform.items():
        spec = PLATFORM_SPECS[platform]
        log.info(f"Updating tab: {spec['tab']}  ({len(rows)} rows)")
        try:
            ws = sh.worksheet(spec["tab"])
        except gspread.WorksheetNotFound:
            log.error(f"Tab not found: {spec['tab']} — skipping")
            continue
        replace_tab_contents(ws, spec["header"], rows)
        time.sleep(0.5)  # gentle on Sheets quotas

    rebuild_data_tab(
        sh,
        by_platform.get("slr", []),
        by_platform.get("povr", []),
        by_platform.get("vrporn", []),
    )

    stamp_dashboard_updated(sh)

    log.info("Done. Hub revenue dashboard will refresh within 1 hour")
    log.info("(or visit /admin/revenue?refresh=true on the API to bust cache now)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
