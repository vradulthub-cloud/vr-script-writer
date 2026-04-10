#!/usr/bin/env python3
"""
Weekly Model Booking List – Roster Updater (flag-not-delete version)
====================================================================
For each agency tab:
  - Scrapes the agency website for current models
  - Adds new models at the bottom (name only; other fields left blank)
  - Flags removed models with a note in the Notes column:
    "[No longer listed on agency site as of YYYY-MM-DD]"
  - Never deletes rows or modifies existing data (except appending removal notes)

Usage:
    python3 weekly_roster_update.py [--dry-run] [--tab "Agency Name"]
"""

import argparse
import logging
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, urljoin

import gspread
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# ── Configuration ─────────────────────────────────────────────────────────────
SPREADSHEET_ID  = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SA_CREDENTIALS  = Path("/Users/andrewninn/Scripts/service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

TODAY = date.today().strftime("%Y-%m-%d")
REMOVAL_NOTE = f"[No longer listed on agency site as of {TODAY}]"

# Sheet layout (1-based column indices)
WEBSITE_ROW    = 2
HEADER_ROW     = 3
DATA_START_ROW = 4
COL_NAME   = 1  # A
COL_NOTES  = 7  # G  (v7 layout after --add-shoots-col)

# Safety: if scraper finds < 65% of sheet models, skip removals
MIN_CONFIDENCE = 0.65

# URL overrides for sites that redirect or have a separate roster page
SITE_URL_OVERRIDES = {
    "https://www.foxxxmodeling.com":  "https://wp-quri045785.pairsite.com/models/",
    "http://www.foxxxmodeling.com":   "https://wp-quri045785.pairsite.com/models/",
    "https://foxxxmodeling.com":      "https://wp-quri045785.pairsite.com/models/",
    "http://foxxxmodeling.com":       "https://wp-quri045785.pairsite.com/models/",
}

# ── Name filter constants ─────────────────────────────────────────────────────
NAV_BLACKLIST = {
    "apply", "blog", "back to models", "our models", "all performers",
    "female performers", "male performers", "new performers",
    "east coast", "west coast", "los angeles", "las vegas", "arizona",
    "florida", "testimonials", "press", "faq", "performer application",
    "services", "choose your", "accessibility menu", "quick link",
    "home", "about", "contact", "models", "talent", "sign up", "login",
    "log in", "join now", "submit", "search", "view all", "see more",
    "load more", "read more", "click here", "invision models",
    "hussie models", "the bakery talent", "nexxxt level", "speigler",
    "foxxx modeling", "zen models", "atmla", "coxxx models",
    "east coast talent", "the model service", "oc models", "101 models",
    "male talent", "female talent", "all talent", "back", "next", "previous",
    "sort by", "filter", "featured", "new", "exclusive",
    "talent booking", "need an agent", "booking info",
    "google translate",
}
FUNCTION_WORDS = {
    "booking", "book", "bookings", "career", "careers",
    "location", "locations", "agency", "agencies", "studio", "studios",
    "homepage", "site", "sites", "page", "pages", "agent", "agents",
    "register", "apply", "join", "sign", "submit", "click",
    "need", "your", "our", "lets", "about", "home", "menu", "main",
    "contact", "info", "information", "press", "news", "gallery",
    "video", "videos", "photo", "photos", "rates", "pricing", "rate",
    "schedule", "calendar", "event", "events", "service", "services",
    "support", "filter", "filters", "sort",
}
MID_WORD_REJECT = {
    "an", "the", "a", "of", "in", "at", "for", "and", "or", "to",
    "by", "on", "with", "from", "into", "your", "our", "its",
}
SLUG_REJECT_PARTS = {
    "page", "models", "talent", "about", "contact", "blog",
    "home", "index", "apply", "join", "gallery", "news", "roster",
    "performers", "girls", "women", "female", "male", "all",
    "new", "featured", "exclusive", "booking",
}

# ── Logging ───────────────────────────────────────────────────────────────────
Path("/Users/andrewninn/Scripts/logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"/Users/andrewninn/Scripts/logs/weekly_update_{TODAY}.log"),
    ]
)
log = logging.getLogger(__name__)


# ── Auth ──────────────────────────────────────────────────────────────────────
def get_client():
    creds = Credentials.from_service_account_file(str(SA_CREDENTIALS), scopes=SCOPES)
    return gspread.authorize(creds)


def _retry_api(func, max_retries=4, base_sleep=12):
    for attempt in range(max_retries):
        try:
            return func()
        except gspread.exceptions.APIError as exc:
            if "429" in str(exc) and attempt < max_retries - 1:
                wait = base_sleep * (2 ** attempt)
                log.warning(f"Rate limited (429) – waiting {wait}s …")
                time.sleep(wait)
            else:
                raise


