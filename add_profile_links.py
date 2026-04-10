#!/usr/bin/env python3
"""
add_profile_links.py
====================
Manages profile hyperlinks on every agency tab.

  Name column       → agency website profile page
  SLR Profile col   → sexlikereal.com pornstar page  (placed right after Name)
  VRP Profile col   → vrporn.com pornstar page        (placed right after SLR Profile)

SLR Profile and VRP Profile columns are created at name_col+1 / name_col+2 if they
don't exist yet. If they exist but are in the wrong position they are moved.

Usage:
    python3 /Users/andrewninn/Scripts/add_profile_links.py
    python3 /Users/andrewninn/Scripts/add_profile_links.py --tab "ATMLA"
    python3 /Users/andrewninn/Scripts/add_profile_links.py --dry-run
    python3 /Users/andrewninn/Scripts/add_profile_links.py --overwrite
"""

import argparse
import json
import logging
import re
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

# ── Config ─────────────────────────────────────────────────────────────────────

SPREADSHEET_ID       = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = Path(__file__).parent / "service_account.json"
SLR_CACHE_FILE       = Path(__file__).parent / "slr_cache.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW     = 3
DATA_START_ROW = 4

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# ── Platform profile URL templates ─────────────────────────────────────────────

SLR_PROFILE_BASE = "https://www.sexlikereal.com/pornstars/{slug}"
VRP_PROFILE_BASE = "https://www.vrporn.com/pornstar/{slug}/"

PROFILE_ANCHOR = "Available For"   # SLR Profile goes right after this; VRP Profile one after SLR

# ── Agency URL templates ────────────────────────────────────────────────────────
# {slug} = full-name slug  |  {first} = first-name slug only (Speigler)

AGENCY_URL_TEMPLATES = {
    "oc models":         "https://ocmodeling.com/model/{slug}/",
    "hussie models":     "https://hussiemodels.com/model/{slug}",
    "nexxxt level":      "https://nexxxtleveltalentagency.com/models/{slug}/",
    "foxxx modeling":    "https://foxxxmodeling.com/model-stats-profile-page/{slug}",
    "zen models":        "https://zenmodels.org/our-models/{slug}/",
    "coxxx models":      "https://coxxxmodels.com/portfolio/{slug}",
    "atmla":             "https://atmla.com/performers/female-models/{slug}/",
    "the model service": "https://themodelservice.com/model/{slug}.html",
    "east coast talent": "https://eastcoasttalents.com/talent/{slug}/",
    "the bakery talent": "https://thebakerytalent.com/{slug}",
    "invision models":   "https://invisionmodels.com/{slug}",
    "speigler":          "https://spieglergirls.com/html/{first}.html",
    # 101 Models uses numeric t_id URLs that require scraping — not handled here
}


# ── Helpers ─────────────────────────────────────────────────────────────────────

def name_to_slug(name: str) -> str:
    """'Adriana Maya' → 'adriana-maya'"""
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def col_index_to_letter(col_idx: int) -> str:
    """0-based column index → A1 letter (e.g. 0→A, 25→Z, 26→AA)."""
    result = ""
    n = col_idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def build_agency_url(agency_name: str, model_name: str) -> str:
    key      = agency_name.lower().strip()
    template = AGENCY_URL_TEMPLATES.get(key, "")
    if not template:
        return ""
    slug  = name_to_slug(model_name)
    first = name_to_slug(model_name.strip().split()[0])
    return template.format(slug=slug, first=first)


def build_slr_url(model_name: str, slr_cache: dict) -> str:
    slug     = name_to_slug(model_name)
    slr_slug = slr_cache.get(slug, slug)
    return SLR_PROFILE_BASE.format(slug=slr_slug)


def build_vrp_url(model_name: str) -> str:
    return VRP_PROFILE_BASE.format(slug=name_to_slug(model_name))


def hyperlink_formula(url: str, display: str) -> str:
    safe_url  = url.replace('"', "")
    safe_name = display.replace('"', '""')
    return f'=HYPERLINK("{safe_url}","{safe_name}")'


def read_col_map(ws) -> tuple[dict, list]:
    """Returns (col_map, all_rows) freshly read from the sheet."""
    all_rows = ws.get_all_values()
    if len(all_rows) < HEADER_ROW:
        return {}, all_rows
    headers = [h.strip() for h in all_rows[HEADER_ROW - 1]]
    col_map = {h: i for i, h in enumerate(headers) if h}
    return col_map, all_rows


