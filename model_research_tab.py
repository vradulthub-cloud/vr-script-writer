"""
model_research_tab.py — Model Research tab for the VR Script Writer app.

Sources (all fetched in parallel):
  - Babepedia via cloudscraper (bio, photo)
  - VRPorn (bio facts + recent scenes)
  - SexLikeReal search (recent scenes)
  - POVR (recent scenes)
  - Internal Model Booking List Google Sheet (agency, rate, rank)
  - DuckDuckGo fallback

Results cached per performer name (24-hour TTL).
"""

import re
import json
import hashlib
import concurrent.futures
from pathlib import Path
from datetime import datetime, timedelta

CACHE_DIR = Path(r"C:\Users\andre\script-writer\research_cache_v2")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL_HOURS = 168  # 7 days — reduces re-fetch churn; stale data kept as fallback

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Section headers that Babepedia puts between bio fields
_BABE_SECTION_NOISE = re.compile(
    r'\s+(Body|Performances|Extra|Personal|Show more)\s*$', re.I
)

# Titles to exclude from recent scene results — compilations, PMVs, best-ofs
_COMPILATION_RE = re.compile(
    r'\b(compilation|compil|pmv|best of|best scenes|top scenes|top \d+|'
    r'collection|all scenes|mega|mashup|mix|highlights|fap|tribute|vol\.?\s*\d+)\b',
    re.I
)


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _cache_path(name: str) -> Path:
    key = hashlib.md5(name.strip().lower().encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def _cache_get(name: str) -> dict | None:
    p = _cache_path(name)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(d.get("_ts", "2000-01-01"))
        if datetime.now() - ts > timedelta(hours=CACHE_TTL_HOURS):
            return None
        return d
    except Exception:
        return None


def _cache_get_stale(name: str) -> dict | None:
    """Return cached data regardless of TTL — used as fallback if fresh fetch is empty."""
    p = _cache_path(name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cache_set(name: str, data: dict):
    data["_ts"] = datetime.now().isoformat()
    _cache_path(name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Slug helpers ───────────────────────────────────────────────────────────────

def _slug(name: str, sep: str = "-") -> str:
    return name.strip().lower().replace(" ", sep)


def _slug_caps(name: str, sep: str = "_") -> str:
    """Title-cased underscore slug: 'leana lovings' -> 'Leana_Lovings'"""
    return sep.join(w.capitalize() for w in name.strip().split())


# ── Date helpers ───────────────────────────────────────────────────────────────

def _date_to_days(date_str: str) -> int:
    """
    Convert a relative date string to approximate days ago (lower = more recent).
    Handles both short ("1y ago", "10mo ago") and long ("1 year ago") forms.
    Returns 999999 if unparseable (sorts to end).
    """
    if not date_str:
        return 999_999
    s = date_str.lower().strip()
    m = re.search(r'(\d+)', s)
    if not m:
        return 999_999
    n = int(m.group(1))
    if 'hour' in s or (s.endswith('h ago') and 'month' not in s):
        return 0
    if 'day' in s or s.endswith('d ago'):
        return n
    if 'week' in s or s.endswith('w ago'):
        return n * 7
    if 'month' in s or 'mo' in s:
        return n * 30
    if 'year' in s or s.endswith('y ago'):
        return n * 365
    return 999_999


# ── Babepedia ─────────────────────────────────────────────────────────────────

def _fetch_babepedia(name: str) -> dict:
    """Scrape Babepedia for bio. Uses cloudscraper to bypass Cloudflare."""
    try:
        import cloudscraper
        from bs4 import BeautifulSoup

        cs = cloudscraper.create_scraper()

        # Babepedia uses Title_Case_Underscores
        slug = _slug_caps(name, "_")
        url = f"https://www.babepedia.com/babe/{slug}"
        r = cs.get(url, timeout=20)

        # Fallback: as-typed with underscores
        if r.status_code != 200 or "search results" in r.text[:3000].lower():
            slug2 = name.strip().replace(" ", "_")
            r = cs.get(f"https://www.babepedia.com/babe/{slug2}", timeout=20)
        if r.status_code != 200 or "search results" in r.text[:3000].lower():
            return {}

        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        data = {"source_url": url}

        ALL_LABELS = [
            "Age", "Born", "Years active", "Birthplace", "Nationality",
            "Ethnicity", "Professions", "Sexuality", "Body", "Hair color",
            "Eye color", "Height", "Weight", "Body type",
            "Measurements", "Bra/cup size", "Boobs", "Pubic hair",
            "Solo", "Girl/girl", "Boy/girl", "Special", "Extra",
            "Instagram", "Achievements",
        ]

        for label in ALL_LABELS:
            rest = [l for l in ALL_LABELS if l != label]
            # Match label on its own line, capture until next label heading or empty lines
            stop_alts = "|".join(re.escape(l) for l in rest)
            pattern = (
                rf'(?m)^{re.escape(label)}[:\s]*\n'
                rf'((?:(?!{stop_alts})[\s\S])*?)'
                rf'(?=\n{stop_alts}[:\s]|\Z)'
            )
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                val = m.group(1).replace("\n", " ").strip()
                val = re.sub(r'\s+', ' ', val).strip()
                val = _BABE_SECTION_NOISE.sub('', val).strip()
                if val and len(val) < 300:
                    key = label.lower().replace("/", "_").replace(" ", "_")
                    data[key] = val

        # Post-clean bra/cup size (strip "show conversions" line)
        if "bra_cup_size" in data:
            data["bra_cup_size"] = re.sub(
                r'\s+show\s+conversions.*', '', data["bra_cup_size"], flags=re.I
            ).strip()

        # Remap to standard keys used by the UI
        for src, dst in [
            ("born",         "birthday"),
            ("hair_color",   "hair"),
            ("eye_color",    "eyes"),
            ("years_active", "years active"),
            ("bra_cup_size", "bra/cup size"),
            ("body_type",    "body type"),
        ]:
            if src in data:
                data[dst] = data.pop(src)

        # Extract "About" biography paragraph
        about_m = re.search(
            r'About\s+' + re.escape(name.split()[0]) + r'[^\n]*\n(.*?)(?=\nShow more|\n\n\n|\Z)',
            text, re.IGNORECASE | re.DOTALL
        )
        if about_m:
            about = about_m.group(1).replace("\n", " ").strip()
            about = re.sub(r'\s+', ' ', about)
            data["about"] = about[:500]

        # Photo URL — try clean profile photo first (no thumb suffix = main portrait)
        photo_url = ""
        import requests as _req_photo
        # 1) Try the canonical Babepedia profile photo: /pics/First_Last.jpg
        for slug_variant in (_slug_caps(name, "_"), name.strip().replace(" ", "_")):
            candidate = f"https://www.babepedia.com/pics/{slug_variant}.jpg"
            try:
                hr = _req_photo.head(candidate, timeout=5, headers=_HEADERS)
                if hr.status_code == 200:
                    photo_url = candidate
                    break
            except Exception:
                pass
        # 2) Try og:image (Babepedia sets this to performer portrait on most pages)
        if not photo_url:
            og = soup.select_one('meta[property="og:image"]')
            if og and og.get("content"):
                og_url = og["content"]
                # Only use og:image if it looks like a performer portrait, not a site logo
                if "babepedia.com" in og_url and "/pics/" in og_url:
                    photo_url = og_url
        # 3) Fallback: scan img tags for /pics/ URL that doesn't look like a movie thumbnail
        if not photo_url:
            first_name_lower = name.strip().split()[0].lower()
            for img_el in soup.select("img[src]"):
                src = img_el.get("src", "")
                if "/pics/" in src and first_name_lower in src.lower():
                    # Skip obvious studio promo images (have studio names in path/class)
                    parent_cls = " ".join(img_el.parent.get("class", []))
                    if any(x in parent_cls.lower() for x in ("movie", "scene", "cover")):
                        continue
                    photo_url = src if src.startswith("http") else "https://www.babepedia.com" + src
                    break

        data["photo_url"] = photo_url

        return data

    except Exception:
        return {}


# ── VRPorn — bio + scenes ─────────────────────────────────────────────────────

def _fetch_vrporn(name: str) -> dict:
    """Scrape VRPorn performer page: bio facts AND recent scenes."""
    try:
        import requests
        from bs4 import BeautifulSoup

        slug = _slug(name)
        # Try date-sorted URL first (WordPress orderby param), then plain performer page
        r = None
        for url in [
            f"https://vrporn.com/pornstars/{slug}/?orderby=date&order=desc",
            f"https://vrporn.com/pornstars/{slug}/",
            f"https://vrporn.com/pornstar/{slug}/",
        ]:
            r = requests.get(url, headers=_HEADERS, timeout=15, allow_redirects=True)
            if r.status_code == 200:
                break
        if not r or r.status_code != 200:
            return {"bio": {}, "scenes": []}

        soup = BeautifulSoup(r.text, "html.parser")

        # ── Bio — parse pipe-separated text from performer section ──────────
        bio = {}
        bio_sec = soup.select_one("[class*='pornstar']")
        if bio_sec:
            parts = bio_sec.get_text(separator="|", strip=True).split("|")
            VRP_KEY_MAP = {
                "birthday":      "birthday",
                "birthdate":     "birthday",
                "ethnicity":     "ethnicity",
                "height":        "height",
                "weight":        "weight",
                "place of birth":"birthplace",
                "birthplace":    "birthplace",
                "measurements":  "measurements",
                "hair color":    "hair",
                "hair":          "hair",
                "eye color":     "eyes",
                "eyes":          "eyes",
                "shoe size":     None,  # skip
            }
            i = 0
            while i < len(parts) - 1:
                # Strip tabs and colons from label
                label = re.sub(r'[\s:]+$', '', parts[i].strip()).strip().lower()
                value = parts[i + 1].strip()
                mapped = VRP_KEY_MAP.get(label)
                if mapped and value and value not in ("", "n/a"):
                    bio[mapped] = value
                    i += 2
                    continue
                i += 1

        # ── Performer profile photo ───────────────────────────────────────────
        profile_photo = ""
        # Look for the performer hero/header image (large portrait on the page)
        _photo_candidates = [
            # explicit class selectors from known VRPorn markup
            soup.select_one("[class*='pornstar-profile'] img[src]"),
            soup.select_one("[class*='performer'] img[src]"),
            soup.select_one("[class*='model-photo'] img[src]"),
            soup.select_one("[class*='profile-photo'] img[src]"),
            soup.select_one("[class*='profile-pic'] img[src]"),
        ]
        for _pc in _photo_candidates:
            if _pc:
                _src = _pc.get("src", "")
                if _src and "placeholder" not in _src.lower() and not _src.endswith(".svg"):
                    profile_photo = _src if _src.startswith("http") else "https://vrporn.com" + _src
                    break
        # If still nothing, look for og:image which is usually the performer portrait
        if not profile_photo:
            _og = soup.select_one('meta[property="og:image"]')
            if _og and _og.get("content"):
                profile_photo = _og["content"]

        # ── Scenes ────────────────────────────────────────────────────────────
        scenes = []
        for art in soup.select("article")[:12]:
            links = art.find_all("a", href=True)
            title = ""
            href = ""
            for a in links:
                txt = a.get_text(strip=True)
                lnk = a.get("href", "")
                if txt and len(txt) > 3 and "/studio/" not in lnk and "/pornstar" not in lnk:
                    title = txt
                    href = lnk
                    break
            if not href and links:
                href = links[0].get("href", "")

            # Studio + date from ui-video-card__text spans
            studio = ""
            date = ""
            for span in art.find_all("span"):
                cls = " ".join(span.get("class", []))
                if "ui-video-card__text" in cls:
                    txt = span.get_text(strip=True)
                    if not txt:
                        continue
                    if "ago" in txt.lower() or any(m in txt for m in
                            ["Jan","Feb","Mar","Apr","May","Jun",
                             "Jul","Aug","Sep","Oct","Nov","Dec"]):
                        if not date:
                            date = txt
                    elif not studio:
                        studio = txt

            # Duration from ui-time element
            dur_el = art.select_one("[class*='ui-time'], [class*='duration']")
            duration = dur_el.get_text(strip=True) if dur_el else ""

            # Stats from footer: [likes, views, comments]
            likes = views = comments = ""
            footer = art.select_one("[class*='footer']")
            if footer:
                items = footer.select("[class*='footer-item']")
                if len(items) >= 2:
                    likes    = items[0].get_text(strip=True)
                    views    = items[1].get_text(strip=True)
                    comments = items[2].get_text(strip=True) if len(items) > 2 else ""

            img = art.select_one("img[src]")
            thumb = img["src"] if img else ""
            if not href.startswith("http") and href:
                href = "https://vrporn.com" + href

            if title:
                scenes.append({
                    "title": title, "date": date, "studio": studio,
                    "url": href, "thumb": thumb, "duration": duration,
                    "views": views, "likes": likes, "comments": comments,
                })

        # Remove compilations / PMVs / best-ofs
        scenes = [s for s in scenes if not _COMPILATION_RE.search(s.get("title", ""))]
        # Sort most-recent first
        scenes.sort(key=lambda sc: _date_to_days(sc.get("date", "")))
        return {"bio": bio, "scenes": scenes[:6], "photo": profile_photo}

    except Exception:
        return {"bio": {}, "scenes": []}


# ── SexLikeReal — search-based scene fetch ────────────────────────────────────

def _fetch_slr_scenes(name: str, profile_url: str = "") -> list[dict]:
    """
    Fetch SLR scenes for a performer, sorted by most recent.

    profile_url — the performer's exact SLR page URL (e.g. from the booking sheet
                  hyperlink).  When provided this is tried first, giving the correct
                  newest-first ordering.
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        slug = _slug(name)  # e.g. "leana-lovings"
        first_name = name.strip().split()[0].lower()
        soup = None

        # Build list of candidate URLs to try, in priority order
        candidates = []
        if profile_url:
            candidates.append(profile_url)  # booking-sheet URL — exact & newest-first
        candidates += [
            f"https://sexlikereal.com/stars/{slug}",
            f"https://sexlikereal.com/stars/{slug}/",
        ]

        # 1) Try performer pages — sorted newest-first by default
        for url in candidates:
            try:
                rp = requests.get(url, headers=_HEADERS, timeout=15,
                                  allow_redirects=True)
                if rp.status_code == 200 and "search results" not in rp.text[:3000].lower():
                    candidate_soup = BeautifulSoup(rp.text, "html.parser")
                    if candidate_soup.select("article"):
                        soup = candidate_soup
                        break
            except Exception:
                pass

        # 2) Fall back to search if performer page not found / no articles
        if soup is None:
            q = name.strip().replace(" ", "+")
            for search_url in [
                f"https://sexlikereal.com/search/?q={q}&ordering=-release_date",
                f"https://sexlikereal.com/search/?q={q}&sort_by=release_date",
                f"https://sexlikereal.com/search/?q={q}",
            ]:
                try:
                    rs = requests.get(search_url, headers=_HEADERS, timeout=15,
                                      allow_redirects=True)
                    if rs.status_code == 200:
                        soup = BeautifulSoup(rs.text, "html.parser")
                        break
                except Exception:
                    pass

        if soup is None:
            return []

        scenes = []
        # Regex covers "1y ago", "10mo ago", "2 weeks ago", "3 days ago" etc.
        _DATE_RE = re.compile(
            r'\b(\d+\s*(?:years?|months?|weeks?|days?|hours?)\s+ago'
            r'|\d+(?:y|mo|w|d|h)\s+ago)',
            re.I
        )

        for art in soup.select("article")[:20]:
            title_el = art.select_one("h3")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            link_el = art.select_one("a[href]")
            href = link_el["href"] if link_el else ""
            if href and not href.startswith("http"):
                href = "https://sexlikereal.com" + href

            # Date — prefer <time> element (most reliable on performer pages)
            time_el = art.select_one("time")
            if time_el:
                date = time_el.get_text(strip=True)
            else:
                art_text = art.get_text(separator="|", strip=True)
                dm = _DATE_RE.search(art_text)
                date = dm.group(1) if dm else ""

            # Studio — find the <p> containing <time>, strip the time text from it
            studio = ""
            for p in art.find_all("p"):
                t_el = p.find("time")
                if t_el:
                    raw = p.get_text(strip=True)
                    studio = raw.replace(t_el.get_text(strip=True), "").strip()
                    break
            # Fallback: /studios/ link slug
            if not studio:
                for sa in art.find_all("a", href=True):
                    lnk = sa.get("href", "")
                    if "/studios/" in lnk:
                        slg = re.sub(r'-\d+$', '', lnk.replace("/studios/", "").strip("/"))
                        studio = re.sub(r'\bSlr\b', 'SLR',
                                 re.sub(r'\bVr\b', 'VR', slg.replace("-", " ").title()))
                        break

            # Duration
            art_text = art.get_text(separator="|", strip=True)
            dur_m = re.search(r'\b(\d{1,2}:\d{2}(?::\d{2})?)\b', art_text)
            duration = dur_m.group(1) if dur_m else ""

            # Stats — views, then next two numbers = likes, comments
            views_m = re.search(r'(\d+\.?\d*[KMB]?)\s+views?', art_text, re.I)
            views = views_m.group(1) + " views" if views_m else ""
            likes = comments = ""
            if views_m:
                nums = re.findall(r'\b(\d+\.?\d*[KMB]?)\b', art_text[views_m.end():])
                if nums:     likes    = nums[0]
                if len(nums) > 1: comments = nums[1]

            img = art.select_one("img[src]")
            thumb = ""
            if img:
                src = img.get("src") or img.get("data-src") or ""
                if src and not src.endswith(".svg"):
                    thumb = src

            scenes.append({
                "title": title, "date": date, "studio": studio,
                "url": href, "thumb": thumb, "duration": duration,
                "views": views, "likes": likes, "comments": comments,
            })

        # Remove compilations / PMVs / best-ofs
        scenes = [s for s in scenes if not _COMPILATION_RE.search(s.get("title", ""))]

        # If from search fallback, prefer scenes that name the performer
        if not profile_url:
            named  = [s for s in scenes if first_name in s["title"].lower()]
            others = [s for s in scenes if s not in named]
            scenes = named + others

        # Sort all scenes most-recent first regardless of server ordering
        scenes.sort(key=lambda sc: _date_to_days(sc.get("date", "")))
        return scenes[:6]

    except Exception:
        return []


# ── POVR ──────────────────────────────────────────────────────────────────────

def _fetch_povr_scenes(name: str) -> list[dict]:
    """Scrape POVR performer page for recent scenes."""
    try:
        import requests
        from bs4 import BeautifulSoup

        slug = _slug(name)
        for url in [
            f"https://povr.com/pornstars/{slug}/",
            f"https://povr.com/models/{slug}/",
        ]:
            r = requests.get(url, headers=_HEADERS, timeout=15, allow_redirects=True)
            if r.status_code == 200:
                break
        else:
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        scenes = []

        for card in soup.select(".scene-card, .video-card, .card, article")[:12]:
            title_el = card.select_one("h2, h3, .title, .scene-title")
            date_el  = card.select_one(".date, time, .release-date")
            link_el  = card.select_one("a[href]")
            img_el   = card.select_one("img[src], img[data-src]")

            title = title_el.get_text(strip=True) if title_el else ""
            date  = date_el.get_text(strip=True) if date_el else ""
            href  = link_el["href"] if link_el else ""
            thumb = ""
            if img_el:
                thumb = img_el.get("src") or img_el.get("data-src") or ""

            if title and len(title) > 3:
                scenes.append({"title": title, "date": date, "url": href, "thumb": thumb})

        return scenes[:6]

    except Exception:
        return []


# ── Internal Model Booking List Google Sheet ───────────────────────────────────

def _fetch_sheet_hyperlinks(creds, sheet_id: str) -> dict:
    """
    Fetch all hyperlinks from every cell in the spreadsheet via Sheets API v4.
    Returns {(sheet_title, row_0idx, col_0idx): url}.
    Cells that are hyperlinked show only display text via get_all_values();
    this call retrieves the actual underlying URLs.
    """
    try:
        import requests as _req
        # Refresh token if expired
        if hasattr(creds, "expired") and creds.expired and hasattr(creds, "refresh"):
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        token = creds.token
        resp = _req.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}",
            params={
                "includeGridData": "true",
                "fields": "sheets(properties/title,data/rowData/values/hyperlink)",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if resp.status_code != 200:
            return {}
        links = {}
        for sheet in resp.json().get("sheets", []):
            title = sheet.get("properties", {}).get("title", "")
            for grid in sheet.get("data", []):
                for r_i, row_data in enumerate(grid.get("rowData", [])):
                    for c_i, cell_data in enumerate(row_data.get("values", [])):
                        hl = cell_data.get("hyperlink")
                        if hl:
                            links[(title, r_i, c_i)] = hl
        return links
    except Exception:
        return {}


_BOOKING_CACHE_PATH = CACHE_DIR / "_booking_sheet_all.json"
_BOOKING_CACHE_TTL_HOURS = 6


def _load_booking_cache() -> dict | None:
    """Load the entire booking sheet cache from disk. Returns None if stale/missing."""
    if not _BOOKING_CACHE_PATH.exists():
        return None
    try:
        d = json.loads(_BOOKING_CACHE_PATH.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(d.get("_ts", "2000-01-01"))
        if datetime.now() - ts > timedelta(hours=_BOOKING_CACHE_TTL_HOURS):
            return None
        return d
    except Exception:
        return None


def _rebuild_booking_cache() -> dict:
    """Fetch ALL agency tabs + hyperlinks from the booking sheet and cache to disk.
    Uses a single Sheets API v4 call to get cell values + hyperlinks together,
    avoiding the slow per-tab gspread iteration."""
    from google.oauth2.service_account import Credentials
    def _get_credentials():
        return Credentials.from_service_account_file(
            r"C:\Users\andre\script-writer\service_account.json",
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
    import requests as _req

    SHEET_ID = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
    creds = _get_credentials()

    # Service account credentials need explicit refresh to get token
    from google.auth.transport.requests import Request
    creds.refresh(Request())
    token = creds.token

    # Single API call: get cell values + hyperlinks for entire spreadsheet
    resp = _req.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}",
        params={
            "includeGridData": "true",
            "fields": "sheets(properties/title,data/rowData/values(formattedValue,hyperlink))",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    if resp.status_code != 200:
        return {"_ts": datetime.now().isoformat(), "performers": {}}

    sheets_data = resp.json().get("sheets", [])

    # Build hyperlinks and row values from the single response
    hyperlinks = {}
    all_sheets = {}  # tab -> list of rows, each row = list of cell values
    for sheet in sheets_data:
        tab = sheet.get("properties", {}).get("title", "")
        rows = []
        for grid in sheet.get("data", []):
            for r_i, row_data in enumerate(grid.get("rowData", [])):
                row_cells = []
                for c_i, cell in enumerate(row_data.get("values", [])):
                    row_cells.append(cell.get("formattedValue", ""))
                    hl = cell.get("hyperlink")
                    if hl:
                        hyperlinks[(tab, r_i, c_i)] = hl
                rows.append(row_cells)
        all_sheets[tab] = rows

    # Convert hyperlinks dict to JSON-serializable format: "tab|row|col" -> url
    hl_json = {f"{t}|{r}|{c}": url for (t, r, c), url in hyperlinks.items()}

    performers = {}  # name_lower -> {agency, agency_url, data, tab, row_idx}

    for tab, rows in all_sheets.items():
        if any(k in tab for k in ("Legend", "Search", "Dashboard")):
            continue
        if len(rows) < 3:
            continue
        headers = [h.strip().lower() for h in rows[2]]

        # Agency website from row[1]
        agency_url = ""
        if len(rows) > 1:
            for c_i, cell in enumerate(rows[1]):
                cell = cell.strip()
                hl = hyperlinks.get((tab, 1, c_i))
                if hl:
                    agency_url = hl
                    break
                if cell.startswith("http"):
                    agency_url = cell
                    break

        for r_offset, row in enumerate(rows[3:]):
            if not row or not row[0].strip():
                continue
            row_idx = r_offset + 3
            name_lower = row[0].strip().lower()

            row_data = {
                headers[i]: row[i].strip()
                for i in range(min(len(headers), len(row)))
                if i < len(headers) and row[i].strip()
            }

            # Overlay hyperlinks for profile columns
            _LINK_COLS = {"slr profile": "slr_profile_url", "vrp profile": "vrp_profile_url"}
            for col_name, url_key in _LINK_COLS.items():
                if col_name in headers:
                    c_i = headers.index(col_name)
                    hl = hyperlinks.get((tab, row_idx, c_i))
                    if hl:
                        row_data[url_key] = hl

            # Scan all cells for hyperlinks
            for c_i, cell_val in enumerate(row):
                hl = hyperlinks.get((tab, row_idx, c_i))
                if hl and c_i < len(headers):
                    col_key = headers[c_i].strip().lower() + "_url"
                    if col_key not in row_data:
                        row_data[col_key] = hl

            performers[name_lower] = {
                "agency": tab,
                "agency_url": agency_url,
                "data": row_data,
            }

    cache = {"_ts": datetime.now().isoformat(), "performers": performers}
    _BOOKING_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return cache


def _fetch_booking_sheet(name: str) -> dict:
    """
    Look up performer in the Model Booking List Google Sheet.

    Uses a disk cache (1-hour TTL) of the entire sheet to avoid hitting
    the Google Sheets API on every lookup.

    Sheet structure per agency tab:
      row[0]  = Agency name label
      row[1]  = Agency website URL (first cell labelled "Website", URL in cell or hyperlink)
      row[2]  = Column headers: Name, Age, …, SLR Profile, VRP Profile, …
      row[3+] = Data rows  (SLR/VRP Profile cells are hyperlinked — display text "SLR"/"VRP")
    """
    try:
        import difflib

        cache = _load_booking_cache()
        if cache is None:
            cache = _rebuild_booking_cache()

        performers = cache.get("performers", {})
        name_norm = name.strip().lower()

        # Exact match
        if name_norm in performers:
            return performers[name_norm]

        # Fuzzy fallback
        close = difflib.get_close_matches(name_norm, list(performers.keys()), n=1, cutoff=0.82)
        if close:
            return performers[close[0]]

        return {}

    except Exception:
        return {}


# ── DuckDuckGo fallback ────────────────────────────────────────────────────────

def _fetch_ddg_bio(name: str) -> str:
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        snippets = []
        with DDGS() as ddgs:
            for q in [
                f'"{name}" pornstar born nationality biography',
                f'"{name}" adult performer age height measurements',
            ]:
                try:
                    for r in ddgs.text(q, max_results=3):
                        body = r.get("body", "").strip()[:300]
                        if name.split()[0].lower() in body.lower():
                            snippets.append(body)
                except Exception:
                    continue

        return " | ".join(snippets[:4]) if snippets else ""

    except Exception:
        return ""


# ── Trending / popular performers ─────────────────────────────────────────────

_TRENDING_CACHE_FILE = CACHE_DIR / "_trending_models.json"


def fetch_trending_models(n: int = 10) -> list[dict]:
    """
    Fetch currently popular VR performers from SLR and VRPorn model listing pages.
    Returns list of {name, photo_url, platform, profile_url, scenes, followers, views}.
    Results are cached on disk for 6 hours.
    """
    # Disk cache
    if _TRENDING_CACHE_FILE.exists():
        try:
            d = json.loads(_TRENDING_CACHE_FILE.read_text(encoding="utf-8"))
            ts = datetime.fromisoformat(d.get("_ts", "2000-01-01"))
            if datetime.now() - ts < timedelta(hours=6):
                return d.get("models", [])[:n]
        except Exception:
            pass

    import requests
    from bs4 import BeautifulSoup

    results = []
    seen = set()

    _NUM_RE = re.compile(r'(\d[\d,\.]*\s*[KMB]?)', re.I)

    def _extract_stat(text):
        """Pull first number-like token from a string."""
        m = _NUM_RE.search(text)
        return m.group(1).replace(",", "").strip() if m else ""

    def _add(name, photo, platform, profile_url="", scenes="", followers="", views=""):
        key = name.strip().lower()
        if key in seen or len(key) < 3:
            return
        if re.match(r'^[A-Z]{2,}$', name.strip()) or name.strip().isdigit():
            return
        if photo and not photo.endswith(".svg") and not photo.endswith(".gif"):
            seen.add(key)
            results.append({
                "name": name.strip(), "photo_url": photo,
                "platform": platform, "profile_url": profile_url,
                "scenes": scenes, "followers": followers, "views": views,
            })

    # ── SLR popular stars ─────────────────────────────────────────────────────
    try:
        for url in [
            "https://sexlikereal.com/stars/?ordering=most_popular",
            "https://sexlikereal.com/stars/",
        ]:
            r = requests.get(url, headers=_HEADERS, timeout=20, allow_redirects=True)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")

            cards = (soup.select("article") or
                     soup.select("[class*='star'] a[href]") or
                     soup.select("[class*='model'] a[href]") or
                     soup.select("[class*='performer'] a[href]"))

            for card in cards[:n * 2]:
                name_el = (card.select_one("h2") or card.select_one("h3") or
                           card.select_one("[class*='name']") or
                           card.select_one("[class*='title']"))
                name = name_el.get_text(strip=True) if name_el else ""
                if not name:
                    name = card.get("title", "") or card.get("aria-label", "")

                img = card.select_one("img[src]") or card.select_one("img[data-src]")
                photo = ""
                if img:
                    photo = img.get("src") or img.get("data-src") or ""
                    if not photo.startswith("http") and photo:
                        photo = "https://sexlikereal.com" + photo

                link = card if card.name == "a" else card.select_one("a[href]")
                href = link.get("href", "") if link else ""
                if href and not href.startswith("http"):
                    href = "https://sexlikereal.com" + href

                # Stats: look for spans/divs mentioning videos, followers, views
                card_text = card.get_text(separator="|", strip=True)
                scenes = followers = views = ""
                for part in card_text.split("|"):
                    pl = part.lower()
                    if any(w in pl for w in ("video", "scene", "film")) and not scenes:
                        scenes = _extract_stat(part)
                    elif any(w in pl for w in ("follower", "fan", "subscribe")) and not followers:
                        followers = _extract_stat(part)
                    elif any(w in pl for w in ("view",)) and not views:
                        views = _extract_stat(part)

                _add(name, photo, "SLR", href, scenes, followers, views)
                if len(results) >= n:
                    break

            if results:
                break
    except Exception:
        pass

    # ── VRPorn popular performers ─────────────────────────────────────────────
    if len(results) < n:
        try:
            for url in [
                "https://vrporn.com/pornstars/?filter=popular",
                "https://vrporn.com/pornstars/",
            ]:
                r = requests.get(url, headers=_HEADERS, timeout=20, allow_redirects=True)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")

                cards = (soup.select("article") or
                         soup.select("[class*='pornstar']") or
                         soup.select("[class*='model-card']"))

                for card in cards[:n * 2]:
                    name_el = (card.select_one("h2") or card.select_one("h3") or
                               card.select_one("[class*='name']") or
                               card.select_one("[class*='title']"))
                    name = name_el.get_text(strip=True) if name_el else ""

                    img = card.select_one("img[src]") or card.select_one("img[data-src]")
                    photo = ""
                    if img:
                        photo = img.get("src") or img.get("data-src") or ""
                        if not photo.startswith("http") and photo:
                            photo = "https://vrporn.com" + photo

                    link = card if card.name == "a" else card.select_one("a[href]")
                    href = link.get("href", "") if link else ""
                    if href and not href.startswith("http"):
                        href = "https://vrporn.com" + href

                    card_text = card.get_text(separator="|", strip=True)
                    scenes = followers = views = ""
                    for part in card_text.split("|"):
                        pl = part.lower()
                        if any(w in pl for w in ("video", "scene", "film")) and not scenes:
                            scenes = _extract_stat(part)
                        elif any(w in pl for w in ("follower", "fan", "subscribe")) and not followers:
                            followers = _extract_stat(part)
                        elif "view" in pl and not views:
                            views = _extract_stat(part)

                    _add(name, photo, "VRP", href, scenes, followers, views)
                    if len(results) >= n:
                        break

                if results:
                    break
        except Exception:
            pass

    # Persist to disk
    try:
        _TRENDING_CACHE_FILE.write_text(
            json.dumps({"_ts": datetime.now().isoformat(), "models": results},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    return results[:n]


# ── Server-side photo fetch (bypasses hotlink protection) ─────────────────────

def fetch_photo_bytes(url: str) -> bytes | None:
    """
    Download image bytes server-side, bypassing Cloudflare / hotlink protection.
    Uses cloudscraper (same as _fetch_babepedia) so Babepedia URLs work.
    Returns raw bytes on success, None on failure.
    """
    if not url:
        return None
    try:
        import cloudscraper
        cs = cloudscraper.create_scraper()
        r = cs.get(url, timeout=12, headers={
            **_HEADERS,
            "Referer": "https://www.babepedia.com/",
        })
        ct = r.headers.get("content-type", "")
        if r.status_code == 200 and "image" in ct:
            return r.content
    except Exception:
        pass
    return None


def fetch_performer_photo_url(name: str) -> str:
    """
    Fetch a performer portrait photo URL.
    VRPorn og:image  → cdn.vrporn.com/models/{slug}/photo_*.jpg  (portrait, no hotlink block)
    SLR og:image     → fallback (some performers only on SLR)
    Returns a CDN URL string ready to use in an <img src>, or "" on failure.
    """
    import requests
    from bs4 import BeautifulSoup

    # ── disk-cache: reuse any non-Babepedia URL ─────────────────────────────────
    cached = _cache_get(name)
    if cached:
        url = cached.get("photo_url", "")
        if url and "babepedia.com" not in url and not url.endswith(".svg"):
            return url

    slug = _slug(name)

    def _is_good(url: str) -> bool:
        return bool(url) and "placeholder" not in url.lower() and not url.endswith(".svg")

    def _try_vrp() -> str:
        for path in [f"https://vrporn.com/pornstars/{slug}/",
                     f"https://vrporn.com/pornstar/{slug}/"]:
            try:
                r = requests.get(path, headers=_HEADERS, timeout=10, allow_redirects=True)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                og = soup.select_one('meta[property="og:image"]')
                if og:
                    p = og.get("content", "")
                    # VRPorn performer og:image = cdn.vrporn.com/models/{slug}/photo_*.jpg (portrait)
                    if _is_good(p):
                        return p
            except Exception:
                pass
        return ""

    def _try_slr() -> str:
        try:
            r = requests.get(f"https://sexlikereal.com/stars/{slug}",
                             headers=_HEADERS, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                og = soup.select_one('meta[property="og:image"]')
                if og:
                    p = og.get("content", "")
                    # Only use SLR og:image if it's a performer-specific image (not the site default)
                    if _is_good(p) and "slr-og" not in p and "default" not in p.lower():
                        return p
        except Exception:
            pass
        return ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fut_vrp = ex.submit(_try_vrp)
        fut_slr = ex.submit(_try_slr)
        return fut_vrp.result() or fut_slr.result()


# ── Main entry point ──────────────────────────────────────────────────────────

def lookup_model_profile(name: str, force_refresh: bool = False) -> dict:
    """
    Fetch all available data for a performer.

    Phase 1 (serial):  booking sheet — needed to extract the SLR profile URL so
                       we can hit the performer's own page (newest-first) instead
                       of a relevance-sorted search.
    Phase 2 (parallel): everything else, with the SLR URL passed in.
    """
    if not force_refresh:
        cached = _cache_get(name)
        if cached:
            return cached
    # Hold stale data as fallback in case fresh fetch returns empty
    _stale = _cache_get_stale(name)

    # ── Phase 1: booking sheet (fast; provides SLR profile URL) ──────────────
    booking = _fetch_booking_sheet(name)
    bk_data = booking.get("data", {}) if booking else {}
    slr_hint = bk_data.get("slr_profile_url", "")

    # ── Phase 2: all web sources in parallel ─────────────────────────────────
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        fut_babe = ex.submit(_fetch_babepedia, name)
        fut_vrp  = ex.submit(_fetch_vrporn, name)
        fut_slr  = ex.submit(_fetch_slr_scenes, name, slr_hint)
        fut_ddg  = ex.submit(_fetch_ddg_bio, name)

    def _safe(fut, default):
        try:
            return fut.result()
        except Exception:
            return default

    babe    = _safe(fut_babe, {})
    vrp_res = _safe(fut_vrp,  {"bio": {}, "scenes": []})
    slr     = _safe(fut_slr,  [])
    ddg_bio = _safe(fut_ddg,  "")
    # booking already fetched in phase 1

    vrp_bio    = vrp_res.get("bio", {}) if isinstance(vrp_res, dict) else {}
    vrp_scenes = vrp_res.get("scenes", []) if isinstance(vrp_res, dict) else []
    vrp_photo  = vrp_res.get("photo", "") if isinstance(vrp_res, dict) else ""

    # Merge bio: Babepedia takes priority (more detailed), VRPorn fills gaps
    bio = {}
    bio.update(vrp_bio)
    for k, v in babe.items():
        if k not in ("source_url", "photo_url", "about") and v:
            bio[k] = v

    about     = babe.get("about", "")
    # Prefer VRPorn performer photo (matches card thumbnails); fall back to Babepedia
    photo_url = vrp_photo or babe.get("photo_url", "")
    sources   = []
    if babe.get("source_url"):
        sources.append(("Babepedia", babe["source_url"]))

    profile = {
        "name":      name,
        "bio":       bio,
        "about":     about,
        "booking":   booking,
        "slr":       slr   if isinstance(slr,  list) else [],
        "vrp":       vrp_scenes,
        "ddg_bio":   ddg_bio if isinstance(ddg_bio, str) else "",
        "photo_url": photo_url,
        "_sources":  sources,
    }

    # Only overwrite cache if fresh fetch returned meaningful data.
    # If everything came back empty (network errors, rate limits), preserve stale data.
    _has_data = bool(photo_url or bio or slr or vrp_scenes or about or ddg_bio)
    if _has_data:
        _cache_set(name, profile)
        return profile
    elif _stale:
        # Bump the timestamp so we don't immediately re-fetch next load
        _stale["_ts"] = datetime.now().isoformat()
        _cache_path(name).write_text(json.dumps(_stale, ensure_ascii=False, indent=2), encoding="utf-8")
        return _stale
    else:
        _cache_set(name, profile)
        return profile