# ── Sheet helpers ─────────────────────────────────────────────────────────────
def get_website_url(ws) -> str:
    try:
        row2 = ws.row_values(WEBSITE_ROW)
        for cell in row2:
            val = (cell or "").strip()
            if val.startswith(("http://", "https://", "www.")):
                return val
    except Exception:
        pass
    return ""


def get_sheet_models(ws) -> list:
    all_values = ws.get_all_values()
    models = []
    for row_idx, row in enumerate(all_values, start=1):
        if row_idx < DATA_START_ROW:
            continue
        name = row[COL_NAME - 1].strip() if len(row) >= COL_NAME else ""
        if not name:
            continue
        notes = row[COL_NOTES - 1].strip() if len(row) >= COL_NOTES else ""
        models.append({"name": name, "row": row_idx, "notes": notes})
    return models


# ── Scraping helpers ──────────────────────────────────────────────────────────
def _make_absolute_url(href: str, base_url: str) -> str:
    if not href:
        return ""
    href = href.strip()
    if href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return ""
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("//"):
        scheme = urlparse(base_url).scheme or "https"
        return f"{scheme}:{href}"
    return urljoin(base_url, href)


def _clean_text(text: str) -> str:
    return re.sub(r"[\s\u200b\u00a0]+", " ", text).strip()


def _autocorrect_allcaps(text: str) -> str:
    s = text.strip()
    if s and s == s.upper() and re.match(r"^[A-Za-z\s]+$", s):
        return s.title()
    return s


def _slug_to_name(slug: str) -> str:
    parts = [p for p in slug.split("-") if p]
    if len(parts) < 2 or len(parts) > 4:
        return ""
    if not all(re.match(r"^[a-zA-Z]+$", p) for p in parts):
        return ""
    if any(p.lower() in SLUG_REJECT_PARTS for p in parts):
        return ""
    return " ".join(p.title() for p in parts)


def _looks_like_name(text: str) -> bool:
    text = text.strip()
    if not text or len(text) > 50 or len(text) < 4:
        return False
    if not re.match(r"^[A-Za-z][A-Za-z\s'\-\.]+$", text):
        return False
    words = text.split()
    if len(words) < 2 or len(words) > 4:
        return False
    if text == text.upper():
        return False
    if text.lower().strip() in NAV_BLACKLIST:
        return False
    for w in words:
        if w.lower() in FUNCTION_WORDS:
            return False
    for w in words[1:]:
        if w.lower() in MID_WORD_REJECT:
            return False
    for w in words:
        if not w or not w[0].isupper():
            return False
        if "-" in w:
            parts = [p for p in w.split("-") if p]
            if not all(p[0].isupper() for p in parts):
                return False
    return True


def _dedupe(models):
    seen = set()
    out = []
    for item in models:
        name = item[0] if isinstance(item, tuple) else item
        key = name.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _scroll_and_load(page, scrolls=5, sleep_per_scroll=1.5):
    for _ in range(scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(sleep_per_scroll)
    load_more_selectors = [
        "button:has-text('Load More')", "button:has-text('Show More')",
        "a:has-text('Load More')", "[class*='load-more']:visible",
        "[class*='loadmore']:visible",
    ]
    for _ in range(6):
        clicked = False
        for sel in load_more_selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    time.sleep(2.5)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1.5)
                    clicked = True
                    break
            except Exception:
                pass
        if not clicked:
            break


def _find_next_pages(soup, base_url: str, max_extra=5):
    base_domain = urlparse(base_url).netloc
    found = set()
    for a in soup.find_all("a", href=True):
        abs_href = _make_absolute_url(a["href"], base_url)
        if not abs_href or abs_href.rstrip("/") == base_url.rstrip("/"):
            continue
        if urlparse(abs_href).netloc != base_domain:
            continue
        if (re.search(r"/page/[2-9]\d*/?$", abs_href, re.I) or
                re.search(r"[?&]paged?=([2-9]|[1-9]\d+)", abs_href, re.I)):
            found.add(abs_href)
    return sorted(found)[:max_extra]


