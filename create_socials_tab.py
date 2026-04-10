#!/usr/bin/env python3
"""
create_socials_tab.py
=====================
Creates (or refreshes) a "📱 Socials" tab in the Model Booking List.

The tab has one row per model (across all agency tabs) with columns:
  Name | Agency | SLR Link | OnlyFans | Twitter | Instagram

Social follower/subscriber counts are scraped via Playwright.
OnlyFans and Twitter counts feed into the compute_rank.py scoring.

Usage:
    python3 /Users/andrewninn/Scripts/create_socials_tab.py
    python3 /Users/andrewninn/Scripts/create_socials_tab.py --overwrite   # re-scrape all
    python3 /Users/andrewninn/Scripts/create_socials_tab.py --dry-run
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

SKIP_TABS  = ["📋 Legend", "🔍 Search", "Export", "📊 Dashboard", "📱 Socials"]
HEADER_ROW = 3
DATA_START = 4
TAB_NAME   = "📱 Socials"

# Socials tab column order
SOCIALS_HEADERS = ["Name", "Agency", "SLR Link", "OnlyFans", "Twitter", "Instagram"]

# Column widths (1-indexed)
COL_WIDTHS = {
    1: 195,   # Name
    2: 150,   # Agency
    3: 310,   # SLR Link
    4: 100,   # OnlyFans
    5: 100,   # Twitter
    6: 100,   # Instagram
}

NAVY  = {"red": 0.102, "green": 0.137, "blue": 0.494}
WHITE = {"red": 1, "green": 1, "blue": 1}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


# ── Name / slug utils ──────────────────────────────────────────────────────────

def name_to_slug(name: str) -> str:
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name.strip())
    return name.strip("-")


def normalize_stat(text: str) -> str:
    text = text.strip()
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*([KkMmBb]?)", text)
    if not m:
        return text
    num = m.group(1).replace(",", "")
    suffix = m.group(2).upper() if m.group(2) else ""
    return f"{num}{suffix}"


# ── Scrapers ───────────────────────────────────────────────────────────────────

def fetch_page(page, url: str, wait_ms: int = 2000) -> BeautifulSoup | None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        time.sleep(wait_ms / 1000)
        return BeautifulSoup(page.content(), "html.parser")
    except Exception as e:
        log.debug(f"    fetch_page failed {url}: {e}")
        return None


def scrape_onlyfans(page, name: str) -> str:
    """Return OnlyFans subscriber count string, or ''."""
    slug    = name_to_slug(name)
    compact = slug.replace("-", "")
    first   = slug.split("-")[0]
    candidates = [slug, compact, first + "xxx", first + "xx", compact + "xxx"]

    for handle in candidates:
        url = f"https://onlyfans.com/{handle}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            time.sleep(1.5)
            soup = BeautifulSoup(page.content(), "html.parser")
            if page.url.endswith("/404") or "not found" in soup.get_text().lower()[:200]:
                continue
            text = soup.get_text(" ", strip=True)
            m = re.search(r"([\d,.]+[KkMm]?)\s*(?:fans|subscribers?)", text, re.IGNORECASE)
            if m:
                return normalize_stat(m.group(1))
        except Exception:
            continue
    return ""


def scrape_twitter(page, name: str) -> str:
    """Return Twitter/X follower count string, or ''."""
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
            if "This account doesn" in text or "doesn't exist" in text:
                continue
            m = re.search(r"([\d,.]+[KkMm]?)\s*followers?", text, re.IGNORECASE)
            if m:
                return normalize_stat(m.group(1))
        except Exception:
            continue
    return ""


def scrape_instagram(page, name: str) -> str:
    """Return Instagram follower count string, or ''."""
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
            meta = soup.find("meta", {"name": "description"}) or \
                   soup.find("meta", {"property": "og:description"})
            if meta:
                content = meta.get("content", "")
                m = re.search(r"([\d,.]+[KkMm]?)\s*(?:Followers|followers)", content)
                if m:
                    return normalize_stat(m.group(1))
        except Exception:
            continue
    return ""


# ── Sheet formatting helpers ───────────────────────────────────────────────────

def fmt(bg, fg, bold=False, size=9, wrap="WRAP", valign="MIDDLE", halign="LEFT"):
    return {
        "backgroundColor": bg,
        "textFormat": {"foregroundColor": fg, "bold": bold, "fontSize": size},
        "wrapStrategy": wrap,
        "verticalAlignment": valign,
        "horizontalAlignment": halign,
    }


def repeat_cell(sheet_id, row, col_start, col_end, cell_fmt):
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row,
                "endRowIndex": row + 1,
                "startColumnIndex": col_start,
                "endColumnIndex": col_end,
            },
            "cell": {"userEnteredFormat": cell_fmt},
            "fields": "userEnteredFormat",
        }
    }


def col_width_req(sheet_id, col_idx, px):
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": col_idx,
                "endIndex": col_idx + 1,
            },
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    }


# ── Build / refresh the socials tab ───────────────────────────────────────────

def collect_models(ss) -> list[dict]:
    """
    Walk all agency tabs and collect {name, agency, slr_link} for every model.
    Strips =HYPERLINK(...) from Name cells to get display name.
    """
    slr_cache: dict = {}
    if SLR_CACHE_FILE.exists():
        slr_cache = json.loads(SLR_CACHE_FILE.read_text())

    models = []
    seen   = set()

    for ws in ss.worksheets():
        if ws.title in SKIP_TABS:
            continue
        all_rows = ws.get_all_values()
        if len(all_rows) < HEADER_ROW:
            continue
        headers  = [h.strip() for h in all_rows[HEADER_ROW - 1]]
        col_map  = {h: i for i, h in enumerate(headers) if h}
        name_col = col_map.get("Name", 0)

        for row in all_rows[DATA_START - 1:]:
            if len(row) <= name_col:
                continue
            raw = row[name_col].strip()
            if not raw:
                continue
            # Strip HYPERLINK formula
            m = re.search(r'=HYPERLINK\("[^"]*",\s*"([^"]+)"\)', raw)
            name = m.group(1) if m else raw

            key = (name.lower(), ws.title)
            if key in seen:
                continue
            seen.add(key)

            slug     = name_to_slug(name)
            slr_slug = slr_cache.get(slug, "")
            slr_link = f"https://www.sexlikereal.com/pornstars/{slr_slug}" if slr_slug else ""

            models.append({
                "name":     name,
                "agency":   ws.title,
                "slr_link": slr_link,
            })

    models.sort(key=lambda x: x["name"].lower())
    log.info(f"Collected {len(models)} unique models across all agency tabs")
    return models


def setup_tab(ss) -> gspread.Worksheet:
    """Create the Socials tab if it doesn't exist, or clear data rows."""
    try:
        ws = ss.worksheet(TAB_NAME)
        # Clear everything below header rows
        last = max(ws.row_count, 10)
        ws.batch_clear([f"A1:Z{last}"])
        log.info(f"Cleared existing {TAB_NAME} tab")
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=TAB_NAME, rows=500, cols=len(SOCIALS_HEADERS))
        log.info(f"Created new {TAB_NAME} tab")
    return ws


