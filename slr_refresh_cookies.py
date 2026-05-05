#!/usr/bin/env python3
"""
slr_refresh_cookies.py
======================
Opens a headed Chrome window so you can log into partners.sexlikereal.com
once. Saves the resulting session cookies to ~/.scraper_state/slr.json
and then syncs them to the Windows production box so the daily scheduled
task can use them.

The whole point: reCAPTCHA almost never challenges a real human in a
real Chrome window — your IP + browser fingerprint + clicking patterns
score high. The challenge headless Playwright sees does NOT appear here.

Run this once a month (cookies expire ~30 days). Total time: ~30 seconds.

    python3 slr_refresh_cookies.py

Optionally skip the Windows sync if you're testing locally:

    python3 slr_refresh_cookies.py --no-sync

When the daily scheduled task starts hitting "SLR login still on /signin"
errors in the log, that's your cue to re-run this script.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

STATE_DIR = Path.home() / ".scraper_state"
STATE_DIR.mkdir(exist_ok=True)
STATE_FILE = STATE_DIR / "slr.json"

SLR_LOGIN_URL = "https://partners.sexlikereal.com/user/signin"
SLR_DASHBOARD_HINT = "/statistics"  # any non-/signin URL means we're authed

WINDOWS_HOST = "andre@100.90.90.68"
WINDOWS_KEY  = str(Path.home() / ".ssh" / "id_ed25519_win")
WINDOWS_DEST = "C:/Users/andre/.scraper_state/"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-sync", action="store_true",
                    help="Skip the SCP-to-Windows step (test locally only)")
    args = ap.parse_args()

    print(f"Opening Chrome to {SLR_LOGIN_URL}...")
    print("Log in normally — reCAPTCHA usually skips for real Chrome users.")
    print("Once you see the partners dashboard, this script will save cookies and exit.\n")

    with sync_playwright() as p:
        # Headed: a real window pops up. User-agent unset so it's the
        # actual Chromium UA — no need for stealth tricks here.
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            storage_state=str(STATE_FILE) if STATE_FILE.exists() else None,
        )
        page = context.new_page()
        page.goto(SLR_LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)

        # Wait up to 5 minutes for the URL to leave /signin (i.e. login completed)
        try:
            page.wait_for_url(lambda u: "/signin" not in u, timeout=300_000)
        except Exception as e:
            print(f"\nNo dashboard reached within 5 min: {e}")
            print("Closing without saving — re-run when you're ready.")
            browser.close()
            return 1

        print(f"\nLogin detected ({page.url}). Saving cookies...")
        context.storage_state(path=str(STATE_FILE))
        browser.close()

    if not STATE_FILE.exists() or STATE_FILE.stat().st_size < 100:
        print(f"ERROR: state file was not written (or is empty): {STATE_FILE}")
        return 2
    print(f"Saved → {STATE_FILE} ({STATE_FILE.stat().st_size} bytes)")

    if args.no_sync:
        print("--no-sync: skipping Windows sync.")
        return 0

    if not Path(WINDOWS_KEY).exists():
        print(f"NOTE: Windows SSH key not found at {WINDOWS_KEY}; skipping sync.")
        print(f"      Copy {STATE_FILE} to {WINDOWS_HOST}:{WINDOWS_DEST}slr.json yourself.")
        return 0

    print(f"\nSyncing to Windows ({WINDOWS_HOST})...")
    # Make sure dest dir exists on Windows
    subprocess.run([
        "ssh", "-i", WINDOWS_KEY, WINDOWS_HOST,
        'powershell -Command "New-Item -ItemType Directory -Path C:\\Users\\andre\\.scraper_state -Force | Out-Null"',
    ], check=False)
    rc = subprocess.run([
        "scp", "-i", WINDOWS_KEY, str(STATE_FILE),
        f"{WINDOWS_HOST}:{WINDOWS_DEST}slr.json",
    ]).returncode
    if rc != 0:
        print(f"SCP failed (exit {rc}). Cookies are saved locally; sync manually.")
        return rc

    print(f"\nDone. SLR cookies now live on Windows for ~30 days.")
    print("Daily scheduled task (EclatechRevenueDailyRefresh) will pick them up tomorrow morning at 6 AM.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
