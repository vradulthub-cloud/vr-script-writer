#!/usr/bin/env python3
"""
Model Booking List – Autonomous Roster Updater  (v7)
=====================================================
Reads each agency tab from the Google Sheet, visits the agency's website,
compares the online roster, and adds/removes models.

With --profiles it also visits individual model profile pages to extract
age and shoot-type categories — much faster and more accurate than the
previous DuckDuckGo approach.

SETUP (run once after upgrading to v7):
    python update_roster.py --add-shoots-col          # inserts Shoot Types col
    python update_roster.py --add-shoots-col --dry-run  # preview first

DAILY USAGE:
    python update_roster.py --dry-run           # preview roster changes
    python update_roster.py                     # apply roster changes
    python update_roster.py --profiles          # roster + fill age & shoot types
    python update_roster.py --tab "ATMLA"       # single tab only
    python update_roster.py --tab "ATMLA" --profiles  # single tab + profiles

Column layout (after running --add-shoots-col):
    A  Name | B  Age | C  AVG Rate | D  Rank | E  Location
    F  Shoot Types (NEW) | G  Notes  (was F before v7)

Requirements:
    pip3 install gspread google-auth playwright beautifulsoup4
    python3 -m playwright install chromium
"""

import argparse
import logging
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, urljoin

import gspread
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright


def _rc_to_a1(row: int, col: int) -> str:
    """Convert 1-based (row, col) to A1 notation, e.g. (1,1) → 'A1'."""
    col_letter = ""
    c = col
    while c:
        c, rem = divmod(c - 1, 26)
        col_letter = chr(65 + rem) + col_letter
    return f"{col_letter}{row}"


def _retry_api(func, max_retries: int = 4, base_sleep: int = 12):
    """
    Call func() and retry up to max_retries times on Google Sheets 429
    (quota-exceeded) errors, using exponential back-off.
    """
    for attempt in range(max_retries):
        try:
            return func()
        except gspread.exceptions.APIError as exc:
            if "429" in str(exc) and attempt < max_retries - 1:
                wait = base_sleep * (2 ** attempt)   # 12, 24, 48 s …
                log.warning(
                    f"Rate limited (429) – waiting {wait}s "
                    f"before retry {attempt + 1}/{max_retries - 1}…"
                )
                time.sleep(wait)
            else:
                raise

# ─── Configuration ────────────────────────────────────────────────────────────
SPREADSHEET_ID = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SA_CREDENTIALS = Path(__file__).parent / "service_account.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Sheet layout constants (1-based column indices)
WEBSITE_ROW    = 2   # Row containing the agency website URL
HEADER_ROW     = 3   # Column header labels
DATA_START_ROW = 4   # Model data starts here

# ── Fallback column indices (used only if header lookup fails) ────────────────
# These are intentionally NOT used directly — call _col(col_map, header, fallback)
# so that the script survives any column insertions/reorders automatically.
COL_NAME     = 1   # A – Model name
COL_AGE      = 4   # D – Age       (after SLR Profile + VRP Profile at B/C)
COL_RATE     = 5   # E – AVG Rate
COL_RANK     = 6   # F – Rank
COL_LOCATION = 7   # G – Location
COL_SHOOTS   = 8   # H – Available For / Shoot Types
COL_NOTES    = 9   # I – Notes

# Safety: only remove a model if the scraper found at least this fraction
# of the current sheet roster. Prevents mass-deletes on paginated sites.
MIN_SCRAPE_CONFIDENCE = 0.65

# Maximum profile pages to scrape per agency in one --profiles run.
# Increase if you want fuller coverage (each page ~2-3 seconds).
MAX_PROFILES_PER_AGENCY = 40

# ─── Site-specific URL overrides ─────────────────────────────────────────────
# Some agency sheets point to the homepage, not the actual roster page.
SITE_URL_OVERRIDES = {
    "https://www.foxxxmodeling.com": "https://wp-quri045785.pairsite.com/models/",
    "http://www.foxxxmodeling.com":  "https://wp-quri045785.pairsite.com/models/",
    "https://foxxxmodeling.com":     "https://wp-quri045785.pairsite.com/models/",
    "http://foxxxmodeling.com":      "https://wp-quri045785.pairsite.com/models/",
}

# ─── Name filtering constants ─────────────────────────────────────────────────

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
    "booking", "book", "bookings",
    "career", "careers",
    "location", "locations",
    "agency", "agencies",
    "studio", "studios",
    "homepage", "site", "sites", "page", "pages",
    "agent", "agents",
    "register", "apply", "join", "sign", "submit", "click",
    "need", "your", "our", "lets",
    "about", "home", "menu", "main",
    "contact", "info", "information",
    "press", "news", "gallery", "video", "videos", "photo", "photos",
    "rates", "pricing", "rate",
    "schedule", "calendar", "event", "events",
    "service", "services", "support",
    "filter", "filters", "sort",
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

# Known adult content categories used in shoot-type keyword scan (last resort)
SHOOT_KEYWORDS = {
    "anal", "dp", "double penetration", "gangbang", "gang bang",
    "bdsm", "fetish", "squirt", "lesbian", "solo", "boy girl",
    "girl girl", "creampie", "facial", "swallow", "pov",
    "interracial", "blowjob", "oral", "hardcore", "softcore",
    "bondage", "domination", "submission", "threesome",
    "outdoor", "teen", "milf", "massage",
    "lingerie", "nude", "stripping", "topless",
    "cum swap", "atm", "dap",
}

