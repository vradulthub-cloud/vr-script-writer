#!/usr/bin/env python3
"""
rediscover_slr_slugs.py
=======================
Targeted SLR slug re-discovery for models not in slr_cache.json.
Reads all agency tabs, finds names without a cache entry, runs
discover_slr_slug for each, then saves the updated cache.

Usage:
    python3 /Users/andrewninn/Scripts/rediscover_slr_slugs.py
"""

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

SPREADSHEET_ID       = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = Path(__file__).parent / "service_account.json"
SLR_CACHE_FILE       = Path(__file__).parent / "slr_cache.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW     = 3
DATA_START_ROW = 4

SKIP_TABS = {"📋 Legend", "🔍 Search", "Export", "📊 Dashboard", "📱 Socials"}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


def name_to_slug(name: str) -> str:
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name.strip())
    return name.strip("-")


def load_slr_cache() -> dict:
    if SLR_CACHE_FILE.exists():
        return json.loads(SLR_CACHE_FILE.read_text())
    return {}


def save_slr_cache(cache: dict):
    SLR_CACHE_FILE.write_text(json.dumps(cache, indent=2))


def fetch_page(page, url: str, wait_ms: int = 2000):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        time.sleep(wait_ms / 1000)
        return BeautifulSoup(page.content(), "html.parser")
    except Exception as e:
        log.debug(f"    fetch failed {url}: {e}")
        return BeautifulSoup("", "html.parser")


def discover_slr_slug(page, name: str, cache: dict) -> str | None:
    slug_base = name_to_slug(name)
    if slug_base in cache:
        return cache[slug_base]

    def _cache_and_return(val):
        cache[slug_base] = val
        return val

    # 1. Try direct URL
    try:
        direct_url = f"https://www.sexlikereal.com/pornstars/{slug_base}"
        page.goto(direct_url, wait_until="domcontentloaded", timeout=15_000)
        final_url = page.url
        m = re.search(r"/pornstars/([a-z0-9-]+-\d+)(?:[/?]|$)", final_url)
        if m:
            return _cache_and_return(m.group(1))
        soup = BeautifulSoup(page.content(), "html.parser")
        canon = soup.find("link", rel="canonical")
        if canon and canon.get("href"):
            m = re.search(r"/pornstars/([a-z0-9-]+-\d+)(?:[/?]|$)", canon["href"])
            if m:
                return _cache_and_return(m.group(1))
    except Exception:
        pass

    # 2. Search page
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
        log.debug(f"    search failed for {name}: {e}")
        return None

    all_links = [a["href"] for a in soup.find_all("a", href=True)
                 if "/pornstars/" in a["href"]]
    slug_links = []
    for href in all_links:
        m = re.search(r"/pornstars/([a-z0-9-]+-\d+)(?:[/?]|$)", href)
        if m:
            slug_links.append(m.group(1))

    # a. Exact match
    exact = re.compile(r"^" + re.escape(slug_base) + r"-\d+$")
    for candidate in slug_links:
        if exact.match(candidate):
            return _cache_and_return(candidate)

    # b. Prefix match
    for candidate in slug_links:
        name_part = re.sub(r"-\d+$", "", candidate)
        if name_part.startswith(slug_base):
            return _cache_and_return(candidate)

    # c. First + last name in slug
    parts = slug_base.split("-")
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        for candidate in slug_links:
            if first in candidate and last in candidate:
                return _cache_and_return(candidate)

    # No match — don't cache None so we can retry later
    return None


def get_missing_names(ss, cache: dict) -> list[tuple[str, str]]:
    """Returns list of (tab_title, model_name) for models not in SLR cache."""
    missing = []
    for ws in ss.worksheets():
        if ws.title in SKIP_TABS:
            continue
        headers = ws.row_values(HEADER_ROW)
        try:
            name_col = headers.index("Name")
        except ValueError:
            continue
        rows = ws.get_all_values()[DATA_START_ROW - 1:]
        for row in rows:
            if len(row) <= name_col:
                continue
            raw = row[name_col].strip()
            # Strip HYPERLINK formula if present
            m = re.search(r'HYPERLINK\("[^"]+","([^"]+)"\)', raw)
            name = m.group(1) if m else raw
            if not name:
                continue
            slug = name_to_slug(name)
            if slug not in cache:
                missing.append((ws.title, name))
    return missing


def main():
    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(SPREADSHEET_ID)

    cache = load_slr_cache()
    log.info(f"Cache loaded: {len(cache)} entries")

    missing = get_missing_names(ss, cache)
    # Deduplicate by name slug
    seen = set()
    unique_missing = []
    for tab, name in missing:
        slug = name_to_slug(name)
        if slug not in seen:
            seen.add(slug)
            unique_missing.append((tab, name))

    log.info(f"Models missing from SLR cache: {len(unique_missing)}")
    if not unique_missing:
        log.info("Nothing to do.")
        return

    found = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        for i, (tab, name) in enumerate(unique_missing, 1):
            log.info(f"  [{i}/{len(unique_missing)}] {name} ({tab})...")
            slug = discover_slr_slug(page, name, cache)
            if slug:
                log.info(f"    → {slug}")
                found += 1
            else:
                log.info(f"    → not found")

            # Save cache every 20 names
            if i % 20 == 0:
                save_slr_cache(cache)
                log.info(f"  [cache saved — {len(cache)} entries]")

        browser.close()

    save_slr_cache(cache)
    log.info(f"\nDone. Found {found}/{len(unique_missing)} new SLR slugs. Cache: {len(cache)} entries.")


if __name__ == "__main__":
    main()