def _insert_col(ws, col_idx: int) -> None:
    ws.spreadsheet.batch_update({"requests": [{"insertDimension": {
        "range": {
            "sheetId":    ws.id,
            "dimension":  "COLUMNS",
            "startIndex": col_idx,
            "endIndex":   col_idx + 1,
        },
        "inheritFromBefore": False,
    }}]})


def _delete_col(ws, col_idx: int) -> None:
    ws.spreadsheet.batch_update({"requests": [{"deleteDimension": {
        "range": {
            "sheetId":    ws.id,
            "dimension":  "COLUMNS",
            "startIndex": col_idx,
            "endIndex":   col_idx + 1,
        },
    }}]})


# ── Column positioning ──────────────────────────────────────────────────────────

def ensure_profile_cols(ws, name_col: int, dry_run: bool) -> tuple[int, int, int]:
    """
    Ensure SLR Profile is immediately after PROFILE_ANCHOR ('Available For')
    and VRP Profile is immediately after SLR Profile.
    Both stay in the main columns section (before the collapsed stats group).
    Returns (slr_col, vrp_col, headers_added).
    """
    col_map, _ = read_col_map(ws)
    slr_col = col_map.get("SLR Profile")
    vrp_col = col_map.get("VRP Profile")

    anchor    = col_map.get(PROFILE_ANCHOR, col_map.get("Name", 0))
    target_slr = anchor + 1
    target_vrp = anchor + 2

    if slr_col == target_slr and vrp_col == target_vrp:
        return slr_col, vrp_col, 0  # already correct

    if dry_run:
        return (target_slr if slr_col is None else slr_col), \
               (target_vrp if vrp_col is None else vrp_col), \
               (1 if slr_col is None else 0) + (1 if vrp_col is None else 0)

    headers_added = 0

    # ── Delete misplaced columns first (highest index first to avoid shift) ───
    to_delete = []
    if slr_col is not None and slr_col != target_slr:
        to_delete.append((slr_col, "SLR Profile"))
    if vrp_col is not None and vrp_col != target_vrp:
        to_delete.append((vrp_col, "VRP Profile"))

    for idx, col_name in sorted(to_delete, key=lambda x: -x[0]):
        log.info(f"    - Removing misplaced '{col_name}' from col {col_index_to_letter(idx)}")
        _delete_col(ws, idx)

    if to_delete:
        col_map, _ = read_col_map(ws)
        slr_col = col_map.get("SLR Profile")
        vrp_col = col_map.get("VRP Profile")
        # Recompute targets after deletions shifted columns
        anchor    = col_map.get(PROFILE_ANCHOR, col_map.get("Name", 0))
        target_slr = anchor + 1
        target_vrp = anchor + 2

    # ── Insert missing columns at target positions ────────────────────────────
    if slr_col is None:
        log.info(f"    + Inserting 'SLR Profile' at {col_index_to_letter(target_slr)}")
        _insert_col(ws, target_slr)
        headers_added += 1
        if vrp_col is not None and vrp_col >= target_slr:
            vrp_col += 1

    if vrp_col is None:
        log.info(f"    + Inserting 'VRP Profile' at {col_index_to_letter(target_vrp)}")
        _insert_col(ws, target_vrp)
        headers_added += 1

    return col_map.get("SLR Profile", target_slr), col_map.get("VRP Profile", target_vrp), headers_added


# ── Tab processor ───────────────────────────────────────────────────────────────

