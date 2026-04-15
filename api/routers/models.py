"""
Models API router.

Provides read endpoints for the model/performer booking database.
Sourced from the Booking sheet, synced into the bookings SQLite table.

Routes:
  GET /api/models/                  — list all models, optional search
  GET /api/models/{name}            — get single model by name (case-insensitive)
  GET /api/models/{name}/profile    — full profile: bio, photo, recent scenes (scraped + cached)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.auth import CurrentUser
from api.database import get_db

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])

# ---------------------------------------------------------------------------
# Shared scraper headers
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_COMPILATION_RE = re.compile(
    r'\b(compilation|compil|pmv|best of|best scenes|top scenes|top \d+|'
    r'collection|all scenes|mega|mashup|mix|highlights|fap|tribute|vol\.?\s*\d+)\b',
    re.I,
)

_BABE_SECTION_NOISE = re.compile(
    r'\s+(Body|Performances|Extra|Personal|Show more)\s*$', re.I
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ModelResponse(BaseModel):
    name: str
    agency: str
    agency_link: str
    rate: str
    rank: str           # Great / Good / Moderate / Poor
    notes: str          # Available For / acts (from Notes column)
    info: str           # Raw compact metadata string
    # Parsed info fields
    age: str
    last_booked: str
    bookings_count: str
    location: str
    # Computed
    opportunity_score: int   # 0–100


class SceneResult(BaseModel):
    title: str = ""
    date: str = ""
    studio: str = ""
    url: str = ""
    thumb: str = ""
    duration: str = ""
    views: str = ""
    likes: str = ""


class ProfileResponse(BaseModel):
    name: str
    photo_url: str = ""
    bio: dict[str, str] = {}
    slr_profile_url: str = ""
    slr_scenes: list[SceneResult] = []
    vrp_profile_url: str = ""
    vrp_scenes: list[SceneResult] = []
    booking_studios: dict[str, int] = {}   # studio → shoot count from our scripts table
    cached_at: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[ModelResponse])
async def list_models(
    user: CurrentUser,
    search: Optional[str] = Query(default=None, description="Search by name or agency"),
):
    """List all models from the bookings table, optionally filtered by name or agency."""
    query = "SELECT name, agency, agency_link, rate, rank, notes, info FROM bookings WHERE 1=1"
    params: list = []

    if search:
        query += " AND (name LIKE ? OR agency LIKE ? OR notes LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    query += " ORDER BY name ASC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_model(dict(r)) for r in rows]


@router.get("/{name}/profile", response_model=ProfileResponse)
async def get_model_profile(
    name: str,
    user: CurrentUser,
    refresh: bool = Query(default=False, description="Force re-scrape, ignoring cache"),
):
    """Full performer profile: bio facts, photo, and recent scenes from SLR + VRPorn.

    Results are cached in SQLite for 7 days. Pass ?refresh=true to force a fresh scrape.
    """
    # Resolve canonical name + agency_link from DB
    with get_db() as conn:
        row = conn.execute(
            "SELECT name, agency_link FROM bookings WHERE LOWER(name) = LOWER(?)",
            (name,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Model '{name}' not found")

    canonical = row["name"]
    agency_link = row["agency_link"] or ""

    # Booking history from our scripts table (studio breakdown)
    with get_db() as conn:
        studio_rows = conn.execute(
            """SELECT studio, COUNT(*) as cnt FROM scripts
               WHERE female LIKE ? GROUP BY studio ORDER BY cnt DESC""",
            (f"%{canonical}%",),
        ).fetchall()
    booking_studios = {r["studio"]: r["cnt"] for r in studio_rows}

    # Check SQLite cache (7-day TTL) unless refresh requested
    if not refresh:
        with get_db() as conn:
            cached = conn.execute(
                "SELECT profile_json, cached_at FROM model_profiles WHERE LOWER(name) = LOWER(?)",
                (canonical,),
            ).fetchone()
        if cached:
            try:
                cached_at = datetime.fromisoformat(cached["cached_at"])
                if cached_at.tzinfo is None:
                    cached_at = cached_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - cached_at < timedelta(days=7):
                    data = json.loads(cached["profile_json"])
                    data["booking_studios"] = booking_studios
                    data["cached_at"] = cached["cached_at"]
                    return ProfileResponse(**data)
            except Exception:
                pass

    # Scrape in parallel via thread pool (blocking IO)
    slr_link = agency_link if "sexlikereal" in agency_link.lower() else ""
    loop = asyncio.get_event_loop()

    babe_fut = loop.run_in_executor(None, _scrape_babepedia, canonical)
    vrp_fut  = loop.run_in_executor(None, _scrape_vrporn, canonical)
    slr_fut  = loop.run_in_executor(None, _scrape_slr_scenes, canonical, slr_link)

    babe_data, vrp_data, slr_scenes = await asyncio.gather(babe_fut, vrp_fut, slr_fut)

    # Merge bio — Babepedia is richer; VRPorn fills gaps
    bio: dict[str, str] = {}
    bio.update(vrp_data.get("bio", {}))
    skip = {"source_url", "photo_url", "about", "_ts"}
    bio.update({
        k: v for k, v in babe_data.items()
        if k not in skip and isinstance(v, str) and v
    })

    about = babe_data.get("about", "")
    if about:
        bio["about"] = about

    photo_url = babe_data.get("photo_url") or vrp_data.get("photo", "") or ""
    slr_profile_url = slr_link or f"https://sexlikereal.com/stars/{_slug(canonical)}"
    vrp_profile_url = f"https://vrporn.com/pornstars/{_slug(canonical)}/"

    now_iso = datetime.now(timezone.utc).isoformat()
    profile_data = {
        "name": canonical,
        "photo_url": photo_url,
        "bio": bio,
        "slr_profile_url": slr_profile_url,
        "slr_scenes": slr_scenes,
        "vrp_profile_url": vrp_profile_url,
        "vrp_scenes": vrp_data.get("scenes", []),
        "booking_studios": booking_studios,
        "cached_at": now_iso,
    }

    # Persist to cache (upsert)
    cache_payload = {k: v for k, v in profile_data.items() if k != "booking_studios"}
    with get_db() as conn:
        conn.execute(
            """INSERT INTO model_profiles (name, profile_json, cached_at)
               VALUES (?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                 profile_json = excluded.profile_json,
                 cached_at    = excluded.cached_at""",
            (canonical, json.dumps(cache_payload), now_iso),
        )

    return ProfileResponse(**profile_data)


@router.get("/{name}", response_model=ModelResponse)
async def get_model(name: str, user: CurrentUser):
    """Get a single model by name (case-insensitive exact match)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT name, agency, agency_link, rate, rank, notes, info FROM bookings WHERE LOWER(name) = LOWER(?)",
            (name,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Model '{name}' not found")

    return _row_to_model(dict(row))


# ---------------------------------------------------------------------------
# Scraper: Babepedia
# ---------------------------------------------------------------------------

def _scrape_babepedia(name: str) -> dict:
    """Scrape Babepedia for bio facts + photo. Uses cloudscraper to bypass CF."""
    try:
        import cloudscraper
        from bs4 import BeautifulSoup

        cs = cloudscraper.create_scraper()
        slug = _slug_caps(name)
        url = f"https://www.babepedia.com/babe/{slug}"
        r = cs.get(url, timeout=20)

        if r.status_code != 200 or "search results" in r.text[:3000].lower():
            slug2 = name.strip().replace(" ", "_")
            r = cs.get(f"https://www.babepedia.com/babe/{slug2}", timeout=20)
        if r.status_code != 200 or "search results" in r.text[:3000].lower():
            return {}

        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        data: dict = {"source_url": url}

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

        if "bra_cup_size" in data:
            data["bra_cup_size"] = re.sub(
                r'\s+show\s+conversions.*', '', data["bra_cup_size"], flags=re.I
            ).strip()

        for src, dst in [
            ("born",         "birthday"),
            ("hair_color",   "hair"),
            ("eye_color",    "eyes"),
            ("years_active", "years active"),
            ("bra_cup_size", "measurements"),
            ("body_type",    "body type"),
        ]:
            if src in data:
                data[dst] = data.pop(src)

        about_m = re.search(
            r'About\s+' + re.escape(name.split()[0]) + r'[^\n]*\n(.*?)(?=\nShow more|\n\n\n|\Z)',
            text, re.IGNORECASE | re.DOTALL,
        )
        if about_m:
            about = about_m.group(1).replace("\n", " ").strip()
            about = re.sub(r'\s+', ' ', about)
            data["about"] = about[:500]

        # Photo: check canonical URL first, then og:image, then img scan
        import requests as _req
        photo_url = ""
        for slug_v in (_slug_caps(name), name.strip().replace(" ", "_")):
            candidate = f"https://www.babepedia.com/pics/{slug_v}.jpg"
            try:
                hr = _req.head(candidate, timeout=5, headers=_HEADERS)
                if hr.status_code == 200:
                    photo_url = candidate
                    break
            except Exception:
                pass

        if not photo_url:
            og = soup.select_one('meta[property="og:image"]')
            if og and og.get("content") and "/pics/" in og["content"]:
                photo_url = og["content"]

        if not photo_url:
            first = name.strip().split()[0].lower()
            for img_el in soup.select("img[src]"):
                src = img_el.get("src", "")
                if "/pics/" in src and first in src.lower():
                    parent_cls = " ".join(img_el.parent.get("class", []))
                    if any(x in parent_cls.lower() for x in ("movie", "scene", "cover")):
                        continue
                    photo_url = src if src.startswith("http") else "https://www.babepedia.com" + src
                    break

        data["photo_url"] = photo_url
        return data

    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Scraper: VRPorn (bio facts + recent scenes)
# ---------------------------------------------------------------------------

def _scrape_vrporn(name: str) -> dict:
    """Scrape VRPorn performer page: bio facts + recent scenes + profile photo."""
    try:
        import requests
        from bs4 import BeautifulSoup

        slug = _slug(name)
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
            return {"bio": {}, "scenes": [], "photo": ""}

        soup = BeautifulSoup(r.text, "html.parser")

        # Bio
        bio: dict[str, str] = {}
        bio_sec = soup.select_one("[class*='pornstar']")
        if bio_sec:
            parts = bio_sec.get_text(separator="|", strip=True).split("|")
            VRP_KEY_MAP = {
                "birthday": "birthday", "birthdate": "birthday",
                "ethnicity": "ethnicity", "height": "height", "weight": "weight",
                "place of birth": "birthplace", "birthplace": "birthplace",
                "measurements": "measurements",
                "hair color": "hair", "hair": "hair",
                "eye color": "eyes", "eyes": "eyes",
                "shoe size": None,
            }
            i = 0
            while i < len(parts) - 1:
                label = re.sub(r'[\s:]+$', '', parts[i].strip()).strip().lower()
                value = parts[i + 1].strip()
                mapped = VRP_KEY_MAP.get(label)
                if mapped and value and value not in ("", "n/a"):
                    bio[mapped] = value
                    i += 2
                    continue
                i += 1

        # Profile photo
        photo = ""
        for sel in [
            "[class*='pornstar-profile'] img[src]",
            "[class*='performer'] img[src]",
            "[class*='model-photo'] img[src]",
            "[class*='profile-photo'] img[src]",
        ]:
            el = soup.select_one(sel)
            if el:
                src = el.get("src", "")
                if src and "placeholder" not in src.lower() and not src.endswith(".svg"):
                    photo = src if src.startswith("http") else "https://vrporn.com" + src
                    break
        if not photo:
            og = soup.select_one('meta[property="og:image"]')
            if og and og.get("content"):
                photo = og["content"]

        # Scenes
        scenes: list[dict] = []
        for art in soup.select("article")[:12]:
            links = art.find_all("a", href=True)
            title = href = ""
            for a in links:
                txt = a.get_text(strip=True)
                lnk = a.get("href", "")
                if txt and len(txt) > 3 and "/studio/" not in lnk and "/pornstar" not in lnk:
                    title = txt
                    href = lnk
                    break

            studio = date = ""
            for span in art.find_all("span"):
                cls = " ".join(span.get("class", []))
                if "ui-video-card__text" in cls:
                    txt = span.get_text(strip=True)
                    if not txt:
                        continue
                    if "ago" in txt.lower() or any(
                        m in txt for m in ["Jan","Feb","Mar","Apr","May","Jun",
                                           "Jul","Aug","Sep","Oct","Nov","Dec"]
                    ):
                        if not date:
                            date = txt
                    elif not studio:
                        studio = txt

            dur_el = art.select_one("[class*='ui-time'], [class*='duration']")
            duration = dur_el.get_text(strip=True) if dur_el else ""

            views = likes = ""
            footer = art.select_one("[class*='footer']")
            if footer:
                items = footer.select("[class*='footer-item']")
                if len(items) >= 2:
                    views = items[0].get_text(strip=True)
                    likes = items[1].get_text(strip=True)

            img = art.select_one("img[src]")
            thumb = img["src"] if img else ""
            if href and not href.startswith("http"):
                href = "https://vrporn.com" + href

            if title:
                scenes.append({
                    "title": title, "date": date, "studio": studio,
                    "url": href, "thumb": thumb, "duration": duration,
                    "views": views, "likes": likes,
                })

        scenes = [s for s in scenes if not _COMPILATION_RE.search(s.get("title", ""))]
        scenes.sort(key=lambda s: _date_to_days(s.get("date", "")))
        return {"bio": bio, "scenes": scenes[:6], "photo": photo}

    except Exception:
        return {"bio": {}, "scenes": [], "photo": ""}


# ---------------------------------------------------------------------------
# Scraper: SexLikeReal (scenes only)
# ---------------------------------------------------------------------------

def _scrape_slr_scenes(name: str, profile_url: str = "") -> list[dict]:
    """Fetch SLR scenes for a performer, sorted most-recent first."""
    try:
        import requests
        from bs4 import BeautifulSoup

        slug = _slug(name)
        first = name.strip().split()[0].lower()
        soup = None

        candidates = []
        if profile_url:
            candidates.append(profile_url)
        candidates += [
            f"https://sexlikereal.com/stars/{slug}",
            f"https://sexlikereal.com/stars/{slug}/",
        ]

        for url in candidates:
            try:
                rp = requests.get(url, headers=_HEADERS, timeout=15, allow_redirects=True)
                if rp.status_code == 200 and "search results" not in rp.text[:3000].lower():
                    candidate_soup = BeautifulSoup(rp.text, "html.parser")
                    if candidate_soup.select("article"):
                        soup = candidate_soup
                        break
            except Exception:
                pass

        if soup is None:
            q = name.strip().replace(" ", "+")
            for search_url in [
                f"https://sexlikereal.com/search/?q={q}&ordering=-release_date",
                f"https://sexlikereal.com/search/?q={q}",
            ]:
                try:
                    rs = requests.get(search_url, headers=_HEADERS, timeout=15, allow_redirects=True)
                    if rs.status_code == 200:
                        soup = BeautifulSoup(rs.text, "html.parser")
                        break
                except Exception:
                    pass

        if soup is None:
            return []

        _DATE_RE = re.compile(
            r'\b(\d+\s*(?:years?|months?|weeks?|days?|hours?)\s+ago'
            r'|\d+(?:y|mo|w|d|h)\s+ago)',
            re.I,
        )

        scenes: list[dict] = []
        for art in soup.select("article")[:20]:
            title_el = art.select_one("h3")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            link_el = art.select_one("a[href]")
            href = link_el["href"] if link_el else ""
            if href and not href.startswith("http"):
                href = "https://sexlikereal.com" + href

            time_el = art.select_one("time")
            if time_el:
                date = time_el.get_text(strip=True)
            else:
                art_text = art.get_text(separator="|", strip=True)
                dm = _DATE_RE.search(art_text)
                date = dm.group(1) if dm else ""

            studio = ""
            for p in art.find_all("p"):
                t_el = p.find("time")
                if t_el:
                    studio = p.get_text(strip=True).replace(t_el.get_text(strip=True), "").strip()
                    break
            if not studio:
                for sa in art.find_all("a", href=True):
                    lnk = sa.get("href", "")
                    if "/studios/" in lnk:
                        slg = re.sub(r'-\d+$', '', lnk.replace("/studios/", "").strip("/"))
                        studio = re.sub(r'\bSlr\b', 'SLR',
                                 re.sub(r'\bVr\b', 'VR', slg.replace("-", " ").title()))
                        break

            art_text = art.get_text(separator="|", strip=True)
            dur_m = re.search(r'\b(\d{1,2}:\d{2}(?::\d{2})?)\b', art_text)
            duration = dur_m.group(1) if dur_m else ""

            views_m = re.search(r'(\d+\.?\d*[KMB]?)\s+views?', art_text, re.I)
            views = views_m.group(1) + " views" if views_m else ""

            img = art.select_one("img[src]")
            thumb = ""
            if img:
                src = img.get("src") or img.get("data-src") or ""
                if src and not src.endswith(".svg"):
                    thumb = src

            scenes.append({
                "title": title, "date": date, "studio": studio,
                "url": href, "thumb": thumb, "duration": duration,
                "views": views, "likes": "",
            })

        scenes = [s for s in scenes if not _COMPILATION_RE.search(s.get("title", ""))]

        if not profile_url:
            named  = [s for s in scenes if first in s["title"].lower()]
            others = [s for s in scenes if s not in named]
            scenes = named + others

        scenes.sort(key=lambda s: _date_to_days(s.get("date", "")))
        return scenes[:6]

    except Exception:
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug(name: str, sep: str = "-") -> str:
    return name.strip().lower().replace(" ", sep)


def _slug_caps(name: str) -> str:
    """Title-cased underscore slug: 'leana lovings' -> 'Leana_Lovings'"""
    return "_".join(w.capitalize() for w in name.strip().split())


def _date_to_days(date_str: str) -> int:
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


def _parse_info(info: str) -> dict[str, str]:
    """Parse 'Age: 30 · Last booked: Oct 2025 · Bookings: 3 · Location: Vegas'"""
    result = {"age": "", "last_booked": "", "bookings_count": "", "location": ""}
    if not info:
        return result
    parts = re.split(r"\s*[·•\-]\s*", info)
    for part in parts:
        part = part.strip()
        if part.lower().startswith("age:"):
            result["age"] = part[4:].strip()
        elif part.lower().startswith("last booked:"):
            result["last_booked"] = part[12:].strip()
        elif part.lower().startswith("bookings:"):
            result["bookings_count"] = part[9:].strip()
        elif part.lower().startswith("location:"):
            result["location"] = part[9:].strip()
    return result


def _months_since_booked(last_booked: str) -> Optional[int]:
    if not last_booked:
        return None
    now = datetime.now(timezone.utc)
    for fmt in ("%b %Y", "%B %Y", "%m/%Y", "%Y"):
        try:
            dt = datetime.strptime(last_booked.strip(), fmt)
            months = (now.year - dt.year) * 12 + (now.month - dt.month)
            return max(0, months)
        except ValueError:
            continue
    return None


def _opportunity_score(rank: str, last_booked: str) -> int:
    rank_map = {"great": 25, "good": 18, "moderate": 10, "poor": 3}
    rank_score = rank_map.get(rank.lower().strip(), 0)
    months = _months_since_booked(last_booked)
    if months is None:
        urgency_score = 30
    elif months > 36:
        urgency_score = 28
    elif months > 24:
        urgency_score = 22
    elif months > 12:
        urgency_score = 15
    elif months > 6:
        urgency_score = 8
    else:
        urgency_score = 3
    return round((rank_score + urgency_score) / 55 * 100)


def _row_to_model(row: dict) -> ModelResponse:
    info = row.get("info", "") or ""
    parsed = _parse_info(info)
    rank = row.get("rank", "") or ""
    score = _opportunity_score(rank, parsed["last_booked"])

    return ModelResponse(
        name=row.get("name", ""),
        agency=row.get("agency", ""),
        agency_link=row.get("agency_link", ""),
        rate=row.get("rate", ""),
        rank=rank,
        notes=row.get("notes", ""),
        info=info,
        age=parsed["age"],
        last_booked=parsed["last_booked"],
        bookings_count=parsed["bookings_count"],
        location=parsed["location"],
        opportunity_score=score,
    )