# Canonical shoot-type names, keyed by every known alias (lowercased).
# Any raw text extracted from a profile page is split into tokens and each
# token is looked up here, producing consistent labels in the sheet.
SHOOT_CANONICAL: dict[str, str] = {
    # ── Boy/Girl ──────────────────────────────────────────────
    "bg": "Boy/Girl", "b/g": "Boy/Girl", "boy girl": "Boy/Girl",
    "boy/girl": "Boy/Girl", "het": "Boy/Girl", "hetero": "Boy/Girl",
    "straight": "Boy/Girl", "mf": "Boy/Girl", "m/f": "Boy/Girl",
    "male female": "Boy/Girl",
    # ── Girl/Girl ─────────────────────────────────────────────
    "gg": "Girl/Girl", "g/g": "Girl/Girl", "girl girl": "Girl/Girl",
    "girl/girl": "Girl/Girl", "girl on girl": "Girl/Girl",
    "ff": "Girl/Girl", "f/f": "Girl/Girl",
    # ── Lesbian ───────────────────────────────────────────────
    "lesbian": "Lesbian", "les": "Lesbian",
    # ── Anal ──────────────────────────────────────────────────
    "anal": "Anal", "anal sex": "Anal",
    # ── DP ────────────────────────────────────────────────────
    "dp": "DP", "double penetration": "DP", "double pen": "DP", "dpp": "DP",
    # ── DAP ───────────────────────────────────────────────────
    "dap": "DAP", "double anal": "DAP", "double anal penetration": "DAP",
    # ── DVP ───────────────────────────────────────────────────
    "dvp": "DVP", "double vag": "DVP", "double vaginal": "DVP", "dv": "DVP",
    # ── Gangbang ──────────────────────────────────────────────
    "gangbang": "Gangbang", "gang bang": "Gangbang", "gb": "Gangbang",
    # ── Threesome ─────────────────────────────────────────────
    "threesome": "Threesome", "3some": "Threesome", "3way": "Threesome",
    "3-way": "Threesome", "three way": "Threesome", "trio": "Threesome",
    # ── MFM / FFM ─────────────────────────────────────────────
    "mfm": "MFM", "ffm": "FFM",
    # ── Oral ──────────────────────────────────────────────────
    "oral": "Oral", "bj": "Oral", "blowjob": "Oral", "blow job": "Oral",
    "fellatio": "Oral",
    # ── Creampie ──────────────────────────────────────────────
    "creampie": "Creampie", "cream pie": "Creampie", "cip": "Creampie",
    "internal": "Creampie", "internal cumshot": "Creampie",
    # ── Facial ────────────────────────────────────────────────
    "facial": "Facial",
    # ── Swallow ───────────────────────────────────────────────
    "swallow": "Swallow", "swallowing": "Swallow",
    "cim": "Swallow", "cum in mouth": "Swallow",
    # ── Squirting ─────────────────────────────────────────────
    "squirt": "Squirting", "squirting": "Squirting",
    "female ejaculation": "Squirting",
    # ── ATM ───────────────────────────────────────────────────
    "atm": "ATM", "ass to mouth": "ATM", "a2m": "ATM",
    # ── Cum Swap ──────────────────────────────────────────────
    "cum swap": "Cum Swap", "cumswap": "Cum Swap", "snowball": "Cum Swap",
    # ── Solo ──────────────────────────────────────────────────
    "solo": "Solo", "masturbation": "Solo", "solo girl": "Solo",
    "masturbate": "Solo",
    # ── Interracial ───────────────────────────────────────────
    "interracial": "Interracial", "ir": "Interracial",
    # ── BDSM ──────────────────────────────────────────────────
    "bdsm": "BDSM", "bondage domination": "BDSM",
    # ── Bondage ───────────────────────────────────────────────
    "bondage": "Bondage",
    # ── Domination / Submission ───────────────────────────────
    "domination": "Domination", "dom": "Domination",
    "submission": "Submission", "sub": "Submission", "submissive": "Submission",
    # ── Fetish ────────────────────────────────────────────────
    "fetish": "Fetish",
    # ── POV ───────────────────────────────────────────────────
    "pov": "POV", "point of view": "POV",
    # ── Hardcore / Softcore ───────────────────────────────────
    "hardcore": "Hardcore", "hard core": "Hardcore",
    "softcore": "Softcore", "soft core": "Softcore",
    # ── Nudity / Topless / Lingerie ───────────────────────────
    "nude": "Nudity", "nudity": "Nudity", "full nude": "Nudity",
    "topless": "Topless", "lingerie": "Lingerie",
    # ── MILF ──────────────────────────────────────────────────
    "milf": "MILF",
    # ── Titty Fuck ────────────────────────────────────────────
    "titty fuck": "Titty Fuck", "tit fuck": "Titty Fuck",
    # ── Hand / Foot / Rim ─────────────────────────────────────
    "handjob": "Hand Job", "hand job": "Hand Job",
    "footjob": "Foot Job", "foot job": "Foot Job",
    "rimjob": "Rimjob", "rim job": "Rimjob", "rimming": "Rimjob",
    # ── Fisting ───────────────────────────────────────────────
    "fisting": "Fisting",
    # ── Water Sports ──────────────────────────────────────────
    "piss": "Water Sports", "watersports": "Water Sports",
    "water sports": "Water Sports", "golden shower": "Water Sports",
    # ── Outdoor / Public ──────────────────────────────────────
    "outdoor": "Outdoor", "outdoors": "Outdoor", "outside": "Outdoor",
    "public": "Public",
    # ── Other ─────────────────────────────────────────────────
    "massage": "Massage", "roleplay": "Roleplay", "role play": "Roleplay",
    "cosplay": "Cosplay", "teen": "Teen",
    "cum on ass": "Cum on Ass", "coa": "Cum on Ass",
    "cum on tits": "Cum on Tits", "cot": "Cum on Tits",
}

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─── Authentication ───────────────────────────────────────────────────────────
def get_gspread_client():
    """Return an authorised gspread client using the service account."""
    if not SA_CREDENTIALS.exists():
        raise FileNotFoundError(
            f"Service account key not found at {SA_CREDENTIALS}\n"
            "Make sure service_account.json is in the same folder as this script."
        )
    creds = Credentials.from_service_account_file(str(SA_CREDENTIALS), scopes=SCOPES)
    return gspread.authorize(creds)


# ─── Dynamic column helpers ────────────────────────────────────────────────────

def _get_col_map(ws) -> dict[str, int]:
    """
    Read row 3 headers and return {header_label: 1-based column index}.
    This is the single source of truth for column positions — it automatically
    adapts when columns are inserted, removed, or reordered.
    """
    try:
        headers = ws.row_values(HEADER_ROW)
        return {h.strip(): (i + 1) for i, h in enumerate(headers) if h.strip()}
    except Exception:
        return {}