def process_tab(ws, agency_name: str, slr_cache: dict,
                dry_run: bool, overwrite: bool) -> dict:
    col_map, all_rows = read_col_map(ws)
    if not col_map:
        return {}

    name_col = col_map.get("Name", 0)

    # ── Ensure profile columns are right after Available For ─────────────────
    slr_col, vrp_col, headers_added = ensure_profile_cols(ws, name_col, dry_run)

    # Re-read after structural changes (insertions/moves shift other col indices)
    if not dry_run and headers_added > 0:
        col_map, all_rows = read_col_map(ws)

    name_col_ltr = col_index_to_letter(name_col)
    slr_col_ltr  = col_index_to_letter(slr_col)
    vrp_col_ltr  = col_index_to_letter(vrp_col)

    updates    = []
    name_links = slr_links = vrp_links = 0

    # ── Write column headers if new columns were just inserted ────────────────
    headers = [h.strip() for h in all_rows[HEADER_ROW - 1]] if not dry_run else []
    if not dry_run:
        if "SLR Profile" not in headers:
            updates.append({
                "range":  f"'{ws.title}'!{slr_col_ltr}{HEADER_ROW}",
                "values": [["SLR Profile"]],
            })
        if "VRP Profile" not in headers:
            updates.append({
                "range":  f"'{ws.title}'!{vrp_col_ltr}{HEADER_ROW}",
                "values": [["VRP Profile"]],
            })

    # ── Iterate data rows ─────────────────────────────────────────────────────
    for row_i, row in enumerate(all_rows[DATA_START_ROW - 1:], start=DATA_START_ROW):
        if len(row) <= name_col:
            continue

        name_cell = row[name_col].strip()
        if not name_cell:
            continue

        # Resolve display name (strip any existing formula)
        if name_cell.startswith("=HYPERLINK("):
            m = re.search(r'=HYPERLINK\("[^"]*",\s*"([^"]+)"\)', name_cell)
            display_name = m.group(1) if m else name_cell
        else:
            display_name = name_cell

        already_name_linked = name_cell.startswith("=HYPERLINK(")

        # ── Name → agency page ────────────────────────────────────────────────
        if not already_name_linked or overwrite:
            agency_url = build_agency_url(agency_name, display_name)
            if agency_url:
                updates.append({
                    "range":  f"'{ws.title}'!{name_col_ltr}{row_i}",
                    "values": [[hyperlink_formula(agency_url, display_name)]],
                })
                name_links += 1

        # ── SLR Profile column ────────────────────────────────────────────────
        slr_cell   = row[slr_col].strip() if slr_col < len(row) else ""
        slr_linked = slr_cell.startswith("=HYPERLINK(")
        if not slr_linked or overwrite:
            updates.append({
                "range":  f"'{ws.title}'!{slr_col_ltr}{row_i}",
                "values": [[hyperlink_formula(build_slr_url(display_name, slr_cache),
                                              "SLR")]],
            })
            slr_links += 1

        # ── VRP Profile column ────────────────────────────────────────────────
        vrp_cell   = row[vrp_col].strip() if vrp_col < len(row) else ""
        vrp_linked = vrp_cell.startswith("=HYPERLINK(")
        if not vrp_linked or overwrite:
            updates.append({
                "range":  f"'{ws.title}'!{vrp_col_ltr}{row_i}",
                "values": [[hyperlink_formula(build_vrp_url(display_name),
                                              "VRP")]],
            })
            vrp_links += 1

    if updates and not dry_run:
        ws.spreadsheet.values_batch_update({
            "valueInputOption": "USER_ENTERED",
            "data": updates,
        })

    return {
        "name_links":    name_links,
        "slr_links":     slr_links,
        "vrp_links":     vrp_links,
        "headers_added": headers_added,
    }


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Add profile hyperlinks: Name→agency, SLR Profile col, VRP Profile col"
    )
    parser.add_argument("--tab",       help="Process only this tab")
    parser.add_argument("--dry-run",   action="store_true", help="Compute but don't write")
    parser.add_argument("--overwrite", action="store_true", help="Re-link already-linked cells")
    args = parser.parse_args()

    slr_cache: dict = {}
    if SLR_CACHE_FILE.exists():
        slr_cache = json.loads(SLR_CACHE_FILE.read_text())
    log.info(f"SLR cache: {len(slr_cache)} entries")

    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc    = gspread.authorize(creds)
    ss    = gc.open_by_key(SPREADSHEET_ID)

    SKIP_TABS = {"📋 Legend", "🔍 Search", "Export", "📊 Dashboard", "📱 Socials"}

    totals = {"name_links": 0, "slr_links": 0, "vrp_links": 0, "headers_added": 0}

    for ws in ss.worksheets():
        if args.tab and ws.title != args.tab:
            continue
        if ws.title in SKIP_TABS:
            log.info(f"\n[{ws.title}] — skipped")
            continue

        log.info(f"\n[{ws.title}]")
        counts = process_tab(ws, ws.title, slr_cache, args.dry_run, args.overwrite)
        if counts:
            log.info(
                f"  → name:{counts['name_links']}  slr:{counts['slr_links']}  "
                f"vrp:{counts['vrp_links']}  headers:{counts['headers_added']}"
                + (" (dry run)" if args.dry_run else "")
            )
            for k in totals:
                totals[k] += counts.get(k, 0)

    log.info(
        f"\nTotal — name:{totals['name_links']}  slr:{totals['slr_links']}  "
        f"vrp:{totals['vrp_links']}  headers:{totals['headers_added']}"
        + (" (dry run — not written)" if args.dry_run else "")
    )


if __name__ == "__main__":
    main()
