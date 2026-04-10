#!/usr/bin/env python3
"""
scrape_platform_stats.py
========================
Scrapes model stats from SexLikeReal, VRPorn, and POVR, writes to Google Sheet.

New columns added to the collapsible stats group:
  SLR Followers | SLR Scenes | VRP Followers | VRP Views | POVR Views

SLR uses ID-based URLs (/pornstars/name-slug-1234) so profile URLs are
discovered via their search and cached to slr_cache.json between runs.

Usage:
    python3 /Users/andrewninn/Scripts/scrape_platform_stats.py
    python3 /Users/andrewninn/Scripts/scrape_platform_stats.py --tab "OC Models"
    python3 /Users/andrewninn/Scripts/scrape_platform_stats.py --overwrite
    python3 /Users/andrewninn/Scripts/scrape_platform_stats.py --dry-run

Requirements:
    pip3 install gspread google-auth playwright beautifulsoup4 --break-system-packages
    python3 -m playwright install chromium
"""

import argparse
import json
import logging
import re
import time
import unicodedata
from pathlib import Path

import gspread
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

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

# New columns to add/update (in order they'll appear in the stats group)
PLATFORM_COLS = [
    "SLR Followers",
    "SLR Scenes",
    "SLR Views",
    "VRP Followers",
    "VRP Views",
    "POVR Views",
    "OnlyFans",
    "Twitter",
    "Instagram",
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


# ── Name utilities ─────────────────────────────────────────────────────────────

def name_to_slug(name: str) -> str:
    """'Melody Marks' → 'melody-marks' (strips accents, special chars)"""
    # Strip accents
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name.strip())
    return name.strip("-")


def normalize_stat(text: str) -> str:
    """'3.5M Views' → '3.5M'  |  '2,600' → '2600'  |  '35.6K followers' → '35.6K'"""
    text = text.strip()
    # Extract leading number+suffix (handle commas in numbers)
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*([KkMmBb]?)", text)
    if not m:
        return text
    num = m.group(1).replace(",", "")
    suffix = m.group(2).upper() if m.group(2) else ""
    return f"{num}{suffix}"


# ── SLR cache ──────────────────────────────────────────────────────────────────

def load_slr_cache() -> dict:
    if SLR_CACHE_FILE.exists():
        return json.loads(SLR_CACHE_FILE.read_text())
    return {}


def save_slr_cache(cache: dict) -> None:
    SLR_CACHE_FILE.write_text(json.dumps(cache, indent=2, sort_keys=True))


# ── Browser page fetch helper ──────────────────────────────────────────────────