def _col(col_map: dict, header: str, fallback: int) -> int:
    """Return the 1-based column index for a header, or the fallback constant."""
    idx = col_map.get(header)
    if idx is None:
        log.debug(f"  Header '{header}' not found in sheet — using fallback col {fallback}")
    return idx if idx is not None else fallback


def _cell(row: list, col_1based: int) -> str:
    """Safely read a cell from a 0-indexed row using a 1-based column index."""
    return row[col_1based - 1].strip() if len(row) >= col_1based else ""


# ─── Sheet helpers ─────────────────────────────────────────────────────────────

def get_sheet_models(ws) -> list[dict]:
    """Return list of model dicts currently in the worksheet."""
    col_map = _get_col_map(ws)
    c_name   = _col(col_map, "Name",         COL_NAME)
    c_age    = _col(col_map, "Age",           COL_AGE)
    c_rate   = _col(col_map, "AVG Rate",      COL_RATE)
    c_rank   = _col(col_map, "Rank",          COL_RANK)
    c_loc    = _col(col_map, "Location",      COL_LOCATION)
    c_shoots = _col(col_map, "Available For", COL_SHOOTS)
    c_notes  = _col(col_map, "Notes",         COL_NOTES)

    all_values = ws.get_all_values()
    models = []
    for row_idx, row in enumerate(all_values, start=1):
        if row_idx < DATA_START_ROW:
            continue
        name = _cell(row, c_name)
        if not name:
            continue
        models.append({
            "name":     name,
            "age":      _cell(row, c_age),
            "rate":     _cell(row, c_rate),
            "rank":     _cell(row, c_rank),
            "location": _cell(row, c_loc),
            "shoots":   _cell(row, c_shoots),
            "notes":    _cell(row, c_notes),
            "row":      row_idx,
        })
    return models


def get_website_url(ws) -> str:
    """Scan row 2 across all columns for a cell that looks like a URL."""
    try:
        row2 = ws.row_values(WEBSITE_ROW)
        for cell in row2:
            val = (cell or "").strip()
            if val.startswith(("http://", "https://", "www.")):
                return val
    except Exception:
        pass
    return ""


# ─── URL helpers ───────────────────────────────────────────────────────────────
def _make_absolute_url(href: str, base_url: str) -> str:
    """Convert a relative href to an absolute URL using base_url."""
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


# ─── Roster scraping ──────────────────────────────────────────────────────────
def _scroll_and_load(page, scrolls: int = 5, sleep_per_scroll: float = 1.5):
    """
    Scroll to the bottom of the page repeatedly to trigger lazy-loaded content,
    then attempt to click any visible 'Load More' / 'Show More' buttons.
    """
    for _ in range(scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(sleep_per_scroll)

    # Click up to 6 "Load More" buttons (some sites need multiple clicks)
    load_more_selectors = [
        "button:has-text('Load More')",
        "button:has-text('Show More')",
        "a:has-text('Load More')",
        "[class*='load-more']:visible",
        "[class*='loadmore']:visible",
    ]
    for _click in range(6):
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


def _find_next_pages(soup: BeautifulSoup, base_url: str, max_extra: int = 5) -> list[str]:
    """
    Detect numbered pagination links (e.g. /page/2/, ?page=2, ?paged=3) and
    return up to max_extra additional page URLs, same-domain only.
    """
    base_domain = urlparse(base_url).netloc
    found: set[str] = set()

    for a in soup.find_all("a", href=True):
        abs_href = _make_absolute_url(a["href"], base_url)
        if not abs_href or abs_href.rstrip("/") == base_url.rstrip("/"):
            continue
        if urlparse(abs_href).netloc != base_domain:
            continue
        # Common patterns: /page/2  ?page=2  ?paged=2  /female/2/
        if (re.search(r"/page/[2-9]\d*/?$", abs_href, re.I) or
                re.search(r"[?&]paged?=([2-9]|[1-9]\d+)", abs_href, re.I)):
            found.add(abs_href)

    return sorted(found)[:max_extra]


def scrape_agency_roster(url: str, agency_name: str) -> list[tuple[str, str]]:
    """
    Scrape model names (and profile URLs where available) from an agency website.
    Returns a list of (display_name, profile_url) tuples.

    Strategy:
      1. Load the roster page and scroll / click 'Load More' to reveal lazy content.
      2. Detect numbered pagination and scrape up to 5 additional pages.
      3. Combine and deduplicate results across all pages.
    """
    if not url:
        log.warning(f"  [{agency_name}] No website URL – skipping scrape")
        return []

    normalized = url.rstrip("/")
    if normalized in SITE_URL_OVERRIDES:
        override = SITE_URL_OVERRIDES[normalized]
        log.info(f"  [{agency_name}] URL override: {url} → {override}")
        url = override

    log.info(f"  [{agency_name}] Scraping: {url}")
    all_models: list[tuple[str, str]] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=USER_AGENT)
            pw_page = ctx.new_page()

            urls_to_visit: list[str] = [url]
            visited: set[str] = set()

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

                # On the very first page, detect and queue pagination links
                if len(visited) == 1:
                    next_pages = _find_next_pages(soup, page_url)
                    if next_pages:
                        log.info(f"  [{agency_name}] Detected {len(next_pages)} additional page(s)")
                    for np in next_pages:
                        if np not in visited:
                            urls_to_visit.append(np)

                time.sleep(1)  # be polite between pages

            browser.close()

        all_models = _dedupe(all_models)

    except Exception as e:
        log.error(f"  [{agency_name}] Scrape failed: {e}")

    log.info(f"  [{agency_name}] Found {len(all_models)} models online (total across all pages)")
    return all_models


# ─── Name / URL extraction helpers ────────────────────────────────────────────
def _slug_to_name(slug: str) -> str:
    """Convert a URL slug like 'august-skye' → 'August Skye'."""
    parts = [p for p in slug.split("-") if p]
    if len(parts) < 2 or len(parts) > 4:
        return ""
    if not all(re.match(r"^[a-zA-Z]+$", p) for p in parts):
        return ""
    if any(p.lower() in SLUG_REJECT_PARTS for p in parts):
        return ""
    return " ".join(p.title() for p in parts)


def _clean_text(text: str) -> str:
    """Collapse tabs, newlines, and Unicode whitespace into single spaces."""
    return re.sub(r"[\s\u200b\u00a0]+", " ", text).strip()