def _extract_models_from_soup(soup, url: str):
    candidate_selectors = [
        ".model-name", ".model_name", ".talent-name", ".talent_name",
        ".performer-name", ".performer_name", ".girl-name", ".girl_name",
        "[class*='model'][class*='name']", "[class*='talent'][class*='name']",
        "figcaption", ".name",
        ".elementor-post h2", ".elementor-post__title a",
        "h3", "h4",
    ]
    for sel in candidate_selectors:
        found = soup.select(sel)
        if len(found) >= 3:
            candidates = []
            for t in found:
                raw = _clean_text(t.get_text(separator=" ", strip=True))
                raw = _autocorrect_allcaps(raw)
                if _looks_like_name(raw):
                    profile_url = ""
                    ancestor = t.find_parent("a", href=True)
                    if ancestor:
                        profile_url = _make_absolute_url(ancestor["href"], url)
                    candidates.append((raw, profile_url))
            if len(candidates) >= 3:
                return _dedupe(candidates)

    roster_keywords = ("/talent", "/model", "/girls", "/performers",
                       "/female", "/women", "/roster")
    if any(kw in url.lower() for kw in roster_keywords):
        links = soup.find_all("a", href=True)
        names = []
        for link in links:
            text = _clean_text(link.get_text(separator=" ", strip=True))
            if _looks_like_name(text):
                profile_url = _make_absolute_url(link["href"], url)
                names.append((text, profile_url))
        if len(names) >= 3:
            return _dedupe(names)

    names = []
    for img in soup.find_all("img", alt=True):
        alt = _clean_text(img["alt"])
        alt = _autocorrect_allcaps(alt)
        if _looks_like_name(alt):
            profile_url = ""
            parent_a = img.find_parent("a", href=True)
            if parent_a:
                profile_url = _make_absolute_url(parent_a["href"], url)
            names.append((alt, profile_url))
    if len(names) >= 3:
        return _dedupe(names)

    try:
        base_domain = urlparse(url).netloc
        all_links = soup.find_all("a", href=True)
        total = len(all_links)
        empty_count = sum(1 for lnk in all_links if not lnk.get_text(strip=True))
        if total >= 5 and empty_count >= total * 0.35:
            slug_names = []
            for link in all_links:
                href = link.get("href", "")
                abs_href = _make_absolute_url(href, url)
                if not abs_href:
                    continue
                try:
                    parsed = urlparse(abs_href)
                except Exception:
                    continue
                if parsed.netloc and parsed.netloc != base_domain:
                    continue
                slug = [s for s in parsed.path.split("/") if s]
                if not slug:
                    continue
                name = _slug_to_name(slug[-1])
                if name and _looks_like_name(name):
                    slug_names.append((name, abs_href))
            if len(slug_names) >= 3:
                log.info("    (Strategy 4 – URL slugs)")
                return _dedupe(slug_names)
    except Exception:
        pass

    try:
        aria_names = []
        for el in soup.find_all(attrs={"aria-label": True}):
            raw = el.get("aria-label", "")
            cleaned = _autocorrect_allcaps(_clean_text(raw))
            if _looks_like_name(cleaned):
                profile_url = ""
                parent_a = el.find_parent("a", href=True) or el.find("a", href=True)
                if parent_a:
                    profile_url = _make_absolute_url(parent_a["href"], url)
                aria_names.append((cleaned, profile_url))
        if len(aria_names) >= 3:
            log.info("    (Strategy 5 – aria-labels)")
            return _dedupe(aria_names)
    except Exception:
        pass

    try:
        names = []
        for link in soup.find_all("a", href=True):
            text = _clean_text(link.get_text(separator=" ", strip=True))
            if _looks_like_name(text):
                profile_url = _make_absolute_url(link["href"], url)
                names.append((text, profile_url))
        if len(names) >= 5:
            log.info("    (Strategy 6 – general link text)")
            return _dedupe(names)
    except Exception:
        pass

    return []


def scrape_agency_roster(url: str, agency_name: str):
    if not url:
        log.warning(f"  [{agency_name}] No website URL – skipping")
        return []

    normalized = url.rstrip("/")
    if normalized in SITE_URL_OVERRIDES:
        override = SITE_URL_OVERRIDES[normalized]
        log.info(f"  [{agency_name}] URL override → {override}")
        url = override

    log.info(f"  [{agency_name}] Scraping: {url}")
    all_models = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=USER_AGENT)
            pw_page = ctx.new_page()
            urls_to_visit = [url]
            visited = set()

            for page_url in urls_to_visit:
                if page_url in visited:
                    continue
                visited.add(page_url)
                try:
                    pw_page.goto(page_url, wait_until="domcontentloaded", timeout=45_000)
                except Exception:
                    try:
                        pw_page.goto(page_url, wait_until="commit", timeout=60_000)
                    except Exception as e:
                        log.warning(f"  [{agency_name}] Could not load {page_url}: {e}")
                        continue

                time.sleep(3)
                _scroll_and_load(pw_page)
                html = pw_page.content()
                soup = BeautifulSoup(html, "html.parser")
                page_models = _extract_models_from_soup(soup, page_url)
                all_models.extend(page_models)
                log.info(f"  [{agency_name}] Page {len(visited)}: {len(page_models)} models found")

                if len(visited) == 1:
                    next_pages = _find_next_pages(soup, page_url)
                    if next_pages:
                        log.info(f"  [{agency_name}] Found {len(next_pages)} extra page(s)")
                    for np in next_pages:
                        if np not in visited:
                            urls_to_visit.append(np)

                time.sleep(1)

            browser.close()
        all_models = _dedupe(all_models)
    except Exception as e:
        log.error(f"  [{agency_name}] Scrape failed: {e}")

    names = [m[0] if isinstance(m, tuple) else m for m in all_models]
    log.info(f"  [{agency_name}] Total online: {len(names)}")
    return names


