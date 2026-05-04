#!/usr/bin/env python3
"""
scrape_revenue_data.py
======================
Headless Playwright scraper that logs into each partner-backend portal
(SexLikeReal, POVR, VRPorn), pulls per-video revenue stats, and writes
matching CSVs to ~/Documents/. Then refresh_premium_breakdowns.py picks
those CSVs up and pushes them to the "Premium Breakdowns" Google Sheet.

Designed to run on the Windows production server via scheduled task —
that machine has a stable IP, the partner accounts are already logged in
on its Chrome profile, and Playwright's Chromium is installed there.

Usage:
    # Pull all three platforms (default — runs the full monthly refresh)
    python3 scrape_revenue_data.py --all

    # Just one platform
    python3 scrape_revenue_data.py --slr
    python3 scrape_revenue_data.py --povr
    python3 scrape_revenue_data.py --vrporn

    # Headed mode (pop the browser open so you can solve a captcha or 2FA)
    python3 scrape_revenue_data.py --all --headed

    # Dry-run: log in + click around but DON'T save the CSVs
    python3 scrape_revenue_data.py --all --dry-run

Credentials:
    Read from the env vars below. Set them in the launching shell or in
    a `.env` file at the repo root (loaded automatically if present).

      SLR_USER, SLR_PASS                 - sellers.sexlikereal.com login
      POVR_USER, POVR_PASS               - partners.povr.com login
      VRPORN_USER, VRPORN_PASS           - admin.vrporn.com login

    Two-factor: we DO NOT bypass 2FA. If a portal requires it, run with
    --headed and complete the challenge by hand on first run; Playwright
    persists session cookies under ~/.scraper_state/<platform>.json so
    subsequent runs auto-resume.

Output:
    ~/Documents/slr_all_studios_video_stats.csv
    ~/Documents/povr_video_data.csv
    ~/Documents/vrporn_video_data.csv

The schema for each file is fixed — refresh_premium_breakdowns.py
validates the header before writing to the sheet, so any portal UI
changes that break our scrape are caught loudly.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

# Optional .env support — convenient for local dev, no-op if missing.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, TimeoutError as PWTimeout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scrape-revenue")


# ---------------------------------------------------------------------------
# Paths + constants
# ---------------------------------------------------------------------------
DOCUMENTS = Path.home() / "Documents"
STATE_DIR = Path.home() / ".scraper_state"
STATE_DIR.mkdir(exist_ok=True)

OUT_SLR    = DOCUMENTS / "slr_all_studios_video_stats.csv"
OUT_POVR   = DOCUMENTS / "povr_video_data.csv"
OUT_VRPORN = DOCUMENTS / "vrporn_video_data.csv"


# ---------------------------------------------------------------------------
# Browser / session helpers
# ---------------------------------------------------------------------------
def open_context(p, platform: str, headed: bool) -> tuple[Browser, BrowserContext]:
    """Spawn a Chromium with persisted storage state for `platform`.

    The state file holds session cookies + localStorage so logged-in sessions
    survive across runs (avoids triggering 2FA every monthly run).
    """
    state_path = STATE_DIR / f"{platform}.json"
    browser = p.chromium.launch(headless=not headed)
    context = browser.new_context(
        storage_state=str(state_path) if state_path.exists() else None,
        viewport={"width": 1440, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
    )
    return browser, context


def save_state(context: BrowserContext, platform: str) -> None:
    state_path = STATE_DIR / f"{platform}.json"
    context.storage_state(path=str(state_path))


# ---------------------------------------------------------------------------
# SexLikeReal — sellers.sexlikereal.com
# ---------------------------------------------------------------------------
def scrape_slr(page: Page, dry_run: bool) -> list[list[str]]:
    """Log into SLR partners (partners.sexlikereal.com) and pull
    all-studios per-video stats.

    Output schema:
      Studio, Release Date, SLR_ID, Title, Uniq Views, Favorites,
      Premium $, Sales $, Scripts $, Total Income $

    *FIRST-RUN REQUIREMENT*: SLR's login form is gated by Google
    reCAPTCHA v2 ("I'm not a robot" checkbox). We CANNOT solve this
    headlessly. The first time you run this script:

        python3 scrape_revenue_data.py --slr --headed

    Complete the reCAPTCHA + login by hand. We persist the resulting
    session cookies under ~/.scraper_state/slr.json. Subsequent runs
    skip the login form entirely (cookies survive ~30 days typically),
    so the monthly scheduled task runs unattended.

    Once logged-in, scrape the per-video stats page (URL/selectors below
    — confirmed against the user's existing CSV header).
    """
    user = os.environ.get("SLR_USER")
    pw   = os.environ.get("SLR_PASS")
    if not user or not pw:
        raise RuntimeError("SLR_USER / SLR_PASS env vars not set")

    log.info("SLR: opening partners portal...")
    page.goto("https://partners.sexlikereal.com/user/signin",
              wait_until="domcontentloaded", timeout=30_000)

    # Already authed via persisted cookies? Sign-in URL redirects off /signin.
    if "/signin" in page.url:
        log.info("SLR: not authed (still on /signin) — login form needs reCAPTCHA")
        # If a human is sitting in front of a headed browser they can solve
        # it; otherwise we surface a clear error so the monthly task fails
        # loudly instead of silently scraping a logged-out page.
        page.fill('input[name="email"]', user)
        page.fill('input[name="password"]', pw)
        # Wait up to 60s for either the URL to leave /signin (reCAPTCHA solved)
        # or for the user to give up.
        try:
            page.locator('input[type="submit"]').click()
            page.wait_for_url(lambda u: "/signin" not in u, timeout=60_000)
        except PWTimeout:
            raise RuntimeError(
                "SLR login still on /signin after 60s — reCAPTCHA likely "
                "blocking. Re-run with --headed and complete the challenge "
                "by hand. Cookies will persist for future unattended runs."
            )

    # TODO: navigate to the per-video stats page. Inspect the partners
    # portal's left-nav after a successful login to find the right URL
    # and table structure. Header in the user's existing CSV is:
    #   Studio | Release Date | SLR_ID | Title | Uniq Views | Favorites |
    #   Premium $ | Sales $ | Scripts $ | Total Income $
    # Likely candidates: /stats, /content, /videos, /earnings — fill in
    # once we've eyeballed the post-login dashboard.
    raise NotImplementedError(
        "SLR per-video stats page URL not yet known — run --headed once, "
        "navigate to the all-studios stats page in the browser, then update "
        "this function with the URL and table-column mapping."
    )


# ---------------------------------------------------------------------------
# POVR — partners.povr.com
# ---------------------------------------------------------------------------
def scrape_povr(page: Page, dry_run: bool) -> list[list[str]]:
    """Log into POVR partners and pull per-video stats.

    Output schema:
      Year, POVR_ID, Title, Premium Views, Time Streamed, Downloads, Member Share $

    Steps:
      1. Land on partners.povr.com → click 'Login' link → fill the modal form
         (form has name="username" + name="password", submit button)
      2. Navigate to /stats?gr=scene&pp=1000&d1=2018-01-01&d2=<today>
         - gr=scene: per-video grouping
         - pp=1000:  "All" per page
         - d1/d2:    date range — default of last-30-days only ships ~400
                     rows; we want all-time (~4,800)
      3. Scrape the table. TD[0] is `#<POVR_ID> - <Title>`, columns 1-4
         are Premium Views / Time Streamed / Downloads / Member Share Amount.
    """
    import re
    from datetime import date

    user = os.environ.get("POVR_USER")
    pw   = os.environ.get("POVR_PASS")
    if not user or not pw:
        raise RuntimeError("POVR_USER / POVR_PASS env vars not set")

    log.info("POVR: opening partners portal...")
    page.goto("https://partners.povr.com/", wait_until="domcontentloaded", timeout=30_000)

    # Marketing landing page renders the login form INSIDE a collapsed
    # accordion — the <input> exists in the DOM but is hidden until the
    # "Login" header link is clicked. If we land already authed, the
    # /stats nav appears and there's no login link to click. Detect by
    # form visibility, not presence.
    if page.locator('input[name="username"]:visible').count() == 0:
        login_link = page.locator('a:has-text("Login"), button:has-text("Login")').first
        if login_link.count() > 0:
            log.info("POVR: clicking Login link to expand form...")
            login_link.click(timeout=10_000)
            page.wait_for_selector('input[name="username"]:visible', state="visible", timeout=10_000)
        else:
            log.info("POVR: already authed (no Login link, form hidden)")
    if page.locator('input[name="username"]:visible').count() > 0:
        log.info("POVR: filling credentials...")
        page.fill('input[name="username"]', user)
        page.fill('input[name="password"]', pw)
        page.click('button[type="submit"], input[type="submit"]')
        try:
            page.wait_for_url(lambda u: "stats" in u or "content" in u, timeout=20_000)
        except PWTimeout:
            # Some logins land on '/' with a stale URL — soft tolerance.
            pass

    today = date.today().isoformat()
    url = f"https://partners.povr.com/stats?gr=scene&pp=1000&d1=2018-01-01&d2={today}"
    log.info(f"POVR: loading per-video stats ({url})")
    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_load_state("networkidle", timeout=30_000)
    page.wait_for_selector("table tbody tr", timeout=30_000)

    raw_rows = page.eval_on_selector_all(
        "table tbody tr",
        "els => els.map(tr => [...tr.querySelectorAll('td')].map(td => (td.innerText||'').trim()))",
    )
    log.info(f"POVR: scraped {len(raw_rows)} table rows")

    out: list[list[str]] = []
    for cells in raw_rows:
        if len(cells) < 5:
            continue
        breakdown = cells[0]
        # Trailing "Total (N rows)" summary row — skip
        if breakdown.lower().startswith("total"):
            continue
        # Parse "#5821241 - Hard Wood On Fire"
        m = re.match(r"#(\d+)\s*-\s*(.+)", breakdown)
        povr_id = m.group(1) if m else ""
        title   = m.group(2).strip() if m else breakdown
        share = cells[4].replace("$", "").replace(",", "").strip()
        out.append([
            "",                          # Year — not in the per-video view
            povr_id,                     # POVR_ID
            title,                       # Title
            cells[1].replace(",", ""),   # Premium Views
            cells[2],                    # Time Streamed (e.g. "14h, 41m")
            cells[3].replace(",", ""),   # Downloads
            share,                       # Member Share $ (raw number)
        ])
    return out


# ---------------------------------------------------------------------------
# VRPorn — admin.vrporn.com (or wherever the ODS portal lives)
# ---------------------------------------------------------------------------
def scrape_vrporn(page: Page, dry_run: bool) -> list[list[str]]:
    """Log into VRPorn ODS / partner portal and pull per-video stats.

    EXPECTED OUTPUT SHAPE:
      Published Date, Title, Slug, Total Hits, Total Earnings $, View Hits,
      View Earnings $, Download Hits, Download Earnings $, Game Hits, Game Earnings $

    The user's existing CSV came from the ODS portal — historical data
    pre-Sep 2025 was their old ODS export, post-Sep 2025 is direct-payout
    via the admin panel. We may need to scrape both and merge.
    """
    user = os.environ.get("VRPORN_USER")
    pw   = os.environ.get("VRPORN_PASS")
    if not user or not pw:
        raise RuntimeError("VRPORN_USER / VRPORN_PASS env vars not set")

    log.info("VRPorn: navigating to login...")
    # TODO: confirm the actual portal URL — the user's note mentions both
    # "ODS portal" and "direct payouts", suggesting two surfaces.
    page.goto("https://admin.vrporn.com/login", wait_until="domcontentloaded")

    if "/login" in page.url:
        log.info("VRPorn: filling credentials...")
        page.fill('input[name="username"], input[type="email"]', user)
        page.fill('input[name="password"], input[type="password"]', pw)
        page.click('button[type="submit"]')
        try:
            page.wait_for_url(lambda u: "/login" not in u, timeout=15_000)
        except PWTimeout:
            raise RuntimeError("VRPorn login failed — check creds or 2FA")

    raise NotImplementedError(
        "VRPorn scrape not yet wired — need the URL of the per-video earnings "
        "page (ODS portal vs direct-payout admin) and the export selector."
    )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def write_csv(out: Path, header: list[str], rows: list[list[str]]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(header)
        w.writerows(rows)
    log.info(f"Wrote {len(rows)} rows → {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
PLATFORMS: dict[str, dict] = {
    "slr": {
        "fn": scrape_slr,
        "out": OUT_SLR,
        "header": ["Studio", "Release Date", "SLR_ID", "Title", "Uniq Views",
                   "Favorites", "Premium $", "Sales $", "Scripts $", "Total Income $"],
    },
    "povr": {
        "fn": scrape_povr,
        "out": OUT_POVR,
        "header": ["Year", "POVR_ID", "Title", "Premium Views",
                   "Time Streamed", "Downloads", "Member Share $"],
    },
    "vrporn": {
        "fn": scrape_vrporn,
        "out": OUT_VRPORN,
        "header": ["Published Date", "Title", "Slug", "Total Hits", "Total Earnings $",
                   "View Hits", "View Earnings $", "Download Hits", "Download Earnings $",
                   "Game Hits", "Game Earnings $"],
    },
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all",    action="store_true", help="Scrape all three platforms")
    ap.add_argument("--slr",    action="store_true")
    ap.add_argument("--povr",   action="store_true")
    ap.add_argument("--vrporn", action="store_true")
    ap.add_argument("--headed",  action="store_true",
                    help="Show the browser (use for first-run 2FA / captcha)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Log in + navigate but don't write CSVs")
    args = ap.parse_args()

    targets: list[str] = []
    if args.all:
        targets = list(PLATFORMS.keys())
    else:
        for p in PLATFORMS:
            if getattr(args, p):
                targets.append(p)
    if not targets:
        ap.error("Pass --all or one of --slr / --povr / --vrporn")

    failed: list[str] = []
    with sync_playwright() as p:
        for platform in targets:
            spec = PLATFORMS[platform]
            log.info(f"=== {platform.upper()} ===")
            browser, context = open_context(p, platform, args.headed)
            try:
                page = context.new_page()
                rows = spec["fn"](page, args.dry_run)
                save_state(context, platform)
                if not args.dry_run:
                    write_csv(spec["out"], spec["header"], rows)
                log.info(f"{platform}: ok ({len(rows)} rows)")
            except NotImplementedError as e:
                log.warning(f"{platform}: skipped — {e}")
                failed.append(platform)
            except Exception as e:
                log.error(f"{platform}: failed — {e}")
                failed.append(platform)
            finally:
                context.close()
                browser.close()

    if failed:
        log.warning(f"Platforms with failures or stubs: {failed}")
        return 1
    log.info("All scrapes completed. Run refresh_premium_breakdowns.py to push to the sheet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