def _autocorrect_allcaps(text: str) -> str:
    """Convert 'AMBER MOORE' → 'Amber Moore' for CSS-uppercase sites."""
    s = text.strip()
    if s and s == s.upper() and re.match(r"^[A-Za-z\s]+$", s):
        return s.title()
    return text


def _normalize_shoots(raw: str) -> str:
    """
    Parse a raw shoot-types string scraped from a profile page and return a
    clean, comma-separated list of canonical category names.

    Handles:
      • Various delimiters: commas, bullets (•·), pipes, semicolons, newlines
      • Abbreviations and alternate spellings via SHOOT_CANONICAL lookup
        e.g.  "B/G"  →  "Boy/Girl"
              "BG"   →  "Boy/Girl"
              "G/G"  →  "Girl/Girl"
              "DP"   →  "DP"
              "Double Penetration" →  "DP"
      • Strips stray punctuation, numbers, very short tokens
      • Deduplicates (case-insensitive)

    Returns "" if no recognizable categories are found.
    """
    if not raw:
        return ""

    # Split on delimiters that are NOT part of category names like "B/G", "G/G"
    # We split on: comma, semicolon, bullet chars, pipe, newline
    tokens = re.split(r"[,;\n•·|]+", raw)

    canonical: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        token = token.strip().strip("•·-–—").strip()
        if not token or token.isdigit():
            continue

        key = token.lower().strip()

        # Direct lookup in canonical map
        if key in SHOOT_CANONICAL:
            name = SHOOT_CANONICAL[key]
        else:
            # Try stripping extra punctuation/spaces
            key_clean = re.sub(r"[^a-z0-9 /]", "", key).strip()
            if key_clean in SHOOT_CANONICAL:
                name = SHOOT_CANONICAL[key_clean]
            else:
                # Keep as-is if it's meaningful (≥2 chars and not purely numeric)
                if len(token) >= 2:
                    name = token.title()
                else:
                    continue

        lower_name = name.lower()
        if lower_name not in seen:
            seen.add(lower_name)
            canonical.append(name)

    return ", ".join(canonical)


def _looks_like_name(text: str) -> bool:
    """Return True only if text strongly resembles a performer's name."""
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