def apply_formatting(ss, ws, num_rows: int):
    sheet_id = ws.id
    reqs = []

    # Title row (row 1): navy, white, bold
    reqs.append(repeat_cell(sheet_id, 0, 0, len(SOCIALS_HEADERS),
        fmt(NAVY, WHITE, bold=True, size=11, wrap="CLIP", halign="CENTER")))

    # Header row (row 2): slightly lighter navy
    LIGHT_NAVY = {"red": 0.173, "green": 0.243, "blue": 0.514}
    reqs.append(repeat_cell(sheet_id, 1, 0, len(SOCIALS_HEADERS),
        fmt(LIGHT_NAVY, WHITE, bold=True, size=9, wrap="CLIP")))

    # Data rows: alternating white / light grey
    LIGHT_GREY = {"red": 0.953, "green": 0.957, "blue": 0.965}
    for r in range(num_rows):
        bg = {"red": 1, "green": 1, "blue": 1} if r % 2 == 0 else LIGHT_GREY
        reqs.append(repeat_cell(sheet_id, 2 + r, 0, len(SOCIALS_HEADERS),
            fmt(bg, {"red": 0, "green": 0, "blue": 0}, size=9, wrap="CLIP")))

    # Column widths
    for col_1idx, px in COL_WIDTHS.items():
        reqs.append(col_width_req(sheet_id, col_1idx - 1, px))

    # Freeze rows 1-2
    reqs.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": 2},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    })

    ss.batch_update({"requests": reqs})