# ── Core update logic ─────────────────────────────────────────────────────────
def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def process_tab(ws, dry_run: bool) -> dict:
    tab_name = ws.title
    result = {"tab": tab_name, "added": 0, "flagged": 0, "skipped": False, "reason": ""}

    url = get_website_url(ws)
    if not url:
        log.info(f"  [{tab_name}] No website URL in row 2 – skipping")
        result["skipped"] = True
        result["reason"] = "No website URL"
        return result

    sheet_models = get_sheet_models(ws)
    log.info(f"  [{tab_name}] Sheet has {len(sheet_models)} model(s)")

    online_names = scrape_agency_roster(url, tab_name)
    if not online_names:
        log.warning(f"  [{tab_name}] No models found online – skipping to avoid data loss")
        result["skipped"] = True
        result["reason"] = "No models scraped from site"
        return result

    sheet_norm  = {normalize_name(m["name"]): m for m in sheet_models}
    online_norm = {normalize_name(n): n for n in online_names}

    # New models (on site, not in sheet)
    to_add = [online_norm[k] for k in online_norm if k not in sheet_norm]

    # Removed models (in sheet, not on site) — apply confidence gate
    confidence = len(online_names) / max(len(sheet_models), 1)
    if confidence < MIN_CONFIDENCE:
        log.warning(
            f"  [{tab_name}] Confidence {confidence:.0%} < {MIN_CONFIDENCE:.0%} "
            f"({len(online_names)} online vs {len(sheet_models)} in sheet) – "
            f"skipping removal flags"
        )
        to_flag = []
    else:
        to_flag = [
            sheet_norm[k] for k in sheet_norm
            if k not in online_norm and REMOVAL_NOTE not in sheet_norm[k]["notes"]
        ]

    log.info(f"  [{tab_name}] → +{len(to_add)} to add, {len(to_flag)} to flag as removed")

    if not dry_run:
        if to_add:
            rows_data = [[name] for name in to_add]
            _retry_api(lambda: ws.append_rows(
                rows_data,
                value_input_option="USER_ENTERED",
                table_range=f"A{DATA_START_ROW}",
            ))
            log.info(f"  [{tab_name}] Added {len(to_add)}: {to_add}")
            time.sleep(2)

        if to_flag:
            updates = []
            for model in to_flag:
                existing = model["notes"]
                new_note = (existing + " " + REMOVAL_NOTE).strip() if existing else REMOVAL_NOTE
                updates.append({"range": f"G{model['row']}", "values": [[new_note]]})
            CHUNK = 50
            for i in range(0, len(updates), CHUNK):
                _retry_api(lambda chunk=updates[i:i+CHUNK]: ws.batch_update(chunk))
                if i + CHUNK < len(updates):
                    time.sleep(1)
            log.info(f"  [{tab_name}] Flagged {len(to_flag)}: {[m['name'] for m in to_flag]}")
            time.sleep(1)
    else:
        if to_add:
            log.info(f"  [{tab_name}] [DRY RUN] Would add: {to_add}")
        if to_flag:
            log.info(f"  [{tab_name}] [DRY RUN] Would flag: {[m['name'] for m in to_flag]}")

    result["added"]   = len(to_add)
    result["flagged"] = len(to_flag)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Weekly roster update (flag-not-delete)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--tab", default=None, help="Process only this tab name")
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "LIVE"
    log.info(f"Weekly roster update starting – mode: {mode} – date: {TODAY}")

    gc = get_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheets = sh.worksheets()
    log.info(f"Found {len(worksheets)} worksheets")

    results = []
    for ws in worksheets:
        if args.tab and ws.title != args.tab:
            continue
        log.info(f"\n{'='*60}")
        log.info(f"Processing: {ws.title}")
        result = process_tab(ws, dry_run=args.dry_run)
        results.append(result)
        time.sleep(2)

    log.info(f"\n{'='*60}")
    log.info("WEEKLY UPDATE SUMMARY")
    log.info(f"{'='*60}")
    total_added   = 0
    total_flagged = 0
    for r in results:
        if r["skipped"]:
            log.info(f"  {r['tab']:30s}  SKIPPED ({r['reason']})")
        else:
            log.info(f"  {r['tab']:30s}  +{r['added']} added, {r['flagged']} flagged removed")
            total_added   += r["added"]
            total_flagged += r["flagged"]
    log.info(f"{'='*60}")
    log.info(f"  TOTAL: +{total_added} new models added, {total_flagged} flagged as removed")

    return results


if __name__ == "__main__":
    main()