def _dedupe(models: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    out = []
    for name, profile_url in models:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            out.append((name, profile_url))
    return out


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _extract_models_from_soup(soup: BeautifulSoup, url: str) -> list[tuple[str, str]]:
    """
    Multi-strategy extractor returning (name, profile_url) tuples.
    Strategies are tried in order; first one yielding ≥3 results wins.
    """

    # Strategy 1 – common model card / grid CSS selectors.
    # For each name element we try to find the nearest <a> ancestor for the profile URL.
    candidate_selectors = [
        ".model-name", ".model_name", ".talent-name", ".talent_name",
        ".performer-name", ".performer_name", ".girl-name", ".girl_name",
        "[class*='model'][class*='name']", "[class*='talent'][class*='name']",
        "figcaption", ".name",
        # Masonry grid used by Coxxx Models (WordPress + masonryPostGrid plugin)
        ".masonryPostGridItemText-custom",
        "[class*='masonryPostGrid'][class*='Text']",
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

    # Strategy 2 – anchor text on roster/talent pages (URL-keyed).
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

    # Strategy 3 – <img> alt tags; profile URL via parent <a>.
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

    # Strategy 4 – URL slug parsing (Wix / canvas sites like Invision Models).
    # Activates when a large share of links have no visible text.
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
                log.info("    (Strategy 4 – URL slugs triggered)")
                return _dedupe(slug_names)
    except Exception:
        pass

    # Strategy 5 – aria-label attributes on Wix gallery items (Bakery Talent).
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
            log.info("    (Strategy 5 – aria-labels triggered)")
            return _dedupe(aria_names)
    except Exception:
        pass

    # Strategy 6 – general anchor text fallback for static HTML sites (Speigler).
    try:
        names = []
        for link in soup.find_all("a", href=True):
            text = _clean_text(link.get_text(separator=" ", strip=True))
            if _looks_like_name(text):
                profile_url = _make_absolute_url(link["href"], url)
                names.append((text, profile_url))
        if len(names) >= 5:
            log.info("    (Strategy 6 – general link text fallback triggered)")
            return _dedupe(names)
    except Exception:
        pass

    return []


# ─── Profile page scraping ─────────────────────────────────────────────────────
def _extract_age_from_profile(soup: BeautifulSoup) -> str:
    """Try multiple heuristics to extract performer age from a profile page."""

    # 1. Elements whose class/id contains "age" as a whole word
    _age_kw = re.compile(r"\bage\b")
    for el in soup.find_all(True):
        el_class = " ".join(el.get("class", [])).lower()
        el_id    = re.sub(r"[-_]", " ", (el.get("id") or "").lower())
        if _age_kw.search(el_class) or _age_kw.search(el_id):
            m = re.search(r"\b(\d{2})\b", el.get_text(strip=True))
            if m:
                age = int(m.group(1))
                if 18 <= age <= 65:
                    return str(age)

    # 2. Definition-list / table label pattern: "Age" → value
    for label_el in soup.find_all(["dt", "th", "td", "label", "strong", "b", "span"]):
        label_text = label_el.get_text(strip=True).lower()
        if label_text in ("age", "age:", "my age"):
            sib = label_el.find_next_sibling()
            if sib:
                m = re.search(r"\b(\d{2})\b", sib.get_text(strip=True))
                if m:
                    age = int(m.group(1))
                    if 18 <= age <= 65:
                        return str(age)
            # Try the parent container
            if label_el.parent:
                parent_text = _clean_text(label_el.parent.get_text(" ", strip=True))
                m = re.search(r"\bAge[:\s]+(\d{2})\b", parent_text, re.IGNORECASE)
                if m:
                    age = int(m.group(1))
                    if 18 <= age <= 65:
                        return str(age)

    text = soup.get_text(" ", strip=True)

    # 3. "Age: 28" / "Age 28" / "Aged 28" anywhere on page
    m = re.search(r"\bAge[d]?[:\s]+(\d{2})\b", text, re.IGNORECASE)
    if m:
        age = int(m.group(1))
        if 18 <= age <= 65:
            return str(age)

    # 4. "28 years old"
    m = re.search(r"\b(\d{2})\s+years?\s+old\b", text, re.IGNORECASE)
    if m:
        age = int(m.group(1))
        if 18 <= age <= 65:
            return str(age)

    # 5. Birth year fallback: born 1995 → age 31
    m = re.search(r"\b(19[6-9]\d|200[0-5])\b", text)
    if m:
        birth_year = int(m.group(1))
        age = date.today().year - birth_year
        if 18 <= age <= 65:
            return str(age)

    return ""


def _extract_shoots_from_profile(soup: BeautifulSoup) -> str:
    """
    Try multiple heuristics to extract shoot categories from a profile page,
    then normalize the result through _normalize_shoots() so every label in
    the sheet uses the canonical SHOOT_CANONICAL name (e.g. 'BG' → 'Boy/Girl').
    """

    shoot_label_keywords = {
        "shoot", "shoots", "will shoot", "will do", "performs",
        "specialt", "categor", "scene type", "content type", "does",
    }

    raw = ""

    # 0. Taxonomy CSS classes: "available-for-{shoot}" (OC Models, similar WordPress sites)
    _avail_cls = re.compile(r"^available-for-(.+)$")
    avail_shoots = []
    for el in soup.find_all(True):
        for cls in el.get("class", []):
            m = _avail_cls.match(cls.lower())
            if m:
                avail_shoots.append(m.group(1).replace("-", " "))
        if avail_shoots:
            break  # found on first matching element — all classes are on it
    if avail_shoots:
        raw = ", ".join(avail_shoots)

    # 1. Labeled elements (dt/dd, strong/value, table rows, etc.)
    for label_el in soup.find_all(["dt", "th", "label", "strong", "b", "span", "p", "h3", "h4"]):
        if raw:
            break
        label_text = label_el.get_text(strip=True).lower()
        if any(kw in label_text for kw in shoot_label_keywords) and len(label_text) < 50:
            # Prefer next sibling
            sib = label_el.find_next_sibling()
            if sib:
                content = _clean_text(sib.get_text(separator=", ", strip=True))
                if 3 < len(content) < 400:
                    raw = content
                    break
            # Fall back to parent container
            if label_el.parent:
                label_str  = label_el.get_text(strip=True)
                parent_str = _clean_text(label_el.parent.get_text(" ", strip=True))
                if parent_str.lower().startswith(label_str.lower()):
                    stripped = parent_str[len(label_str):].strip().lstrip(":").strip()
                else:
                    stripped = parent_str
                if 3 < len(stripped) < 400:
                    raw = stripped
                    break

    # 2. Tag / category container elements
    if not raw:
        tag_pattern = re.compile(r"tag|categor|shoot|skill|specialt|genre", re.I)
        for el in soup.find_all(True, class_=tag_pattern):
            content = _clean_text(el.get_text(separator=", ", strip=True))
            if 3 < len(content) < 400:
                raw = content
                break

    # 3. Full-text keyword scan (last resort)
    if not raw:
        text = soup.get_text(" ", strip=True).lower()
        found = []
        for cat in sorted(SHOOT_KEYWORDS):
            if re.search(r"\b" + re.escape(cat) + r"\b", text):
                found.append(cat)
        if len(found) >= 2:
            raw = ", ".join(found)

    # Normalize all aliases → canonical names before returning
    return _normalize_shoots(raw)


def _extract_location_from_profile(soup: BeautifulSoup) -> str:
    """Try multiple heuristics to extract a performer's home city/state."""

    location_labels = {"location", "location:", "based in", "based in:", "home base",
                       "home base:", "city", "city:", "hometown", "hometown:",
                       "home city", "home city:", "base", "base:"}

    # Stop words defined first — referenced by _valid_location below
    STOP_WORDS = ("available", "height", "weight", "age", "book", "click",
                  "contact", "models", "about", "apply", "blog", "http",
                  "escort", "back to", "bottom of")

    _loc_kw = re.compile(r"\b(?:location|city|hometown)\b")
    _INVALID_LOC = re.compile(r"\d")  # digits = not a city name (pagination, dates, etc.)

    def _valid_location(text: str) -> bool:
        """Return True if text looks like an actual city/state value."""
        if not text or len(text) < 2 or len(text) > 60:
            return False
        if _INVALID_LOC.search(text):          # reject "1/17", "March 2026", etc.
            return False
        if text.lower() in location_labels:    # reject bare label words
            return False
        if any(w in text.lower() for w in STOP_WORDS):  # reject "Las Vegas Models", etc.
            return False
        return True

    _slug_to_city = {
        "los-angeles": "Los Angeles", "las-vegas": "Las Vegas",
        "florida": "Florida", "new-york": "New York", "miami": "Miami",
        "phoenix": "Phoenix", "chicago": "Chicago", "atlanta": "Atlanta",
        "dallas": "Dallas", "houston": "Houston", "seattle": "Seattle",
        "portland": "Portland", "denver": "Denver", "nashville": "Nashville",
        "san-diego": "San Diego", "san-francisco": "San Francisco",
        "austin": "Austin", "scottsdale": "Scottsdale", "tempe": "Tempe",
        "arizona": "Arizona", "california": "California", "texas": "Texas",
        "east-coast": "East Coast", "west-coast": "West Coast",
    }

    # 1a. Taxonomy CSS class pattern (e.g. OC Models: "model-location-las-vegas")
    #     Extract city directly from the class name — more reliable than reading element text.
    _tax_loc = re.compile(r"\bmodel-location-([a-z0-9-]+)\b")
    for el in soup.find_all(True):
        for cls in el.get("class", []):
            m = _tax_loc.match(cls.lower())
            if m:
                slug = m.group(1)
                city = _slug_to_city.get(slug, slug.replace("-", " ").title())
                if _valid_location(city):
                    return city

    # 1b. Elements whose class/id contains "location", "city", or "hometown" as whole words
    for el in soup.find_all(True):
        el_class = " ".join(el.get("class", [])).lower()
        el_id    = re.sub(r"[-_]", " ", (el.get("id") or "").lower())
        if not (_loc_kw.search(el_class) or _loc_kw.search(el_id)):
            continue
        # Skip nav/menu items — they match e.g. "menu-item-object-model-location"
        if "menu" in el_class or "nav" in el_class:
            continue
        text = _clean_text(el.get_text(strip=True))
        if _valid_location(text):
            return text

    # 2. Definition-list / label pattern: "Location" → value
    for label_el in soup.find_all(["dt", "th", "td", "label", "strong", "b", "span", "p"]):
        label_text = label_el.get_text(strip=True).lower().rstrip(":")
        if label_text in location_labels:
            sib = label_el.find_next_sibling()
            if sib:
                text = _clean_text(sib.get_text(strip=True))
                if _valid_location(text):
                    return text
            # Check parent container for "Location: Las Vegas" style
            if label_el.parent:
                parent_text = _clean_text(label_el.parent.get_text(" ", strip=True))
                m = re.search(
                    r"(?:location|based in|home base|hometown)[:\s]+([A-Za-z][^,\n]{2,50})",
                    parent_text, re.IGNORECASE,
                )
                if m:
                    return m.group(1).strip()

    # 3. Full-text keyword scan
    text = soup.get_text(" ", strip=True)

    # Two city patterns: ALL-CAPS style (e.g. "LAS VEGAS") and Title-Case style
    # (e.g. "Las Vegas", "Los Angeles, CA").  ALL-CAPS is tried first so sites
    # like Invision (where labels AND content are uppercase) resolve cleanly.
    # Max 2 words for all-caps (avoids "LAS VEGAS AVAILABLE FOR") and 3 for title-case.
    ALL_CAPS_CITY = r"([A-Z]{2,}(?:[ ,]+[A-Z]{2,}){0,1})"
    TITLE_CITY    = r"([A-Z][a-z]+(?:[ ,]+[A-Z][a-z]+){0,2})"

    _patterns = [
        # Most-specific: "BASED IN" is unambiguous
        (rf"BASED IN\s+{ALL_CAPS_CITY}",          True),
        (rf"BASED IN\s+{TITLE_CITY}",             True),
        # Label-colon variants (colon optional — handles "Location Miami" too)
        (rf"[Ll]ocation[:\s]+{TITLE_CITY}",       True),
        (rf"[Ll]ocation[:\s]+{ALL_CAPS_CITY}",    True),
        (rf"[Hh]ome\s*[Tt]own[:\s]+{TITLE_CITY}", True),
        (rf"[Hh]ome\s+[Bb]ase[:\s]+{TITLE_CITY}", True),
        (rf"[Cc]ity:\s*{TITLE_CITY}",              True),  # colon required to avoid ethnicity fields
    ]
    # US 2-letter state abbreviations — safe to include as second word
    US_STATES = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID",
                 "IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS",
                 "MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK",
                 "OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
                 "WI","WY","DC"}

    def _clean_city(raw: str) -> str:
        """Strip trailing non-city words from the captured string."""
        words = raw.strip().rstrip(",").split()
        result = []
        for w in words:
            w_clean = w.rstrip(",")
            # Stop at gerunds, -ABLE words, prepositions, stop words
            if re.search(r"ING$|ABL[EY]?$|FOR$|THE$|AND$|OR$", w_clean, re.I):
                break
            if w_clean.lower() in STOP_WORDS:
                break
            # If it's a 2-letter state abbrev, include and stop
            if w_clean in US_STATES:
                result.append(w_clean)
                break
            result.append(w_clean)
        return " ".join(result)

    for pat, _ in _patterns:
        m = re.search(pat, text)
        if not m:
            continue
        raw = m.group(1)
        candidate = _clean_city(raw)
        # Accept if it looks like a real place (short, no stop words)
        if 2 <= len(candidate) < 40 and not any(
            w in candidate.lower() for w in STOP_WORDS
        ):
            return candidate

    return ""


def _extract_agent_from_profile(soup: BeautifulSoup) -> str:
    """
    Try to extract an agent / booking contact name from a profile page.
    Returns the agent's name as a string, or "" if not found.
    """
    agent_labels = {"agent", "agent:", "booking agent", "booking agent:",
                    "booking contact", "booking contact:", "my agent",
                    "represented by", "represented by:", "contact", "contact:"}

    # 1. Labeled elements
    for label_el in soup.find_all(["dt", "th", "td", "label", "strong", "b", "span", "p"]):
        label_text = label_el.get_text(strip=True).lower().rstrip(":")
        if label_text in agent_labels:
            sib = label_el.find_next_sibling()
            if sib:
                text = _clean_text(sib.get_text(strip=True))
                if text and len(text) < 60:
                    return text
            if label_el.parent:
                parent_text = _clean_text(label_el.parent.get_text(" ", strip=True))
                m = re.search(
                    r"(?:agent|booking agent|booking contact|represented by)[:\s]+([A-Za-z][^\n,]{2,50})",
                    parent_text, re.IGNORECASE,
                )
                if m:
                    return m.group(1).strip()

    # 2. Free-text scan
    text = soup.get_text(" ", strip=True)
    m = re.search(
        r"(?:booking agent|booking contact|represented by|my agent)[:\s]+([A-Za-z][^\n,]{2,50})",
        text, re.IGNORECASE,
    )
    if m:
        candidate = m.group(1).strip()
        if len(candidate) < 60:
            return candidate

    return ""


def scrape_profiles_batch(
    name_url_pairs: list[tuple[str, str]],
    agency_name: str,
) -> dict[str, dict]:
    """
    Visit multiple profile pages using a SINGLE Playwright browser session
    (avoids the overhead of spawning a new browser per model).

    Returns {profile_url: {"age": str, "shoots": str}}.
    Pairs with empty URLs are silently skipped.
    """
    # Deduplicate by URL, skip blanks
    seen_urls: set[str] = set()
    valid: list[tuple[str, str]] = []
    for name, u in name_url_pairs:
        if u and u not in seen_urls:
            seen_urls.add(u)
            valid.append((name, u))

    if not valid:
        return {}

    log.info(f"  [{agency_name}] Scraping {len(valid)} profile page(s)…")
    results: dict[str, dict] = {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=USER_AGENT)
            page = ctx.new_page()

            for name, profile_url in valid:
                try:
                    page.goto(profile_url, wait_until="domcontentloaded", timeout=20_000)
                    time.sleep(1.5)
                    html   = page.content()
                    soup   = BeautifulSoup(html, "html.parser")
                    age      = _extract_age_from_profile(soup)
                    shoots   = _extract_shoots_from_profile(soup)
                    location = _extract_location_from_profile(soup)
                    agent    = _extract_agent_from_profile(soup)
                    results[profile_url] = {
                        "age": age, "shoots": shoots,
                        "location": location, "agent": agent,
                    }
                    shoots_preview = (shoots[:40] + "…") if len(shoots) > 40 else shoots
                    log.info(
                        f"    {name}: age={age or '?'}  "
                        f"loc={location or '?'}  "
                        f"agent={agent or '?'}  "
                        f"shoots={shoots_preview or '?'}"
                    )
                except Exception as e:
                    log.debug(f"    Profile failed for {name} ({profile_url}): {e}")
                    results[profile_url] = {"age": "", "shoots": ""}

                time.sleep(0.3)

            browser.close()

    except Exception as e:
        log.error(f"  [{agency_name}] Profile batch scrape failed: {e}")

    return results


# ─── Diff logic ────────────────────────────────────────────────────────────────
def compute_diff(sheet_models: list[dict], online_names: list[str], tab_name: str):
    """
    Return (to_add, to_remove).
    Applies a confidence gate to prevent mass-deletes on paginated sites.
    """
    sheet_norm  = {normalize_name(m["name"]): m for m in sheet_models}
    online_norm = {normalize_name(n): n for n in online_names}

    to_add = [online_norm[k] for k in online_norm if k not in sheet_norm]

    if sheet_models:
        confidence = len(online_names) / len(sheet_models)
        if confidence < MIN_SCRAPE_CONFIDENCE:
            log.warning(
                f"  [{tab_name}] Only found {len(online_names)} models vs "
                f"{len(sheet_models)} in sheet (confidence {confidence:.0%} < "
                f"{MIN_SCRAPE_CONFIDENCE:.0%}) – skipping removals to be safe"
            )
            to_remove = []
        else:
            to_remove = [sheet_norm[k] for k in sheet_norm if k not in online_norm]
    else:
        to_remove = []

    return to_add, to_remove


# ─── Apply changes to sheet ────────────────────────────────────────────────────
def _delete_rows_batch(ws, row_numbers: list[int]):
    """
    Delete multiple rows in a SINGLE Google Sheets batchUpdate API call.
    Requests are sent high-to-low so earlier deletions don't shift later indices.
    """
    if not row_numbers:
        return
    requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": ws.id,
                    "dimension": "ROWS",
                    "startIndex": r - 1,   # 0-based
                    "endIndex":   r,
                }
            }
        }
        for r in sorted(row_numbers, reverse=True)
    ]
    _retry_api(lambda: ws.spreadsheet.batch_update({"requests": requests}))


