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
import re
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
# VRPorn's UI exposes daily totals (not per-video) under /account/earnings/.
# Per-video data lives elsewhere in the partner portal (TBD); for now the
# daily file feeds the dashboard's "yesterday" + "this-month-daily" cards.
OUT_VRPORN = DOCUMENTS / "vrporn_daily.csv"
# Daily-totals files (one per platform, all merge into _DailyData on upload).
OUT_POVR_DAILY = DOCUMENTS / "povr_daily.csv"
OUT_SLR_DAILY  = DOCUMENTS / "slr_daily.csv"


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
def _solve_slr_recaptcha(page: Page, api_key: str) -> str:
    """Submit the page's reCAPTCHA v2 challenge to 2Captcha and inject the
    response token into the form. Returns the solver's solution token
    (mostly for logging/debugging).

    2Captcha pricing: ~$2.99 per 1000 reCAPTCHA v2 solves at the time of
    writing. Daily SLR scrape = 1 solve/day = ~$1/year of CAPTCHA budget.

    Set TWOCAPTCHA_API_KEY in .env. Sign up + fund at https://2captcha.com.
    """
    # Lazy import so the rest of the file stays useful when the dep isn't
    # installed (e.g. running --povr-daily on a fresh machine).
    try:
        from twocaptcha import TwoCaptcha
    except ImportError as e:
        raise RuntimeError(
            "twocaptcha-python not installed. `pip install 2captcha-python` "
            "(or remove TWOCAPTCHA_API_KEY from .env to fall back to --headed)"
        ) from e

    sitekey = page.evaluate(
        "() => { const el = document.querySelector('[data-sitekey]'); "
        "return el ? el.getAttribute('data-sitekey') : null; }"
    )
    if not sitekey:
        raise RuntimeError("SLR: no reCAPTCHA data-sitekey on page (page layout changed?)")

    log.info(f"SLR: solving reCAPTCHA via 2Captcha (sitekey={sitekey[:20]}...)")
    solver = TwoCaptcha(api_key)
    # The solver blocks until 2Captcha returns (typically 15-45s for v2).
    result = solver.recaptcha(sitekey=sitekey, url=page.url)
    token = result.get("code", "")
    if not token:
        raise RuntimeError(f"SLR: 2Captcha returned no token: {result}")

    # Inject the token into the hidden response field that reCAPTCHA's JS
    # would normally populate when the user clicks "I'm not a robot".
    page.evaluate(
        "(t) => {"
        "  const el = document.getElementById('g-recaptcha-response');"
        "  if (el) { el.innerHTML = t; el.value = t; el.style.display = 'block'; }"
        "  document.querySelectorAll('textarea[name=g-recaptcha-response]').forEach("
        "    e => { e.innerHTML = t; e.value = t; }"
        "  );"
        "}",
        token,
    )
    log.info(f"SLR: reCAPTCHA token injected ({len(token)} chars)")
    return token


