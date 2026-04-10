#!/usr/bin/env python3
"""
run_all.py
==========
Master script — runs every maintenance script in the correct order.

Steps:
  1. roster       — Sync adds/removes from agency websites + fill age/location/shoots (--profiles)
  2. profile_links — Write Name→agency, SLR Profile, VRP Profile hyperlinks
  3. rank         — Score & tier every model (Great/Good/Moderate/Unknown)
  4. beautify     — Formatting, banding, conditional rules, column widths
  5. ui           — Title bars, gridlines, freeze rows
  6. enhancements — Hyperlink title bars, Bookings/Last Booked Date columns, stale CF
  7. backfill     — Fill "Last Booked Date" from master scenes doc
  8. search       — Refresh the 🔍 Search tab
  9. dashboard    — Rebuild the 📊 Dashboard
  10. duplicates  — Report models signed with multiple agencies
  11. legend      — Rebuild the 📋 Legend tab

Usage:
    python3 /Users/andrewninn/Scripts/run_all.py
    python3 /Users/andrewninn/Scripts/run_all.py --skip backfill   # skip one step
    python3 /Users/andrewninn/Scripts/run_all.py --only dashboard  # run only one step
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

def _is_interactive() -> bool:
    return sys.stdin.isatty()

SCRIPTS_DIR = Path(__file__).parent

# (short_name, script_filename, extra_args)
STEPS = [
    ("roster",        "update_roster.py",          ["--profiles"]),
    ("profile_links", "add_profile_links.py",       []),
    ("rank",          "compute_rank.py",            []),
    ("beautify",      "beautify_sheet.py",          []),
    ("ui",            "ui_improvements.py",         []),
    ("enhancements",  "add_enhancements.py",        []),
    ("backfill",      "backfill_dates_booked.py",   []),
    ("search",        "create_search_tab.py",       []),
    ("dashboard",     "create_dashboard.py",        []),
    ("duplicates",    "detect_duplicates.py",       []),
    ("legend",        "create_legend.py",           []),
]

STEP_NAMES = {name for name, _, _args in STEPS}


def run_step(name: str, script: str, extra_args: list, dry_run: bool) -> bool:
    path = SCRIPTS_DIR / script
    cmd = [sys.executable, str(path)] + extra_args

    print(f"\n{'='*65}")
    print(f"  STEP: {name}  ({script})")
    print(f"{'='*65}")

    if dry_run:
        print(f"  [DRY RUN] Would run: {' '.join(cmd)}")
        return True

    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        print(f"\n  ❌ {name} FAILED (exit code {result.returncode})")
        return False

    print(f"\n  ✅ {name} completed.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Run all Model Booking List maintenance scripts in order."
    )
    parser.add_argument(
        "--skip", metavar="STEP", action="append", default=[],
        help=f"Skip a step by short name. Can repeat. Options: {', '.join(s for s, _, _a in STEPS)}"
    )
    parser.add_argument(
        "--only", metavar="STEP",
        help="Run only this step (by short name)."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would run without executing anything."
    )
    args = parser.parse_args()

    if args.only and args.only not in STEP_NAMES:
        print(f"Unknown step: {args.only}. Options: {', '.join(s for s, _, _a in STEPS)}")
        sys.exit(1)

    for bad in args.skip:
        if bad not in STEP_NAMES:
            print(f"Unknown step to skip: {bad}. Options: {', '.join(s for s, _, _a in STEPS)}")
            sys.exit(1)

    steps_to_run = [
        (name, script, extra_args) for name, script, extra_args in STEPS
        if (not args.only or name == args.only) and name not in args.skip
    ]

    print(f"\n🚀  Model Booking List — Full Refresh")
    print(f"    Steps to run: {', '.join(n for n, _, _a in steps_to_run)}")

    failed = []
    for i, (name, script, extra_args) in enumerate(steps_to_run):
        ok = run_step(name, script, extra_args, args.dry_run)
        if not ok:
            failed.append(name)
            if _is_interactive():
                resp = input(f"\n  Continue despite failure in '{name}'? [y/N] ").strip().lower()
                if resp != "y":
                    print("  Aborting.")
                    break
            else:
                print(f"  Non-interactive mode — continuing past failure in '{name}'.")
        # Pause between steps to avoid Google Sheets API rate-limit (60 req/min)
        if i < len(steps_to_run) - 1 and not args.dry_run:
            time.sleep(15)

    print(f"\n{'='*65}")
    if failed:
        print(f"⚠️   Finished with errors in: {', '.join(failed)}")
    else:
        print(f"✅  All steps completed successfully.")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