def apply_changes(
    ws,
    to_add:       list[str],
    to_remove:    list[dict],
    sheet_models: list[dict],
    name_to_url:  dict[str, str],   # normalized_name → profile_url
    dry_run:      bool,
    do_profiles:  bool,
    agency_name:  str,
):
    """
    Write roster additions/deletions back to the worksheet using batched API
    calls so we stay well within the 60-writes/minute Google Sheets quota.

    When do_profiles=True, also visit profile pages to fill age + shoot types
    for newly-added models and existing models missing either field.
    """

    # ── Removals – one batchUpdate call for all rows ───────────────────────────
    if to_remove:
        log.info(f"    Removing {len(to_remove)} model(s): "
                 f"{[m['name'] for m in to_remove]}")
        if not dry_run:
            _delete_rows_batch(ws, [m["row"] for m in to_remove])
            time.sleep(2)   # let the sheet settle before reading row positions

    # ── Resolve column positions dynamically from sheet headers ──────────────────
    col_map  = _get_col_map(ws)
    c_name   = _col(col_map, "Name",         COL_NAME)
    c_age    = _col(col_map, "Age",           COL_AGE)
    c_shoots = _col(col_map, "Available For", COL_SHOOTS)
    c_loc    = _col(col_map, "Location",      COL_LOCATION)
    c_notes  = _col(col_map, "Notes",         COL_NOTES)
    c_agent  = col_map.get("Agent")          # optional — only written if column exists

    # ── Additions – one append_rows call for all new models ────────────────────
    if to_add:
        log.info(f"    Adding {len(to_add)} model(s): {to_add}")
        if not dry_run:
            # Batch profile scrape for all new models (if --profiles flag)
            new_profiles: dict[str, dict] = {}
            if do_profiles:
                new_pairs = [
                    (name, name_to_url.get(normalize_name(name), ""))
                    for name in to_add
                ][:MAX_PROFILES_PER_AGENCY]
                new_profiles = scrape_profiles_batch(new_pairs, agency_name)

            # Build one row per new model using actual column positions
            max_col = max(c_name, c_age, c_shoots, c_loc, c_notes,
                          c_agent or 0)
            rows_data = []
            for name in to_add:
                profile_url  = name_to_url.get(normalize_name(name), "")
                profile_data = new_profiles.get(profile_url, {})
                row = [""] * max_col
                row[c_name   - 1] = name
                row[c_age    - 1] = profile_data.get("age", "")
                row[c_shoots - 1] = profile_data.get("shoots", "")
                row[c_loc    - 1] = profile_data.get("location", "")
                if c_agent:
                    row[c_agent - 1] = profile_data.get("agent", "")
                rows_data.append(row)

            # Single API call – append all rows at once
            _retry_api(lambda: ws.append_rows(
                rows_data,
                value_input_option="USER_ENTERED",
                table_range=f"A{DATA_START_ROW}",
            ))
            time.sleep(2)

    # ── Fill missing fields for existing models (batched) ──────────────────────
    remove_names = {normalize_name(m["name"]) for m in to_remove}

    if do_profiles:
        need_data = [
            m for m in sheet_models
            if normalize_name(m["name"]) not in remove_names
            and (not m.get("age") or not m.get("shoots") or not m.get("location"))
        ]
        if need_data:
            log.info(
                f"    Fetching profile data for {len(need_data)} model(s) "
                f"missing age/shoots/location…"
            )
            if not dry_run:
                pairs = [
                    (m["name"], name_to_url.get(normalize_name(m["name"]), ""))
                    for m in need_data
                ][:MAX_PROFILES_PER_AGENCY]
                existing_profiles = scrape_profiles_batch(pairs, agency_name)

                updates = []
                for model in need_data[:MAX_PROFILES_PER_AGENCY]:
                    profile_url = name_to_url.get(normalize_name(model["name"]), "")
                    data = existing_profiles.get(profile_url, {})
                    if not model.get("age") and data.get("age"):
                        updates.append({
                            "range":  _rc_to_a1(model["row"], c_age),
                            "values": [[data["age"]]],
                        })
                    if not model.get("shoots") and data.get("shoots"):
                        updates.append({
                            "range":  _rc_to_a1(model["row"], c_shoots),
                            "values": [[data["shoots"]]],
                        })
                    if not model.get("location") and data.get("location"):
                        updates.append({
                            "range":  _rc_to_a1(model["row"], c_loc),
                            "values": [[data["location"]]],
                        })
                    if c_agent and data.get("agent"):
                        updates.append({
                            "range":  _rc_to_a1(model["row"], c_agent),
                            "values": [[data["agent"]]],
                        })

                CHUNK = 50
                for i in range(0, len(updates), CHUNK):
                    _retry_api(lambda chunk=updates[i:i + CHUNK]:
                               ws.batch_update(chunk))
                    if i + CHUNK < len(updates):
                        time.sleep(1)
        else:
            log.info("    All existing models already have age/shoots/location data.")
    else:
        missing = [
            m for m in sheet_models
            if normalize_name(m["name"]) not in remove_names
            and (not m.get("age") or not m.get("shoots") or not m.get("location"))
        ]
        if missing:
            log.info(
                f"    ℹ  {len(missing)} model(s) missing age/shoots/location. "
                f"Re-run with --profiles to populate from profile pages."
            )