def scrape_slr(page: Page, dry_run: bool) -> list[list[str]]:
    """Log into SLR partners (partners.sexlikereal.com) and pull all-studios
    daily revenue from /statistics/daily/...

    Output schema (matches _DailyData via uploader normalization):
      Date (ISO), Studio, Total Earnings $

    SLR's login form is gated by Google reCAPTCHA v2. Two paths:

      1. Set TWOCAPTCHA_API_KEY in .env — we solve the captcha automatically
         via the 2Captcha service (~$0.003 per solve = ~$1/year for daily).
      2. Run with --headed once, complete the challenge by hand. Cookies
         persist under ~/.scraper_state/slr.json for ~30 days.

    Once authed, navigate to the per-studio daily stats page. The URL the
    user gave us as a starting point: /statistics/daily/studio/64/project/1
    """
    from datetime import date, timedelta

    user = os.environ.get("SLR_USER")
    pw   = os.environ.get("SLR_PASS")
    if not user or not pw:
        raise RuntimeError("SLR_USER / SLR_PASS env vars not set")

    log.info("SLR: opening partners portal...")
    page.goto("https://partners.sexlikereal.com/user/signin",
              wait_until="domcontentloaded", timeout=30_000)

    # Already authed via persisted cookies? Sign-in URL redirects off /signin.
    if "/signin" in page.url:
        log.info("SLR: not authed (cookies expired or never saved)")

        # Three paths to get past the reCAPTCHA, in order of preference:
        #   1. TWOCAPTCHA_API_KEY in env → automated solve (~$1/yr daily)
        #   2. Cookie-refresh helper (slr_refresh_cookies.py) → free,
        #      done-once-a-month from a real Chrome on any machine.
        #      Real browsers almost never see the captcha at all.
        #   3. --headed flag with a human present → manual click.
        captcha_key = os.environ.get("TWOCAPTCHA_API_KEY", "").strip()
        if captcha_key:
            page.fill('input[name="email"]', user)
            page.fill('input[name="password"]', pw)
            _solve_slr_recaptcha(page, captcha_key)
            try:
                page.locator('input[type="submit"]').click()
                page.wait_for_url(lambda u: "/signin" not in u, timeout=60_000)
            except PWTimeout:
                raise RuntimeError(
                    "SLR: 2Captcha-assisted login failed. Either the balance is "
                    "empty or sitekey changed — re-run with --headed to fall back."
                )
            log.info(f"SLR: login successful via 2Captcha ({page.url})")
        else:
            # No captcha solver configured. The right fix is to run
            # slr_refresh_cookies.py from any machine with a real Chrome,
            # which produces a fresh ~/.scraper_state/slr.json that this
            # scraper picks up. Surface a loud, actionable error.
            raise RuntimeError(
                "SLR cookies are stale or missing. Run "
                "`python3 slr_refresh_cookies.py` from any machine with a "
                "real Chrome (Mac, your laptop). It opens a window, you log "
                "in normally (reCAPTCHA almost never challenges real users), "
                "and cookies sync to Windows automatically. Lasts ~30 days."
            )

    # Discover the dropdown's studio IDs by walking the studios menu
    # element on /statistics/daily. The user has 5 studios per the live UI:
    # VRHush, VRAllure, FuckPassVR, BlowJobNow, NaughtyJOI — each with
    # its own numeric ID (studio/64 was confirmed = FuckPassVR).
    log.info("SLR: discovering studio IDs from the picker dropdown...")
    today = date.today()
    # Loop window: how far back we want to capture. SLR's daily-stats table
    # caps output at ~30 rows from the `?from=` anchor (returns the FIRST
    # 30 days from that point, NOT the most recent), so a single fetch with
    # from=today-60d only yields the OLDEST 30 days. Fix: loop month-by-month
    # from the start window forward, fetching each month separately and
    # stitching results.
    days_back = int(os.environ.get("SLR_DAYS_BACK", "75"))
    start_anchor = (today.replace(day=1) - timedelta(days=days_back)).replace(day=1)
    page.goto(f"https://partners.sexlikereal.com/statistics/daily/studio/64/project/1?from={start_anchor.isoformat()}",
              wait_until="networkidle", timeout=30_000)

    studios = _discover_slr_studios(page)
    if not studios:
        # Fallback: just scrape the studio we landed on
        studios = [(64, "Studio 64")]
    log.info(f"SLR: {len(studios)} studio(s) found: {[s[1] for s in studios]}")

    # Build the list of month-anchor `from=` values to walk. SLR's table
    # returns at most ~30 rows from each anchor (the OLDEST 30 days from
    # `from`, not the most recent), so we iterate month-by-month from the
    # start anchor forward to today, then fetch each studio per anchor.
    anchors: list[date] = []
    cur = start_anchor
    while cur <= today:
        anchors.append(cur)
        # Step to the first of the next month
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1, day=1)
        else:
            cur = cur.replace(month=cur.month + 1, day=1)
    log.info(f"SLR: walking {len(anchors)} monthly anchor(s) from {anchors[0].isoformat()} → today")

    out: list[list[str]] = []
    seen_keys: set[tuple[str, str]] = set()  # (date, studio) — dedupe across loops
    for sid, sname in studios:
        added_total = 0
        for anchor in anchors:
            url = (f"https://partners.sexlikereal.com/statistics/daily/"
                   f"studio/{sid}/project/1?from={anchor.isoformat()}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
                page.wait_for_selector("table tbody tr", timeout=20_000)
            except Exception as e:
                log.warning(f"SLR: studio {sid} ({sname}) anchor={anchor.isoformat()} "
                            f"failed — {type(e).__name__}; skipping this window")
                continue

            raw_rows = page.eval_on_selector_all(
                "table tbody tr",
                "els => els.map(tr => [...tr.querySelectorAll('td')].map(td => (td.innerText||'').trim()))",
            )
            added = 0
            for cells in raw_rows:
                if len(cells) < 11:
                    continue
                date_str = cells[0].strip()
                if not date_str or date_str.lower().startswith("total"):
                    continue
                try:
                    iso = datetime.strptime(date_str, "%b %d, %Y").strftime("%Y-%m-%d")
                except ValueError:
                    continue
                key = (iso, sname)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                total_income = cells[10].replace("$", "").replace(",", "").strip() or "0"
                out.append([iso, sname, total_income])
                added += 1
            added_total += added
        log.info(f"SLR: {sname} (studio/{sid})  +{added_total} daily rows across {len(anchors)} window(s)")

    log.info(f"SLR: total daily rows across {len(studios)} studio(s): {len(out)}")
    return out


# Map raw dropdown labels → canonical studio codes the rest of the system uses.
# The portal renders e.g. "VRHush (VR Straight)" — we strip the suffix and map.
_SLR_STUDIO_NAMES: dict[str, str] = {
    "vrhush":     "VRH",
    "vrallure":   "VRA",
    "fuckpassvr": "FPVR",
    "blowjobnow": "BJN",
    "naughtyjoi": "NJOI",
}


def _slr_canonicalize_studio(raw: str) -> str:
    """Trim '(VR Straight)' / '(POV)' suffix, map to canonical 4-letter code."""
    base = re.sub(r"\s*\(.*?\)\s*", "", raw or "").strip().lower()
    return _SLR_STUDIO_NAMES.get(base, raw.strip())


def _discover_slr_studios(page: Page) -> list[tuple[int, str]]:
    """Read the studio dropdown on /statistics/daily/... and return
    [(studio_id, canonical_name), ...] for every studio the user can see.

    The page uses a Select2-enhanced <select class="js-m-select--studio">
    with <option value="<id>"> children. The original <select> is hidden
    by Select2 but still in the DOM, so we read its options directly —
    no need to expand the visible UI dropdown.

    Verified options on the live page:
      value="64"  → VRHush (VR Straight)       → VRH
      value="213" → VRAllure (VR Straight)     → VRA
      value="352" → FuckPassVR (VR Straight)   → FPVR
      value="489" → BlowJobNow (VR Straight)   → BJN
      value="663" → NaughtyJOI (VR Straight)   → NJOI
    """
    raw = page.eval_on_selector_all(
        "select.js-m-select--studio option, select[class*='studio'] option",
        """els => els.map(e => ({
            value: e.value,
            text: (e.textContent || '').trim()
        }))"""
    )
    out: list[tuple[int, str]] = []
    seen: set[int] = set()
    for r in raw:
        try:
            sid = int(r["value"])
        except (ValueError, TypeError):
            continue
        if sid in seen or not r["text"]:
            continue
        seen.add(sid)
        out.append((sid, _slr_canonicalize_studio(r["text"])))
    return out


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

    # POVR's /stats backend returns blank/empty HTML when the date range
    # spans more than ~1 year (server-side query timeout). The user's
    # existing CSV indexes by (Year × POVR_ID) — one row per video per
    # year that earned. We mirror that: paginate each year separately,
    # emit one row per (year, video) tuple.
    #
    # Per-page row counts are 97-100 (the dropdown pp=100 is approximate
    # not exact), so we ONLY stop a year's pagination when we hit a fully
    # empty page (0 data rows). 50 pages × 100 = 5000 rows is a generous
    # safety cap per year.
    today = date.today()
    YEARS = list(range(2022, today.year + 1))  # POVR launched Feb 2022
    PAGE_SIZE = 100
    MAX_PAGES_PER_YEAR = 50

    out: list[list[str]] = []

    for year in YEARS:
        d1 = f"{year}-01-01"
        d2 = today.isoformat() if year == today.year else f"{year}-12-31"
        year_count = 0

        for p_num in range(1, MAX_PAGES_PER_YEAR + 1):
            url = (f"https://partners.povr.com/stats?gr=scene&pp={PAGE_SIZE}"
                   f"&d1={d1}&d2={d2}&p={p_num}")
            # Per-page retry loop. POVR's CDN intermittently throws
            # ERR_CONNECTION_TIMED_OUT mid-scrape — single retry usually fixes
            # it. We also tolerate the no-rows timeout that signals end-of-pagination.
            page_loaded = False
            for attempt in (1, 2, 3):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    page.wait_for_selector("table tbody tr", timeout=20_000)
                    page_loaded = True
                    break
                except Exception as e:
                    if attempt < 3:
                        log.warning(f"POVR: {year} p={p_num} attempt {attempt} failed ({type(e).__name__}); retrying...")
                        page.wait_for_timeout(3_000)
                    else:
                        log.warning(f"POVR: {year} p={p_num} gave up after 3 attempts ({type(e).__name__}: {e}); moving to next year")
            if not page_loaded:
                break

            cells_per_row = page.eval_on_selector_all(
                "table tbody tr",
                "els => els.map(tr => [...tr.querySelectorAll('td')].map(td => (td.innerText||'').trim()))",
            )

            page_added = 0
            for cells in cells_per_row:
                if len(cells) < 5:
                    continue
                breakdown = cells[0]
                if breakdown.lower().startswith("total"):
                    continue
                m = re.match(r"#(\d+)\s*-\s*(.+)", breakdown)
                if not m:
                    continue
                povr_id = m.group(1)
                title   = m.group(2).strip()
                share = cells[4].replace("$", "").replace(",", "").strip()
                out.append([
                    str(year),                       # Year column = bucket year
                    povr_id,                         # POVR_ID
                    title,                           # Title
                    cells[1].replace(",", ""),       # Premium Views
                    cells[2],                        # Time Streamed (e.g. "14h, 41m")
                    cells[3].replace(",", ""),       # Downloads
                    share,                           # Member Share $
                ])
                page_added += 1
                year_count += 1

            log.info(f"POVR: {year} p={p_num}  +{page_added}  year_total={year_count}")
            if page_added == 0:
                break  # empty page — pagination exhausted for this year

    log.info(f"POVR: total (year, video) rows: {len(out)}")
    return out


def scrape_povr_daily(page: Page, dry_run: bool, lookback_days: int = 60) -> list[list[str]]:
    """Scrape POVR daily revenue (last `lookback_days`).

    Output schema (matches the _DailyData tab on the sheet):
      Date (YYYY-MM-DD), Studio (always 'All' for now), Total Earnings $

    Uses /stats?gr=day&pp=100&d1=<date>&d2=<today>. With gr=day, each row
    is one calendar day's total across all studios. POVR returns the
    table sorted desc by date. We don't paginate by default — 60 days
    fits in a single 100-row page.
    """
    import re
    from datetime import date, timedelta

    user = os.environ.get("POVR_USER")
    pw   = os.environ.get("POVR_PASS")
    if not user or not pw:
        raise RuntimeError("POVR_USER / POVR_PASS env vars not set")

    log.info("POVR daily: opening partners portal...")
    page.goto("https://partners.povr.com/", wait_until="domcontentloaded", timeout=30_000)

    # Same login dance as the per-video scraper — the form lives behind a
    # collapsed accordion on the marketing landing.
    if page.locator('input[name="username"]:visible').count() == 0:
        link = page.locator('a:has-text("Login"), button:has-text("Login")').first
        if link.count() > 0:
            link.click(timeout=10_000)
            page.wait_for_selector('input[name="username"]:visible', state="visible", timeout=10_000)
    if page.locator('input[name="username"]:visible').count() > 0:
        page.fill('input[name="username"]', user)
        page.fill('input[name="password"]', pw)
        page.click('button[type="submit"], input[type="submit"]')
        try:
            page.wait_for_url(lambda u: "stats" in u or "content" in u, timeout=20_000)
        except PWTimeout:
            pass

    today = date.today()
    d1 = (today - timedelta(days=lookback_days)).isoformat()
    d2 = today.isoformat()
    url = f"https://partners.povr.com/stats?gr=day&pp=100&d1={d1}&d2={d2}"
    log.info(f"POVR daily: loading {url}")

    last_exc: Exception | None = None
    for attempt in (1, 2, 3):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_load_state("networkidle", timeout=45_000)
            page.wait_for_selector("table tbody tr", timeout=30_000)
            last_exc = None
            break
        except Exception as e:
            last_exc = e
            log.warning(f"POVR daily: attempt {attempt}/3 failed ({type(e).__name__}); retrying...")
            page.wait_for_timeout(2_500)
    if last_exc is not None:
        raise last_exc

    cells_per_row = page.eval_on_selector_all(
        "table tbody tr",
        "els => els.map(tr => [...tr.querySelectorAll('td')].map(td => (td.innerText||'').trim()))",
    )

    out: list[list[str]] = []
    # POVR's daily TD[0] is a date string like "2026-04-30" (already ISO),
    # TD[4] is "$X,XXX.XX" Member Share. Skip the trailing "Total (N rows)".
    iso_date = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for cells in cells_per_row:
        if len(cells) < 5:
            continue
        first = cells[0].strip()
        if first.lower().startswith("total") or not iso_date.match(first):
            continue
        share = cells[4].replace("$", "").replace(",", "").strip()
        out.append([
            first,        # Date (already ISO)
            "All",        # Studio (POVR's daily view aggregates across studios)
            share,        # Total Earnings $ (raw)
        ])

    log.info(f"POVR daily: {len(out)} daily rows captured ({d1} → {d2})")
    return out



# ---------------------------------------------------------------------------
# VRPorn — admin.vrporn.com (or wherever the ODS portal lives)
# ---------------------------------------------------------------------------
def scrape_vrporn(page: Page, dry_run: bool) -> list[list[str]]:
    """Log into VRPorn (consumer site, content-creator account) and pull
    daily earnings totals from /account/earnings/.

    Output schema (matches what the dashboard wants for daily granularity):
      Date, Studio, Total Earnings $

    Note: VRPorn's UI doesn't expose per-video earnings via a stable URL
    we've found yet, so per-video catalog stays in the user's existing
    "VRPorn Videos" tab (manual import) until we discover that surface.
    What this scraper provides is *daily totals per studio*, which feeds
    the dashboard's "yesterday" + "this-month daily" cards.

    Scrape strategy:
      1. Log into vrporn.com (dismiss age-gate "Agree" button on the login modal,
         fill #v-0-0-1-0 / #v-0-0-1-1, submit)
      2. Navigate to /account/earnings/?studio=<NAME>&d1=<date>&d2=<date>
         for each studio + date range
      3. Parse the daily list (rendered as div.app-earnings-tab-premium__table-item
         with two cols: date string + dollar amount)
      4. Paginate via &page=N until empty
    """
    user = os.environ.get("VRPORN_USER")
    pw   = os.environ.get("VRPORN_PASS")
    if not user or not pw:
        raise RuntimeError("VRPORN_USER / VRPORN_PASS env vars not set")

    # ── Login (idempotent — skips if storage_state already authed) ───────────
    log.info("VRPorn: opening /login/...")
    page.goto("https://vrporn.com/login/", wait_until="domcontentloaded", timeout=30_000)

    # Age-gate modal — only the BUTTON.button_primary version, NOT the
    # "Website's Terms-of-Service Agreement" link with the same text.
    try:
        page.locator('button.button_primary:has-text("Agree")').first.click(timeout=5_000)
        page.wait_for_timeout(800)
    except Exception:
        pass

    # If we're still on /login/ AFTER dismissing the age gate, fill creds.
    if "/login" in page.url and page.locator('#v-0-0-1-0:visible').count() > 0:
        log.info("VRPorn: filling credentials...")
        page.fill('#v-0-0-1-0', user)
        page.fill('#v-0-0-1-1', pw)
        # Press Enter (the "Log In" button selector is ambiguous because
        # there's also a top-bar "Log In" link).
        page.locator('#v-0-0-1-1').press("Enter")
        page.wait_for_load_state("networkidle", timeout=20_000)

    # If we're still stuck on /login/ — bail loudly.
    if "/login" in page.url:
        raise RuntimeError("VRPorn login failed — still on /login/ after submit")

    # ── Use the proxy-statistics API directly ─────────────────────────────
    # The /account/earnings/ UI is just a thin client over an internal API:
    #   GET /proxy-statistics/api/v1/report/total
    #     ?date=YYYY-MM-DD       (range start, inclusive)
    #     &dateEnd=YYYY-MM-DD    (range end, inclusive)
    #     &page=N&limit=20
    # Once authenticated, the same session cookies that load /account/earnings/
    # work for the API. Hitting it directly bypasses the 20-row UI cap by
    # paginating via `page=` and walking arbitrary date ranges via `dateEnd=`.
    log.info("VRPorn: loading /account/earnings/ to warm session cookies...")
    page.goto("https://vrporn.com/account/earnings/", wait_until="networkidle", timeout=30_000)

    from datetime import date, timedelta
    today = date.today()
    days_back = int(os.environ.get("VRPORN_DAYS_BACK", "120"))
    range_start = today - timedelta(days=days_back)
    log.info(f"VRPorn: querying proxy-statistics API for "
             f"{range_start.isoformat()} → {today.isoformat()}")

    out: list[list[str]] = []
    seen_dates: set[str] = set()
    api_url = "https://vrporn.com/proxy-statistics/api/v1/report/total"
    MAX_PAGES = 30   # 30 pages × 20 rows = 600 days, plenty
    for page_n in range(1, MAX_PAGES + 1):
        params = {
            "date":    range_start.isoformat(),
            "dateEnd": today.isoformat(),
            "page":    str(page_n),
            "limit":   "20",
        }
        try:
            resp = page.request.get(api_url, params=params, timeout=20_000)
        except Exception as e:
            log.warning(f"VRPorn: API page {page_n} request failed: {type(e).__name__}; stopping")
            break
        if not resp.ok:
            log.warning(f"VRPorn: API page {page_n} returned {resp.status}; stopping")
            break
        try:
            payload = resp.json()
        except Exception:
            log.warning(f"VRPorn: API page {page_n} returned non-JSON; stopping")
            break
        # Payload shape (verified): {"data": {"items": [{"earnings": N, "createdDate": "YYYY-MM-DD"}, ...], "pageCount": N, ...}}
        data_obj = payload.get("data") if isinstance(payload, dict) else None
        items = data_obj.get("items") if isinstance(data_obj, dict) else None
        if not isinstance(items, list) or not items:
            log.info(f"VRPorn: API page {page_n} returned 0 items — done")
            break
        added = 0
        for item in items:
            iso = (item.get("createdDate") or item.get("date") or "")[:10]
            if not iso or iso in seen_dates:
                continue
            seen_dates.add(iso)
            amt = item.get("earnings") or 0
            try:
                amt_f = float(str(amt).replace("$", "").replace(",", ""))
            except (ValueError, TypeError):
                amt_f = 0.0
            # Output uses "Apr 30, 2026" — the format the uploader expects
            try:
                from datetime import datetime as _dt
                pretty = _dt.strptime(iso, "%Y-%m-%d").strftime("%b %d, %Y")
            except ValueError:
                pretty = iso
            out.append([pretty, "All", f"{amt_f:.2f}"])
            added += 1
        page_count = data_obj.get("pageCount", page_n) if isinstance(data_obj, dict) else page_n
        log.info(f"VRPorn: API page {page_n}/{page_count}  +{added} rows (total {len(out)})")
        if added == 0 or page_n >= page_count:
            break
    log.info(f"VRPorn: {len(out)} unique daily rows captured via API")
    return out


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
        # SLR scraper now writes daily-totals shape (Date / Studio / $);
        # the per-video CSV the manual export produces stays separately
        # in slr_all_studios_video_stats.csv until we discover the
        # equivalent post-login per-video page.
        "fn": scrape_slr,
        "out": OUT_SLR_DAILY,
        "header": ["Date", "Studio", "Total Earnings $"],
    },
    "povr": {
        "fn": scrape_povr,
        "out": OUT_POVR,
        "header": ["Year", "POVR_ID", "Title", "Premium Views",
                   "Time Streamed", "Downloads", "Member Share $"],
    },
    "povr-daily": {
        "fn": scrape_povr_daily,
        "out": OUT_POVR_DAILY,
        "header": ["Date", "Studio", "Total Earnings $"],
    },
    "vrporn": {
        "fn": scrape_vrporn,
        "out": OUT_VRPORN,
        # Daily-totals schema (we currently only scrape the "All" studio
        # aggregate; per-studio + per-video are TODOs that need additional
        # surface mapping).
        "header": ["Date", "Studio", "Total Earnings $"],
    },
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all",        action="store_true", help="Scrape all three platforms (per-video where available + daily)")
    ap.add_argument("--daily",      action="store_true", help="Scrape only daily-totals across all platforms (much faster than full per-video)")
    ap.add_argument("--slr",        action="store_true")
    ap.add_argument("--povr",       action="store_true", help="POVR per-video (full catalog, ~3 min)")
    ap.add_argument("--povr-daily", action="store_true", dest="povr_daily", help="POVR daily totals (last 60 days, ~10s)")
    ap.add_argument("--vrporn",     action="store_true")
    ap.add_argument("--headed",     action="store_true",
                    help="Show the browser (use for first-run 2FA / captcha)")
    ap.add_argument("--dry-run",    action="store_true",
                    help="Log in + navigate but don't write CSVs")
    args = ap.parse_args()

    targets: list[str] = []
    if args.all:
        targets = ["slr", "povr", "vrporn"]  # full per-video scrape (drops daily)
    elif args.daily:
        # SLR is included if EITHER:
        #   (a) we have valid persisted cookies (the 30-day cookie-refresh
        #       pattern via slr_refresh_cookies.py — free), OR
        #   (b) TWOCAPTCHA_API_KEY is configured (~$1/yr — paid).
        # Otherwise we'd fail-loud every morning. Operator can still run
        # `--slr` explicitly with `--headed` for a one-off manual login.
        targets = ["povr-daily", "vrporn"]
        slr_state = STATE_DIR / "slr.json"
        if os.environ.get("TWOCAPTCHA_API_KEY", "").strip() or slr_state.exists():
            targets.append("slr")
    else:
        for p in PLATFORMS:
            # argparse converts hyphens to underscores for attribute names
            attr = p.replace("-", "_")
            if getattr(args, attr, False):
                targets.append(p)
    if not targets:
        ap.error("Pass --all, --daily, or one of --slr / --povr / --povr-daily / --vrporn")

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
