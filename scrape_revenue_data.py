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
        log.info("SLR: not authed — filling credentials")
        page.fill('input[name="email"]', user)
        page.fill('input[name="password"]', pw)

        # Solve the reCAPTCHA. Prefer 2Captcha if configured; fall back to
        # waiting for a human (--headed mode) for up to 60s.
        captcha_key = os.environ.get("TWOCAPTCHA_API_KEY", "").strip()
        if captcha_key:
            _solve_slr_recaptcha(page, captcha_key)
        else:
            log.info("SLR: no TWOCAPTCHA_API_KEY — assuming --headed mode (60s grace for human solver)")

        try:
            page.locator('input[type="submit"]').click()
            page.wait_for_url(lambda u: "/signin" not in u, timeout=60_000)
        except PWTimeout:
            raise RuntimeError(
                "SLR login still on /signin after 60s — reCAPTCHA solver may have failed "
                "or 2Captcha balance is empty. Run --headed to fall back to manual."
            )
        log.info(f"SLR: login successful ({page.url})")

    # TODO: this requires a real signed-in session to inspect. The URL the
    # user gave us — /statistics/daily/studio/64/project/1 — implies:
    #   - "studio/64" = a numeric studio ID (we'll need to discover the
    #     full set: probably one per studio, e.g. 64=VRH, 65=VRA, 66=FPVR).
    #   - "project/1" = a project filter (possibly studio sub-channel).
    # Once we have a working session post-2Captcha, the next step is to
    # eyeball this page, identify the table structure, and fill in the
    # parsing — same shape as scrape_povr_daily / scrape_vrporn.
    log.info("SLR: navigating to daily stats page...")
    today = date.today()
    d_from = (today - timedelta(days=60)).isoformat()
    page.goto(f"https://partners.sexlikereal.com/statistics/daily/studio/64/project/1?from={d_from}",
              wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_load_state("networkidle", timeout=20_000)

    raise NotImplementedError(
        "SLR daily-stats parsing not yet wired — need to inspect the live "
        "page DOM after a successful 2Captcha-assisted login. Re-run once "
        "TWOCAPTCHA_API_KEY is set + funded, then we'll fill in the table parser."
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

    # ── Scrape /account/earnings/ ────────────────────────────────────────────
    # Default view is "last 30-or-so days" with no date filter. For lifetime
    # capture we'd need to step back month-by-month; for the user's immediate
    # ask ("this month daily + yesterday") the default 20-row view is enough.
    # We loop pagination while the page has rows.
    log.info("VRPorn: loading /account/earnings/...")
    page.goto("https://vrporn.com/account/earnings/", wait_until="networkidle", timeout=30_000)

    # Studio dropdown values seen on the live page:
    STUDIOS = ["All", "FuckPassVR", "XPlayVR", "BlowJobNow", "VRHush", "VRAllure", "NaughtyJOI"]
    # We only scrape "All" for now — the per-studio split is summable from
    # POVR/SLR which DO give us studio-level data, and VRPorn's "All" total
    # is what the user's existing dashboard surfaces.
    # TODO: per-studio loop once we confirm the URL param name (likely ?studio=<name>).

    # Page 1 of /account/earnings/ shows the most recent ~20 days. The
    # `?page=N` param in the URL doesn't actually paginate — it returns
    # the same content. The visible "1, 2" page links use JS navigation
    # that we haven't mapped yet. For the user's immediate need ("this
    # month daily + yesterday") the default 20-day window is enough; the
    # historical backfill can come later via a different endpoint.
    out: list[list[str]] = []
    pattern = re.compile(r'([A-Z][a-z]{2}\s+\d+,\s+\d{4})\s*\n\s*\$([\d,]+(?:\.\d+)?)')
    body = page.evaluate("document.body.innerText")
    matches = pattern.findall(body)
    seen_dates: set[str] = set()
    for date_str, amount in matches:
        if date_str in seen_dates:
            continue
        seen_dates.add(date_str)
        out.append([
            date_str,                            # Date (e.g. "Apr 30, 2026")
            "All",                               # Studio (TODO: per-studio loop)
            amount.replace(",", ""),             # Total Earnings $ (raw)
        ])
    log.info(f"VRPorn: {len(out)} unique daily rows captured (default last-20-day view)")
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
        # SLR is included only if a 2Captcha key is configured — otherwise
        # the daily run would fail-loud every morning. Operator can opt in
        # explicitly with `--slr` for a one-off --headed run regardless.
        targets = ["povr-daily", "vrporn"]
        if os.environ.get("TWOCAPTCHA_API_KEY", "").strip():
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