# ─── One-time column setup ─────────────────────────────────────────────────────
def add_shoots_column(sh, dry_run: bool):
    """
    One-time setup: insert a blank 'Shoot Types' column at position F (col 6)
    in every worksheet, pushing the existing Notes column from F → G.

    Run:  python update_roster.py --add-shoots-col [--dry-run]
    """
    log.info("Adding Shoot Types column to all tabs…")
    for ws in sh.worksheets():
        tab = ws.title
        log.info(f"  Tab: {tab}")
        if dry_run:
            log.info(f"    [DRY RUN] Would insert empty column at position {COL_SHOOTS}")
            continue
        try:
            # Use the Google Sheets batchUpdate API to insert a column
            body = {
                "requests": [
                    {
                        "insertDimension": {
                            "range": {
                                "sheetId": ws.id,
                                "dimension": "COLUMNS",
                                "startIndex": COL_SHOOTS - 1,  # 0-based
                                "endIndex":   COL_SHOOTS,
                            },
                            "inheritFromBefore": False,
                        }
                    }
                ]
            }
            sh.batch_update(body)

            # Set the header label in row 3 (the column header row)
            try:
                ws.update_cell(HEADER_ROW, COL_SHOOTS, "Shoot Types")
            except Exception:
                pass

            log.info(f"    ✓ Inserted 'Shoot Types' column at col {COL_SHOOTS} (F)")
            time.sleep(0.5)

        except Exception as e:
            log.error(f"    ✗ Failed for tab '{tab}': {e}")

    log.info("Column setup complete.")


# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Update Model Booking List roster")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without writing to the sheet",
    )
    parser.add_argument(
        "--tab", default=None,
        help="Process only one tab (exact name). Default: all tabs.",
    )
    parser.add_argument(
        "--profiles", action="store_true",
        help=(
            "Also visit individual model profile pages to extract age + shoot types. "
            "Up to %(default)s profiles per agency. "
            "Tip: combine with --tab to test one agency first."
        ),
    )
    parser.add_argument(
        "--add-shoots-col", action="store_true",
        help=(
            "One-time setup: insert a 'Shoot Types' column (F) in all tabs, "
            "shifting the Notes column from F to G. Run this once before "
            "using v7 features."
        ),
    )
    args = parser.parse_args()

    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_ID)

    # ── One-time column insertion ──────────────────────────────────────────────
    if args.add_shoots_col:
        add_shoots_column(sh, dry_run=args.dry_run)
        return

    # ── Normal roster update ───────────────────────────────────────────────────
    mode = "DRY RUN" if args.dry_run else "LIVE"
    profile_mode = " + PROFILES" if args.profiles else ""
    log.info(f"Starting roster update – mode: {mode}{profile_mode}")

    worksheets = sh.worksheets()
    log.info(f"Found {len(worksheets)} worksheet(s) in spreadsheet")

    for ws in worksheets:
        tab_name = ws.title
        if args.tab and tab_name != args.tab:
            continue

        log.info(f"\n{'='*60}")
        log.info(f"Processing tab: {tab_name}")

        url = get_website_url(ws)
        if not url:
            log.info("  No website URL found in row 2 – skipping")
            continue

        sheet_models = get_sheet_models(ws)
        log.info(f"  Sheet has {len(sheet_models)} model(s)")

        online_models = scrape_agency_roster(url, tab_name)
        if not online_models:
            log.warning("  No models found online – skipping to avoid data loss")
            continue

        online_names = [m[0] for m in online_models]
        name_to_url  = {normalize_name(m[0]): m[1] for m in online_models}

        to_add, to_remove = compute_diff(sheet_models, online_names, tab_name)
        log.info(f"  Diff → +{len(to_add)} to add, -{len(to_remove)} to remove")

        apply_changes(
            ws,
            to_add=to_add,
            to_remove=to_remove,
            sheet_models=sheet_models,
            name_to_url=name_to_url,
            dry_run=args.dry_run,
            do_profiles=args.profiles,
            agency_name=tab_name,
        )

        time.sleep(2)

    log.info(f"\n{'='*60}")
    log.info("Roster update complete.")


if __name__ == "__main__":
    main()
