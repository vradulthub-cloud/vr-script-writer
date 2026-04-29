#!/usr/bin/env python3
"""refresh_comp_links.py — Regenerate presigned S4 URLs for every scene row in the Compilations Index tabs.

S4 presigned URLs cap at 7 days (the SigV4 maximum). Compilation links live
in Google Sheets — without a refresher they go dead every Sunday. This cron
walks all 4 studios' "{Studio} Index" tabs and rewrites column F for every
scene row.

Cron suggested cadence: weekly, before the 7-day TTL expires.

    0 3 * * 0  /opt/homebrew/bin/python3 /Users/andrewninn/Scripts/refresh_comp_links.py >> ~/Scripts/logs/refresh_comp_links.log 2>&1

Usage:
    python3 refresh_comp_links.py             # all studios
    python3 refresh_comp_links.py --studio VRH    # single studio
    python3 refresh_comp_links.py --dry-run       # report counts, write nothing
    python3 refresh_comp_links.py --max 50        # cap rows for safety/testing
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Load S4 creds (cron-friendly).
ENV_FILE = Path.home() / ".config" / "eclatech" / "s4.env"
if ENV_FILE.exists():
    for _line in ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v)

import s4_client  # noqa: E402
import comp_tools  # noqa: E402  — reuses _get_gc + COMP_SHEET_ID + mega_export_link

INDEX_TAB_SUFFIX = " Index"

# Tab name per studio. Mirrors api/routers/compilations.py:_index_tab_name —
# studios that have a Compilations Index tab in the planning sheet.
STUDIO_TABS = {
    "FPVR": "FPVR" + INDEX_TAB_SUFFIX,
    "VRH":  "VRH"  + INDEX_TAB_SUFFIX,
    "VRA":  "VRA"  + INDEX_TAB_SUFFIX,
}

# Column index (0-based) of the mega_link cell. From compilations.py header:
# B=scene_num, C=scene_id, D=title, E=performers, F=mega_link, G=slr_link.
MEGA_LINK_COL = 5  # F


def refresh_studio(studio: str, dry_run: bool, cap: int | None) -> tuple[int, int, int]:
    """Walk one studio's Index tab. Returns (rewritten, unchanged, errors)."""
    tab_name = STUDIO_TABS[studio]
    print(f"[{studio}] reading {tab_name}…", flush=True)
    gc = comp_tools._get_gc()
    sh = gc.open_by_key(comp_tools.COMP_SHEET_ID)
    try:
        ws = sh.worksheet(tab_name)
    except Exception:
        print(f"  WARN: tab '{tab_name}' not found; skipping")
        return 0, 0, 0

    rows = ws.get_all_values()
    print(f"  {len(rows)} rows total", flush=True)

    rewritten = 0
    unchanged = 0
    no_objects = 0  # scene exists in Sheet but has no objects in S4 yet (e.g.
                    # comp planned but content not yet migrated)
    errors = 0
    updates: list[tuple[int, str]] = []  # (row_index_1based, new_url)

    for i, r in enumerate(rows, start=1):
        if len(r) < 6:
            continue
        col_b = r[1].strip() if len(r) > 1 else ""
        if not col_b.isdigit():
            continue  # not a scene row
        scene_id = r[2].strip() if len(r) > 2 else ""
        if not scene_id:
            continue
        old_link = r[5].strip()
        try:
            new_link = comp_tools.mega_export_link(scene_id)
        except Exception as exc:
            print(f"  ERR row {i} {scene_id}: {exc}")
            errors += 1
            continue
        if not new_link:
            no_objects += 1
            continue
        if new_link == old_link:
            unchanged += 1
            continue
        updates.append((i, new_link))
        rewritten += 1
        if cap and rewritten >= cap:
            print(f"  --max cap hit ({cap}); stopping")
            break

    print(f"  {rewritten} rewritten, {unchanged} unchanged, "
          f"{no_objects} no-objects-yet, {errors} errors")

    if not dry_run and updates:
        print(f"  flushing {len(updates)} cells to F…", flush=True)
        # Batch update — single API call per chunk of 1000 cells.
        batch = []
        for row_idx, new_url in updates:
            batch.append({
                "range": f"F{row_idx}",
                "values": [[new_url]],
            })
            if len(batch) >= 500:
                ws.batch_update(batch, value_input_option="RAW")
                batch = []
                time.sleep(0.5)
        if batch:
            ws.batch_update(batch, value_input_option="RAW")

    return rewritten, unchanged, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio", choices=list(STUDIO_TABS), default=None,
                        help="Single studio (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Walk tabs and report; write nothing back")
    parser.add_argument("--max", type=int, default=None,
                        help="Cap rewritten rows per studio (safety/testing)")
    args = parser.parse_args()

    studios = [args.studio] if args.studio else list(STUDIO_TABS)
    started = time.time()
    total_rew = 0
    total_unc = 0
    total_err = 0
    for st in studios:
        rew, unc, err = refresh_studio(st, args.dry_run, args.max)
        total_rew += rew
        total_unc += unc
        total_err += err
        print()

    print(f"Done in {time.time() - started:.1f}s.")
    print(f"  rewritten: {total_rew}")
    print(f"  unchanged: {total_unc}")
    print(f"  errors:    {total_err}")
    return 0 if total_err == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