def fetch_page(page, url: str, wait_ms: int = 2000) -> BeautifulSoup | None:
    """Navigate to *url*, wait for content, return BeautifulSoup. Returns None on error."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        time.sleep(wait_ms / 1000)
        return BeautifulSoup(page.content(), "html.parser")
    except Exception as e:
        log.debug(f"    fetch_page failed {url}: {e}")
        return None


# ── SexLikeReal ────────────────────────────────────────────────────────────────

def discover_slr_slug(page, name: str, cache: dict) -> str | None:
    """
    Find the SLR profile slug (e.g. 'melody-marks-2112') for a performer.
    1. Check cache first.
    2. Try direct URL (slug-base with no number → SLR may redirect to numbered slug).
    3. Search SLR performers page; try progressively looser matches:
       a. Exact: slug-base-<digits>
       b. Contains: slug starts with slug-base (handles extra words like -vr/-xxx)
       c. First-result: take the first /pornstars/X-<digits> link (best guess)
    4. Cache the result if found.
    """
    slug_base = name_to_slug(name)
    if slug_base in cache:
        return cache[slug_base]

    def _cache_and_return(val):
        cache[slug_base] = val
        log.debug(f"    [SLR] Discovered slug: {val}")
        return val

    # ── 1. Try direct URL (no number) — may redirect to the numbered slug ────────
    try:
        direct_url = f"https://www.sexlikereal.com/pornstars/{slug_base}"
        page.goto(direct_url, wait_until="domcontentloaded", timeout=15_000)
        final_url = page.url
        m = re.search(r"/pornstars/([a-z0-9-]+-\d+)(?:[/?]|$)", final_url)
        if m:
            return _cache_and_return(m.group(1))
        # Also check canonical link in page source
        soup = BeautifulSoup(page.content(), "html.parser")
        canon = soup.find("link", rel="canonical")
        if canon and canon.get("href"):
            m = re.search(r"/pornstars/([a-z0-9-]+-\d+)(?:[/?]|$)", canon["href"])
            if m:
                return _cache_and_return(m.group(1))
    except Exception:
        pass

    # ── 2. Search page ───────────────────────────────────────────────────────────
    search_url = f"https://www.sexlikereal.com/pornstars?q={name.replace(' ', '+')}"
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=20_000)
        try:
            page.wait_for_selector("a[href*='/pornstars/']", timeout=6_000)
        except Exception:
            pass
        time.sleep(1.5)
        soup = BeautifulSoup(page.content(), "html.parser")
    except Exception as e:
        log.debug(f"    [SLR] search failed for {name}: {e}")
        return None

    all_links = [a["href"] for a in soup.find_all("a", href=True)
                 if "/pornstars/" in a["href"]]
    slug_links = []
    for href in all_links:
        m = re.search(r"/pornstars/([a-z0-9-]+-\d+)(?:[/?]|$)", href)
        if m:
            slug_links.append(m.group(1))

    # a. Exact match: slug-base-<digits>
    exact = re.compile(r"^" + re.escape(slug_base) + r"-\d+$")
    for candidate in slug_links:
        if exact.match(candidate):
            return _cache_and_return(candidate)

    # b. Contains match: slug starts with slug-base (e.g. adriana-chechik-vr-123)
    for candidate in slug_links:
        name_part = re.sub(r"-\d+$", "", candidate)
        if name_part.startswith(slug_base):
            return _cache_and_return(candidate)

    # c. First-name + last-name partial: both first and last name words appear in slug
    parts = slug_base.split("-")
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        for candidate in slug_links:
            if first in candidate and last in candidate:
                return _cache_and_return(candidate)

    return None


def scrape_slr(page, name: str, cache: dict) -> dict:
    """Return {'slr_followers': ..., 'slr_scenes': ...} or {}."""
    slug = discover_slr_slug(page, name, cache)
    if not slug:
        return {}

    url = f"https://www.sexlikereal.com/pornstars/{slug}"
    soup = fetch_page(page, url, wait_ms=2000)
    if not soup:
        return {}

    stats = {}
    text_blocks = [el.get_text(" ", strip=True) for el in soup.find_all(
        ["span", "div", "p", "li", "strong", "b"]
    )]

    for t in text_blocks:
        # "35.6K followers" / "12K followers"
        if "follower" in t.lower() and "slr_followers" not in stats:
            m = re.search(r"([\d,.]+[KkMm]?)\s+followers?", t, re.IGNORECASE)
            if m:
                stats["slr_followers"] = normalize_stat(m.group(1))

        # "348 Total Scenes" / "107 scenes"
        if "scene" in t.lower() and "slr_scenes" not in stats:
            m = re.search(r"(\d+)\s+(?:total\s+)?scenes?", t, re.IGNORECASE)
            if m and int(m.group(1)) < 10000:
                stats["slr_scenes"] = m.group(1)

        # "3.5M views" / "250K views" / "Views: 1.2M"
        if "view" in t.lower() and "slr_views" not in stats:
            m = re.search(r"([\d,.]+[KkMmBb]?)\s+views?", t, re.IGNORECASE)
            if not m:
                m = re.search(r"views?\s*[:\-]?\s*([\d,.]+[KkMmBb]?)", t, re.IGNORECASE)
            if m:
                stats["slr_views"] = normalize_stat(m.group(1))

    return stats


# ── VRPorn ─────────────────────────────────────────────────────────────────────

def scrape_vrporn(page, name: str) -> dict:
    """Return {'vrp_followers': ..., 'vrp_views': ..., 'vrp_videos': ...} or {}."""
    slug = name_to_slug(name)
    url = f"https://vrporn.com/pornstars/{slug}/"
    soup = fetch_page(page, url, wait_ms=2000)
    if not soup:
        return {}

    # Check for 404 / no profile
    if soup.find("title") and "404" in (soup.find("title").get_text() or ""):
        return {}

    stats = {}
    text_blocks = [el.get_text(" ", strip=True) for el in soup.find_all(
        ["span", "div", "p", "li", "strong", "b", "h2", "h3"]
    )]

    for t in text_blocks:
        # "74 Videos"
        if "video" in t.lower() and "vrp_videos" not in stats:
            m = re.search(r"(\d+)\s+videos?", t, re.IGNORECASE)
            if m and int(m.group(1)) < 50000:
                stats["vrp_videos"] = m.group(1)

        # "2.6K Followers" / "1,700 Followers"
        if "follower" in t.lower() and "vrp_followers" not in stats:
            m = re.search(r"([\d,.]+[KkMm]?)\s+followers?", t, re.IGNORECASE)
            if m:
                stats["vrp_followers"] = normalize_stat(m.group(1))

        # "3.5M Views" / "761.6K Views"
        if "view" in t.lower() and "vrp_views" not in stats:
            m = re.search(r"([\d,.]+[KkMmBb]?)\s+views?", t, re.IGNORECASE)
            if m:
                stats["vrp_views"] = normalize_stat(m.group(1))

    return stats


# ── POVR ───────────────────────────────────────────────────────────────────────

def scrape_povr(page, name: str) -> dict:
    """Return {'povr_views': ...} or {}."""
    slug = name_to_slug(name)
    url = f"https://povr.com/pornstars/{slug}"
    soup = fetch_page(page, url, wait_ms=2000)
    if not soup:
        return {}

    # Check for 404 / redirect to listing
    title = soup.find("title")
    if title and re.search(r"404|not found|pornstars$", title.get_text(), re.I):
        return {}

    stats = {}
    text_blocks = [el.get_text(" ", strip=True) for el in soup.find_all(
        ["span", "div", "p", "li", "strong", "b", "h1", "h2"]
    )]

    for t in text_blocks:
        # "3.96m views" / "106k views" / "1.17m views"
        if "view" in t.lower() and "povr_views" not in stats:
            m = re.search(r"([\d,.]+[KkMmBb]?)\s+views?", t, re.IGNORECASE)
            if m:
                stats["povr_views"] = normalize_stat(m.group(1))

    return stats


# ── OnlyFans ───────────────────────────────────────────────────────────────────

def scrape_onlyfans(page, name: str) -> dict:
    """
    Try to find a model's OnlyFans by searching SLR's performer page (which often
    links to OF) or by guessing common slug patterns.
    Returns {'of_subscribers': '35.6K'} or {}.
    """
    # Try slug variants: melody-marks → melodymarks, melodym, etc.
    slug = name_to_slug(name)
    compact = slug.replace("-", "")          # "melodymarks"
    first   = slug.split("-")[0]             # "melody"
    candidates = [slug, compact, first + "xxx", first + "xx", compact + "xxx"]

    for handle in candidates:
        url = f"https://onlyfans.com/{handle}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            time.sleep(1.5)
            soup = BeautifulSoup(page.content(), "html.parser")
            # Check for redirect to /404
            if page.url.endswith("/404") or "not found" in soup.get_text().lower()[:200]:
                continue
            # Look for fans/subscribers count
            text = soup.get_text(" ", strip=True)
            m = re.search(r"([\d,.]+[KkMm]?)\s*(?:fans|subscribers?|following)", text, re.IGNORECASE)
            if m:
                return {"of_subscribers": normalize_stat(m.group(1))}
        except Exception:
            continue
    return {}


# ── Twitter / X ────────────────────────────────────────────────────────────────

def scrape_twitter(page, name: str) -> dict:
    """
    Look up Twitter/X follower count from the model's profile.
    Returns {'twitter_followers': '125.4K'} or {}.
    """
    slug    = name_to_slug(name)
    compact = slug.replace("-", "")
    candidates = [compact, slug.replace("-", "_"), name.replace(" ", "").lower()]

    for handle in candidates:
        url = f"https://x.com/{handle}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            time.sleep(2.0)
            soup = BeautifulSoup(page.content(), "html.parser")
            text = soup.get_text(" ", strip=True)
            # Bail if profile doesn't exist
            if "This account doesn" in text or "doesn't exist" in text:
                continue
            # "125.4K Followers"
            m = re.search(r"([\d,.]+[KkMm]?)\s*followers?", text, re.IGNORECASE)
            if m:
                return {"twitter_followers": normalize_stat(m.group(1))}
        except Exception:
            continue
    return {}


# ── Instagram ──────────────────────────────────────────────────────────────────

def scrape_instagram(page, name: str) -> dict:
    """
    Look up Instagram follower count from the model's public profile.
    Returns {'ig_followers': '85.2K'} or {}.
    """
    slug    = name_to_slug(name)
    compact = slug.replace("-", "")
    candidates = [compact, slug.replace("-", "_"), name.replace(" ", "").lower()]

    for handle in candidates:
        url = f"https://www.instagram.com/{handle}/"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            time.sleep(2.0)
            soup = BeautifulSoup(page.content(), "html.parser")
            text = soup.get_text(" ", strip=True)
            if "Sorry, this page" in text or "Page Not Found" in text:
                continue
            # Instagram bakes follower count into og:description meta
            meta = soup.find("meta", {"name": "description"}) or soup.find("meta", {"property": "og:description"})
            if meta:
                content = meta.get("content", "")
                m = re.search(r"([\d,.]+[KkMm]?)\s*(?:Followers|followers)", content)
                if m:
                    return {"ig_followers": normalize_stat(m.group(1))}
        except Exception:
            continue
    return {}


# ── Sheet helpers ──────────────────────────────────────────────────────────────

def col_index_to_a1(idx: int) -> str:
    """0-based index → column letter(s): 0→A, 25→Z, 26→AA"""
    result = ""
    n = idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def ensure_platform_cols(ws, headers: list) -> list:
    """Append any missing PLATFORM_COLS headers to row 3. Returns updated headers."""
    missing = [c for c in PLATFORM_COLS if c not in headers]
    if not missing:
        return headers

    updates = []
    start = len(headers)
    for i, col_name in enumerate(missing):
        col_a1 = col_index_to_a1(start + i)
        updates.append({
            "range": f"'{ws.title}'!{col_a1}{HEADER_ROW}",
            "values": [[col_name]],
        })
        headers.append(col_name)

    for attempt in range(3):
        try:
            ws.spreadsheet.values_batch_update({
                "valueInputOption": "RAW",
                "data": updates,
            })
            break
        except Exception as e:
            if attempt == 2:
                raise
            log.warning(f"  Column add attempt {attempt+1} failed: {e}. Retrying...")
            time.sleep(10)
    log.info(f"  Added columns: {missing}")
    return headers


# ── Tab processor ──────────────────────────────────────────────────────────────

def process_tab(ws, page, slr_cache: dict, overwrite: bool, dry_run: bool) -> int:
    all_rows = ws.get_all_values()
    if len(all_rows) < HEADER_ROW:
        return 0

    headers = [h.strip() for h in all_rows[HEADER_ROW - 1]]
    if not headers or not headers[0]:
        return 0

    if not dry_run:
        headers = ensure_platform_cols(ws, headers)

    col_map = {h: i for i, h in enumerate(headers) if h}
    name_col = col_map.get("Name", 0)

    # Check which platform cols exist
    plat_indices = {c: col_map.get(c) for c in PLATFORM_COLS}
    if not any(v is not None for v in plat_indices.values()):
        log.warning(f"  No platform columns found — skipping")
        return 0

    updates = []
    skipped = 0

    for row_i, row in enumerate(all_rows[DATA_START_ROW - 1:], start=DATA_START_ROW):
        if len(row) <= name_col:
            continue
        name = row[name_col].strip()
        if not name:
            continue

        # Skip if already filled (unless --overwrite)
        if not overwrite:
            already_filled = any(
                col_map.get(c) is not None
                and len(row) > col_map[c]
                and row[col_map[c]].strip()
                for c in PLATFORM_COLS
            )
            if already_filled:
                skipped += 1
                continue

        log.info(f"    {name}...")

        slr_stats  = scrape_slr(page, name, slr_cache)
        vrp_stats  = scrape_vrporn(page, name)
        povr_stats = scrape_povr(page, name)
        of_stats   = scrape_onlyfans(page, name)
        tw_stats   = scrape_twitter(page, name)
        ig_stats   = scrape_instagram(page, name)

        field_map = {
            "SLR Followers": slr_stats.get("slr_followers", ""),
            "SLR Scenes":    slr_stats.get("slr_scenes", ""),
            "SLR Views":     slr_stats.get("slr_views", ""),
            "VRP Followers": vrp_stats.get("vrp_followers", ""),
            "VRP Views":     vrp_stats.get("vrp_views", ""),
            "POVR Views":    povr_stats.get("povr_views", ""),
            "OnlyFans":      of_stats.get("of_subscribers", ""),
            "Twitter":       tw_stats.get("twitter_followers", ""),
            "Instagram":     ig_stats.get("ig_followers", ""),
        }

        found_any = any(v for v in field_map.values())
        if found_any:
            log.info(f"      SLR: {slr_stats or '-'}  VRP: {vrp_stats or '-'}  "
                     f"POVR: {povr_stats or '-'}  OF: {of_stats or '-'}  "
                     f"TW: {tw_stats or '-'}  IG: {ig_stats or '-'}")
        else:
            log.info(f"      No platform profiles found")

        for col_name, value in field_map.items():
            if not value:
                continue
            col_idx = plat_indices.get(col_name)
            if col_idx is None:
                continue
            col_a1 = col_index_to_a1(col_idx)
            updates.append({
                "range": f"'{ws.title}'!{col_a1}{row_i}",
                "values": [[value]],
            })

        time.sleep(0.5)   # brief pause between models

    if skipped:
        log.info(f"  Skipped {skipped} already-filled models (use --overwrite to refresh)")

    if updates and not dry_run:
        ws.spreadsheet.values_batch_update({
            "valueInputOption": "RAW",
            "data": updates,
        })
        log.info(f"  → {len(updates)} cells written")
    elif dry_run:
        log.info(f"  [dry-run] Would write {len(updates)} cells")

    return len(updates)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape SLR/VRPorn/POVR stats into Google Sheet")
    parser.add_argument("--tab",       help="Process only this tab name")
    parser.add_argument("--overwrite", action="store_true", help="Re-scrape even filled rows")
    parser.add_argument("--dry-run",   action="store_true", help="Scrape but don't write to sheet")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("Scrape Platform Stats  (SLR / VRPorn / POVR)")
    log.info("=" * 60)

    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc    = gspread.authorize(creds)
    ss    = gc.open_by_key(SPREADSHEET_ID)

    slr_cache   = load_slr_cache()
    total_cells = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx     = browser.new_context(user_agent=USER_AGENT)
        page    = ctx.new_page()

        SKIP_TABS = {"📋 Legend", "🔍 Search", "Export", "📊 Dashboard", "📱 Socials"}

        for ws in ss.worksheets():
            if args.tab and ws.title != args.tab:
                continue
            if ws.title in SKIP_TABS:
                log.info(f"\n[{ws.title}] — skipped (non-agency tab)")
                continue

            log.info(f"\n[{ws.title}]")
            try:
                n = process_tab(ws, page, slr_cache, args.overwrite, args.dry_run)
                total_cells += n
            except Exception as e:
                log.error(f"  [{ws.title}] ERROR: {e}")
                time.sleep(10)  # back off on error before continuing
                continue

            save_slr_cache(slr_cache)   # save after each tab in case of interrupt
            time.sleep(3)  # pause between tabs to avoid rate limits

        browser.close()

    log.info(f"\nDone. {total_cells} cells updated. SLR cache: {len(slr_cache)} performers.")


if __name__ == "__main__":
    main()