def write_tab(ws, models: list[dict], scraped: dict, dry_run: bool):
    """Write title, headers, and all data rows to the Socials tab."""
    rows = [
        ["📱 Social Media", "", "", "", "", ""],
        SOCIALS_HEADERS,
    ]
    for m in models:
        name = m["name"]
        slr  = m["slr_link"]
        name_cell = f'=HYPERLINK("{slr}","{name}")' if slr else name
        soc  = scraped.get(name.lower(), {})
        rows.append([
            name_cell,
            m["agency"],
            slr,
            soc.get("of", ""),
            soc.get("tw", ""),
            soc.get("ig", ""),
        ])

    if dry_run:
        log.info(f"[dry-run] Would write {len(rows)} rows to {TAB_NAME}")
        return

    ws.update(rows, value_input_option="USER_ENTERED")
    log.info(f"Wrote {len(rows)} rows to {TAB_NAME}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build/refresh the 📱 Socials tab")
    parser.add_argument("--overwrite", action="store_true",
                        help="Re-scrape social stats for all models")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Scrape but don't write to sheet")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("Create / Refresh  📱 Socials Tab")
    log.info("=" * 60)

    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc    = gspread.authorize(creds)
    ss    = gc.open_by_key(SPREADSHEET_ID)

    models = collect_models(ss)

    # Existing scraped data (skip re-scraping unless --overwrite)
    existing: dict = {}
    if not args.overwrite:
        try:
            ws_existing = ss.worksheet(TAB_NAME)
            existing_rows = ws_existing.get_all_values()
            for row in existing_rows[2:]:   # skip title + header
                if len(row) >= 6 and row[0]:
                    # Strip HYPERLINK to get name
                    raw = row[0].strip()
                    m   = re.search(r'=HYPERLINK\("[^"]*",\s*"([^"]+)"\)', raw)
                    name_key = (m.group(1) if m else raw).lower()
                    existing[name_key] = {
                        "of": row[3] if len(row) > 3 else "",
                        "tw": row[4] if len(row) > 4 else "",
                        "ig": row[5] if len(row) > 5 else "",
                    }
            log.info(f"Loaded {len(existing)} existing social records (use --overwrite to re-scrape)")
        except gspread.WorksheetNotFound:
            pass

    # Determine which models need scraping
    to_scrape = [
        m for m in models
        if args.overwrite or not any(existing.get(m["name"].lower(), {}).values())
    ]
    log.info(f"{len(to_scrape)} models to scrape  ({len(models) - len(to_scrape)} already have data)")

    scraped = dict(existing)   # start with existing, overwrite with fresh

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx     = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = ctx.new_page()

        for i, m in enumerate(to_scrape, 1):
            name = m["name"]
            log.info(f"  [{i}/{len(to_scrape)}] {name}...")

            of = scrape_onlyfans(page, name)
            tw = scrape_twitter(page, name)
            ig = scrape_instagram(page, name)

            scraped[name.lower()] = {"of": of, "tw": tw, "ig": ig}
            found = [k for k, v in {"OF": of, "TW": tw, "IG": ig}.items() if v]
            log.info(f"    {', '.join(found) or 'nothing found'}"
                     + (f"  OF={of}" if of else "")
                     + (f"  TW={tw}" if tw else "")
                     + (f"  IG={ig}" if ig else ""))

            time.sleep(0.5)

        browser.close()

    # Write to sheet
    ws = setup_tab(ss)
    write_tab(ws, models, scraped, args.dry_run)

    if not args.dry_run:
        apply_formatting(ss, ws, len(models))
        log.info("Formatting applied")

    log.info("")
    log.info("=" * 60)
    log.info(f"Done. {TAB_NAME} tab ready.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
