"""
Models API router.

Routes:
  GET  /api/models/                  — list all models with sheet stats
  GET  /api/models/trending          — trending performers from SLR + VRPorn (cached 6h)
  GET  /api/models/{name}            — single model
  GET  /api/models/{name}/photo      — proxied model photo (public, no auth)
  GET  /api/models/{name}/profile    — full profile: bio, photo, recent scenes (cached 7d)
  POST /api/models/{name}/brief      — AI booking brief (Claude)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from api.auth import CurrentUser
from api.database import get_db

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])

# ---------------------------------------------------------------------------
# Scraper headers + filters
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
    rank: str
    notes: str
    info: str
    age: str
    last_booked: str
    bookings_count: str
    location: str
    opportunity_score: int
    # All sheet columns passed through (platform stats, social, SLR/VRP profile URLs)
    sheet_data: dict[str, str] = {}


class SceneResult(BaseModel):
    title: str = ""
    date: str = ""
    studio: str = ""
    url: str = ""
    thumb: str = ""
    duration: str = ""
    views: str = ""
    likes: str = ""
    comments: str = ""


class BookingHistory(BaseModel):
    total: int = 0
    last_date: str = ""       # ISO date string from scripts table
    last_display: str = ""    # "Mar 2026 (2 mo ago)"
    studios: dict[str, int] = {}   # studio → count


class ProfileResponse(BaseModel):
    name: str
    photo_url: str = ""
    bio: dict[str, str] = {}
    slr_profile_url: str = ""
    slr_scenes: list[SceneResult] = []
    vrp_profile_url: str = ""
    vrp_scenes: list[SceneResult] = []
    booking_history: BookingHistory = BookingHistory()
    cached_at: str = ""


class TrendingModel(BaseModel):
    name: str
    photo_url: str = ""
    platform: str = ""        # "SLR" or "VRP"
    profile_url: str = ""
    scenes: str = ""
    followers: str = ""
    views: str = ""


class BriefRequest(BaseModel):
    context: dict[str, str] = {}


class BriefResponse(BaseModel):
    brief: str


# ---------------------------------------------------------------------------
# Routes — list / trending / get
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[ModelResponse])
async def list_models(
    user: CurrentUser,
    search: Optional[str] = Query(default=None),
):
    query = "SELECT name, agency, agency_link, rate, rank, notes, info, raw_json FROM bookings WHERE 1=1"
    params: list = []
    if search:
        query += " AND (name LIKE ? OR agency LIKE ? OR notes LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    query += " ORDER BY name ASC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_model(dict(r)) for r in rows]


@router.get("/trending", response_model=list[TrendingModel])
async def get_trending_models(
    user: CurrentUser,
    n: int = Query(default=10, le=20),
    refresh: bool = Query(default=False),
):
    """Trending performers from SLR + VRPorn. Cached 6h in SQLite."""
    CACHE_NAME = "_trending_cache"

    if not refresh:
        with get_db() as conn:
            cached = conn.execute(
                "SELECT profile_json, cached_at FROM model_profiles WHERE name = ?",
                (CACHE_NAME,),
            ).fetchone()
        if cached:
            try:
                ts = datetime.fromisoformat(cached["cached_at"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - ts < timedelta(hours=6):
                    data = json.loads(cached["profile_json"])
                    return [TrendingModel(**m) for m in data[:n]]
            except Exception:
                pass

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, _scrape_trending, n)

    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO model_profiles (name, profile_json, cached_at)
               VALUES (?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                 profile_json = excluded.profile_json,
                 cached_at    = excluded.cached_at""",
            (CACHE_NAME, json.dumps([m.model_dump() for m in results]), now_iso),
        )

    return results[:n]


@router.get("/{name}/photo")
async def get_model_photo(name: str):
    """
    Serve a model's photo proxied through the server.

    Public endpoint (no auth) — used as <img src> in the frontend.
    Tries in order: cached profile photo, VRPorn CDN, Babepedia.
    Returns image bytes with 24h cache header, or 404.
    """
    import requests as _req

    # 1. Check cached profile for a photo URL
    photo_url = ""
    with get_db() as conn:
        cached = conn.execute(
            "SELECT profile_json FROM model_profiles WHERE LOWER(name) = LOWER(?) AND name != '_trending_cache'",
            (name,),
        ).fetchone()
    if cached:
        try:
            data = json.loads(cached["profile_json"])
            photo_url = data.get("photo_url", "") or ""
        except Exception:
            pass

    # 2. If no cached photo, try known URL patterns
    if not photo_url:
        candidates = [
            f"https://cdn.vrporn.com/models/{_slug(name)}/photo.jpg",
            f"https://www.babepedia.com/pics/{_slug_caps(name)}.jpg",
            f"https://www.babepedia.com/pics/{name.strip().replace(' ', '_')}.jpg",
        ]
        for url in candidates:
            try:
                hr = _req.head(url, timeout=5, headers=_HEADERS, allow_redirects=True)
                ct = hr.headers.get("content-type", "")
                if hr.status_code == 200 and "image" in ct:
                    photo_url = url
                    break
            except Exception:
                pass

    if not photo_url:
        raise HTTPException(status_code=404, detail="No photo found")

    # 3. Fetch and proxy the image bytes
    try:
        r = _req.get(photo_url, timeout=10, headers=_HEADERS, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 500:
            ct = r.headers.get("content-type", "image/jpeg")
            return Response(
                content=r.content,
                media_type=ct,
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Photo fetch failed")


@router.get("/{name}/profile", response_model=ProfileResponse)
async def get_model_profile(
    name: str,
    user: CurrentUser,
    refresh: bool = Query(default=False),
):
    """Full performer profile: bio, photo, SLR + VRPorn scenes. 7-day cache."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT name, agency_link, raw_json FROM bookings WHERE LOWER(name) = LOWER(?)",
            (name,),
        ).fetchone()

    # Model may not be in bookings (e.g. trending / searched) — still scrape
    canonical = row["name"] if row else name.strip()
    agency_link = (row["agency_link"] if row else "") or ""

    # Parse sheet_data for SLR/VRP profile URLs
    try:
        sd = json.loads((row["raw_json"] if row else "") or "{}")
        if not isinstance(sd, dict):
            sd = {}
    except Exception:
        sd = {}
    slr_hint = sd.get("slr profile url", "") or sd.get("slr_profile_url", "") or (
        agency_link if "sexlikereal" in agency_link.lower() else ""
    )

    # Booking history from scripts table
    booking_history = _get_booking_history(canonical)

    # Cache check (exclude the trending aggregate row)
    if not refresh:
        with get_db() as conn:
            cached = conn.execute(
                "SELECT profile_json, cached_at FROM model_profiles WHERE LOWER(name) = LOWER(?) AND name != '_trending_cache'",
                (canonical,),
            ).fetchone()
        if cached:
            try:
                ts = datetime.fromisoformat(cached["cached_at"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - ts < timedelta(days=7):
                    data = json.loads(cached["profile_json"])
                    data["booking_history"] = booking_history.model_dump()
                    data["cached_at"] = cached["cached_at"]
                    return ProfileResponse(**data)
            except Exception:
                pass

    # Scrape in parallel
    loop = asyncio.get_event_loop()
    babe_fut = loop.run_in_executor(None, _scrape_babepedia, canonical)
    vrp_fut  = loop.run_in_executor(None, _scrape_vrporn, canonical)
    slr_fut  = loop.run_in_executor(None, _scrape_slr_scenes, canonical, slr_hint)
    babe_data, vrp_data, slr_scenes = await asyncio.gather(babe_fut, vrp_fut, slr_fut)

    bio: dict[str, str] = {}
    bio.update(vrp_data.get("bio", {}))
    skip = {"source_url", "photo_url", "about", "_ts"}
    bio.update({k: v for k, v in babe_data.items() if k not in skip and isinstance(v, str) and v})
    if babe_data.get("about"):
        bio["about"] = babe_data["about"]

    # Prefer VRPorn CDN photo (no hotlink block); fall back to Babepedia
    photo_url = vrp_data.get("photo", "") or babe_data.get("photo_url", "") or ""
    slr_profile_url = slr_hint or f"https://sexlikereal.com/stars/{_slug(canonical)}"
    vrp_profile_url = f"https://vrporn.com/pornstars/{_slug(canonical)}/"

    now_iso = datetime.now(timezone.utc).isoformat()
    cache_payload = {
        "name": canonical,
        "photo_url": photo_url,
        "bio": bio,
        "slr_profile_url": slr_profile_url,
        "slr_scenes": slr_scenes,
        "vrp_profile_url": vrp_profile_url,
        "vrp_scenes": vrp_data.get("scenes", []),
        "cached_at": now_iso,
    }

    with get_db() as conn:
        conn.execute(
            """INSERT INTO model_profiles (name, profile_json, cached_at)
               VALUES (?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                 profile_json = excluded.profile_json,
                 cached_at    = excluded.cached_at""",
            (canonical, json.dumps(cache_payload), now_iso),
        )

    return ProfileResponse(
        **cache_payload,
        booking_history=booking_history,
    )


@router.post("/{name}/brief", response_model=BriefResponse)
async def generate_booking_brief(
    name: str,
    user: CurrentUser,
    body: BriefRequest,
):
    """Generate a 3-sentence AI booking brief using Claude."""
    try:
        import anthropic
        from api.config import get_settings
        settings = get_settings()

        ctx_lines = [f"Performer: {name}"]
        for k, v in body.context.items():
            if v:
                ctx_lines.append(f"{k}: {v}")

        prompt = (
            "You are a talent booking advisor for a VR adult content studio. "
            "Based on the data below, write a concise 3-sentence booking brief. "
            "Cover: (1) her current market standing and platform performance, "
            "(2) your studio's history with her and what that means, "
            "(3) a clear recommendation — Book Now / Re-book / Monitor / Pass — with one-line reason.\n\n"
            + "\n".join(ctx_lines)
        )

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return BriefResponse(brief=msg.content[0].text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}", response_model=ModelResponse)
async def get_model(name: str, user: CurrentUser):
    with get_db() as conn:
        row = conn.execute(
            "SELECT name, agency, agency_link, rate, rank, notes, info, raw_json FROM bookings WHERE LOWER(name) = LOWER(?)",
            (name,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Model '{name}' not found")
    return _row_to_model(dict(row))


# ---------------------------------------------------------------------------
# Booking history helper
# ---------------------------------------------------------------------------

def _get_booking_history(name: str) -> BookingHistory:
    """Derive booking history from the scripts table."""
    try:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT studio, shoot_date FROM scripts
                   WHERE female LIKE ? ORDER BY shoot_date DESC""",
                (f"%{name}%",),
            ).fetchall()

        if not rows:
            return BookingHistory()

        studios: dict[str, int] = {}
        for r in rows:
            s = (r["studio"] or "").strip()
            if s:
                studios[s] = studios.get(s, 0) + 1

        last_date = rows[0]["shoot_date"] or ""
        last_display = ""
        if last_date:
            try:
                ld = datetime.fromisoformat(last_date)
                months_ago = int((datetime.now() - ld).days / 30.44)
                last_display = f"{ld.strftime('%b %Y')} ({months_ago} mo ago)"
            except Exception:
                last_display = last_date

        return BookingHistory(
            total=len(rows),
            last_date=last_date,
            last_display=last_display,
            studios=studios,
        )
    except Exception:
        return BookingHistory()


# ---------------------------------------------------------------------------
# Scraper: trending models
# ---------------------------------------------------------------------------

def _scrape_trending(n: int = 10) -> list[TrendingModel]:
    """Scrape SLR + VRPorn trending/popular performer pages."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    results: list[TrendingModel] = []
    seen: set[str] = set()
    _NUM_RE = re.compile(r'(\d[\d,\.]*\s*[KMB]?)', re.I)

    def _stat(text: str) -> str:
        m = _NUM_RE.search(text)
        return m.group(1).replace(",", "").strip() if m else ""

    def _add(name: str, photo: str, platform: str, url: str = "",
             scenes: str = "", followers: str = "", views: str = ""):
        key = name.strip().lower()
        if key in seen or len(key) < 3:
            return
        if re.match(r'^[A-Z]{2,}$', name.strip()) or name.strip().isdigit():
            return
        if photo and not photo.endswith(".svg") and not photo.endswith(".gif"):
            seen.add(key)
            results.append(TrendingModel(
                name=name.strip(), photo_url=photo, platform=platform,
                profile_url=url, scenes=scenes, followers=followers, views=views,
            ))

    # SLR popular stars
    try:
        for url in ["https://sexlikereal.com/stars/?ordering=most_popular", "https://sexlikereal.com/stars/"]:
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
                           card.select_one("[class*='name']") or card.select_one("[class*='title']"))
                name = name_el.get_text(strip=True) if name_el else (
                    card.get("title", "") or card.get("aria-label", ""))
                img = card.select_one("img[src]") or card.select_one("img[data-src]")
                photo = ""
                if img:
                    photo = img.get("src") or img.get("data-src") or ""
                    if photo and not photo.startswith("http"):
                        photo = "https://sexlikereal.com" + photo
                link = card if card.name == "a" else card.select_one("a[href]")
                href = link.get("href", "") if link else ""
                if href and not href.startswith("http"):
                    href = "https://sexlikereal.com" + href
                card_text = card.get_text(separator="|", strip=True)
                sc = fl = vi = ""
                for part in card_text.split("|"):
                    pl = part.lower()
                    if any(w in pl for w in ("video", "scene", "film")) and not sc:
                        sc = _stat(part)
                    elif any(w in pl for w in ("follower", "fan")) and not fl:
                        fl = _stat(part)
                    elif "view" in pl and not vi:
                        vi = _stat(part)
                _add(name, photo, "SLR", href, sc, fl, vi)
                if len(results) >= n:
                    break
            if results:
                break
    except Exception:
        pass

    # VRPorn popular performers
    if len(results) < n:
        try:
            for url in ["https://vrporn.com/pornstars/?filter=popular", "https://vrporn.com/pornstars/"]:
                r = requests.get(url, headers=_HEADERS, timeout=20, allow_redirects=True)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                cards = (soup.select("article") or
                         soup.select("[class*='pornstar']") or
                         soup.select("[class*='model-card']"))
                for card in cards[:n * 2]:
                    name_el = (card.select_one("h2") or card.select_one("h3") or
                               card.select_one("[class*='name']") or card.select_one("[class*='title']"))
                    name = name_el.get_text(strip=True) if name_el else ""
                    img = card.select_one("img[src]") or card.select_one("img[data-src]")
                    photo = ""
                    if img:
                        photo = img.get("src") or img.get("data-src") or ""
                        if photo and not photo.startswith("http"):
                            photo = "https://vrporn.com" + photo
                    link = card if card.name == "a" else card.select_one("a[href]")
                    href = link.get("href", "") if link else ""
                    if href and not href.startswith("http"):
                        href = "https://vrporn.com" + href
                    card_text = card.get_text(separator="|", strip=True)
                    sc = fl = vi = ""
                    for part in card_text.split("|"):
                        pl = part.lower()
                        if any(w in pl for w in ("video", "scene", "film")) and not sc:
                            sc = _stat(part)
                        elif any(w in pl for w in ("follower", "fan")) and not fl:
                            fl = _stat(part)
                        elif "view" in pl and not vi:
                            vi = _stat(part)
                    _add(name, photo, "VRP", href, sc, fl, vi)
                    if len(results) >= n:
                        break
                if results:
                    break
        except Exception:
            pass

    return results[:n]


# ---------------------------------------------------------------------------
# Scraper: Babepedia
# ---------------------------------------------------------------------------

def _scrape_babepedia(name: str) -> dict:
    try:
        import cloudscraper
        from bs4 import BeautifulSoup

        cs = cloudscraper.create_scraper()
        slug = _slug_caps(name)
        url = f"https://www.babepedia.com/babe/{slug}"
        r = cs.get(url, timeout=20)

        if r.status_code != 200 or "search results" in r.text[:3000].lower():
            r = cs.get(f"https://www.babepedia.com/babe/{name.strip().replace(' ', '_')}", timeout=20)
        if r.status_code != 200 or "search results" in r.text[:3000].lower():
            return {}

        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        data: dict = {"source_url": url}

        ALL_LABELS = [
            "Age", "Born", "Years active", "Birthplace", "Nationality",
            "Ethnicity", "Professions", "Sexuality", "Hair color", "Eye color",
            "Height", "Weight", "Body type", "Measurements", "Bra/cup size",
            "Boobs", "Pubic hair", "Instagram", "Achievements",
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
                val = re.sub(r'\s+', ' ', m.group(1).replace("\n", " ")).strip()
                val = _BABE_SECTION_NOISE.sub('', val).strip()
                if val and len(val) < 300:
                    data[label.lower().replace("/", "_").replace(" ", "_")] = val

        if "bra_cup_size" in data:
            data["bra_cup_size"] = re.sub(r'\s+show\s+conversions.*', '', data["bra_cup_size"], flags=re.I).strip()

        for src, dst in [("born", "birthday"), ("hair_color", "hair"), ("eye_color", "eyes"),
                         ("years_active", "years active"), ("bra_cup_size", "bra/cup size"),
                         ("body_type", "body type")]:
            if src in data:
                data[dst] = data.pop(src)

        about_m = re.search(
            r'About\s+' + re.escape(name.split()[0]) + r'[^\n]*\n(.*?)(?=\nShow more|\n\n\n|\Z)',
            text, re.IGNORECASE | re.DOTALL,
        )
        if about_m:
            about = re.sub(r'\s+', ' ', about_m.group(1).replace("\n", " ")).strip()
            data["about"] = about[:500]

        import requests as _req
        photo_url = ""
        for slug_v in (_slug_caps(name), name.strip().replace(" ", "_")):
            try:
                hr = _req.head(f"https://www.babepedia.com/pics/{slug_v}.jpg", timeout=5, headers=_HEADERS)
                if hr.status_code == 200:
                    photo_url = f"https://www.babepedia.com/pics/{slug_v}.jpg"
                    break
            except Exception:
                pass
        if not photo_url:
            og = soup.select_one('meta[property="og:image"]')
            if og and og.get("content") and "/pics/" in og["content"]:
                photo_url = og["content"]
        data["photo_url"] = photo_url
        return data
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Scraper: VRPorn
# ---------------------------------------------------------------------------

def _scrape_vrporn(name: str) -> dict:
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

        bio: dict[str, str] = {}
        bio_sec = soup.select_one("[class*='pornstar']")
        if bio_sec:
            parts = bio_sec.get_text(separator="|", strip=True).split("|")
            KEY_MAP = {
                "birthday": "birthday", "birthdate": "birthday",
                "ethnicity": "ethnicity", "height": "height", "weight": "weight",
                "place of birth": "birthplace", "birthplace": "birthplace",
                "measurements": "measurements", "hair color": "hair", "hair": "hair",
                "eye color": "eyes", "eyes": "eyes", "shoe size": None,
            }
            i = 0
            while i < len(parts) - 1:
                label = re.sub(r'[\s:]+$', '', parts[i].strip()).strip().lower()
                value = parts[i + 1].strip()
                mapped = KEY_MAP.get(label)
                if mapped and value and value not in ("", "n/a"):
                    bio[mapped] = value
                    i += 2
                    continue
                i += 1

        # Profile photo — prefer og:image (CDN URL, no hotlink block)
        photo = ""
        og = soup.select_one('meta[property="og:image"]')
        if og and og.get("content"):
            p = og["content"]
            if p and "placeholder" not in p.lower() and not p.endswith(".svg"):
                photo = p
        if not photo:
            for sel in ["[class*='pornstar-profile'] img[src]", "[class*='performer'] img[src]"]:
                el = soup.select_one(sel)
                if el:
                    src = el.get("src", "")
                    if src and "placeholder" not in src.lower() and not src.endswith(".svg"):
                        photo = src if src.startswith("http") else "https://vrporn.com" + src
                        break

        scenes: list[dict] = []
        for art in soup.select("article")[:12]:
            links = art.find_all("a", href=True)
            title = href = ""
            for a in links:
                txt = a.get_text(strip=True)
                lnk = a.get("href", "")
                if txt and len(txt) > 3 and "/studio/" not in lnk and "/pornstar" not in lnk:
                    title = txt; href = lnk; break

            studio = date = ""
            for span in art.find_all("span"):
                cls = " ".join(span.get("class", []))
                if "ui-video-card__text" in cls:
                    txt = span.get_text(strip=True)
                    if not txt:
                        continue
                    if "ago" in txt.lower() or any(m in txt for m in
                            ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]):
                        if not date: date = txt
                    elif not studio:
                        studio = txt

            dur_el = art.select_one("[class*='ui-time'], [class*='duration']")
            duration = dur_el.get_text(strip=True) if dur_el else ""

            views = likes = comments = ""
            footer = art.select_one("[class*='footer']")
            if footer:
                items = footer.select("[class*='footer-item']")
                if len(items) >= 2:
                    views = items[0].get_text(strip=True)
                    likes = items[1].get_text(strip=True)
                    comments = items[2].get_text(strip=True) if len(items) > 2 else ""

            img = art.select_one("img[src]")
            thumb = img["src"] if img else ""
            if href and not href.startswith("http"):
                href = "https://vrporn.com" + href

            if title:
                scenes.append({"title": title, "date": date, "studio": studio,
                                "url": href, "thumb": thumb, "duration": duration,
                                "views": views, "likes": likes, "comments": comments})

        scenes = [s for s in scenes if not _COMPILATION_RE.search(s.get("title", ""))]
        scenes.sort(key=lambda s: _date_to_days(s.get("date", "")))
        return {"bio": bio, "scenes": scenes[:6], "photo": photo}
    except Exception:
        return {"bio": {}, "scenes": [], "photo": ""}


# ---------------------------------------------------------------------------
# Scraper: SexLikeReal
# ---------------------------------------------------------------------------

def _scrape_slr_scenes(name: str, profile_url: str = "") -> list[dict]:
    try:
        import requests
        from bs4 import BeautifulSoup

        slug = _slug(name)
        first = name.strip().split()[0].lower()
        soup = None

        candidates = []
        if profile_url:
            candidates.append(profile_url)
        candidates += [f"https://sexlikereal.com/stars/{slug}", f"https://sexlikereal.com/stars/{slug}/"]

        for url in candidates:
            try:
                rp = requests.get(url, headers=_HEADERS, timeout=15, allow_redirects=True)
                if rp.status_code == 200 and "search results" not in rp.text[:3000].lower():
                    s = BeautifulSoup(rp.text, "html.parser")
                    if s.select("article"):
                        soup = s; break
            except Exception:
                pass

        if soup is None:
            q = name.strip().replace(" ", "+")
            for search_url in [f"https://sexlikereal.com/search/?q={q}&ordering=-release_date",
                                f"https://sexlikereal.com/search/?q={q}"]:
                try:
                    rs = requests.get(search_url, headers=_HEADERS, timeout=15, allow_redirects=True)
                    if rs.status_code == 200:
                        soup = BeautifulSoup(rs.text, "html.parser"); break
                except Exception:
                    pass

        if soup is None:
            return []

        _DATE_RE = re.compile(
            r'\b(\d+\s*(?:years?|months?|weeks?|days?|hours?)\s+ago|\d+(?:y|mo|w|d|h)\s+ago)', re.I)

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
                    studio = p.get_text(strip=True).replace(t_el.get_text(strip=True), "").strip(); break
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
            scenes.append({"title": title, "date": date, "studio": studio, "url": href,
                           "thumb": thumb, "duration": duration, "views": views, "likes": "", "comments": ""})

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

def _slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-")

def _slug_caps(name: str) -> str:
    return "_".join(w.capitalize() for w in name.strip().split())

def _date_to_days(date_str: str) -> int:
    if not date_str:
        return 999_999
    s = date_str.lower().strip()
    m = re.search(r'(\d+)', s)
    if not m:
        return 999_999
    n = int(m.group(1))
    if 'hour' in s or (s.endswith('h ago') and 'month' not in s): return 0
    if 'day' in s or s.endswith('d ago'):  return n
    if 'week' in s or s.endswith('w ago'): return n * 7
    if 'month' in s or 'mo' in s:          return n * 30
    if 'year' in s or s.endswith('y ago'): return n * 365
    return 999_999

def _parse_info(info: str) -> dict[str, str]:
    result = {"age": "", "last_booked": "", "bookings_count": "", "location": ""}
    if not info:
        return result
    for part in re.split(r"\s*[·•\-]\s*", info):
        part = part.strip()
        if part.lower().startswith("age:"):          result["age"] = part[4:].strip()
        elif part.lower().startswith("last booked:"): result["last_booked"] = part[12:].strip()
        elif part.lower().startswith("bookings:"):   result["bookings_count"] = part[9:].strip()
        elif part.lower().startswith("location:"):   result["location"] = part[9:].strip()
    return result

def _months_since_booked(last_booked: str) -> Optional[int]:
    if not last_booked:
        return None
    now = datetime.now(timezone.utc)
    for fmt in ("%b %Y", "%B %Y", "%m/%Y", "%Y"):
        try:
            dt = datetime.strptime(last_booked.strip(), fmt)
            return max(0, (now.year - dt.year) * 12 + (now.month - dt.month))
        except ValueError:
            continue
    return None

def _opportunity_score(rank: str, last_booked: str, sheet_data: dict) -> int:
    """Score using rank + urgency + platform pull (SLR/VRP followers) + activity."""
    def _parse_k(val: str) -> int:
        if not val: return 0
        val = val.upper().replace(",", "")
        try:
            if "K" in val: return int(float(val.replace("K","")) * 1000)
            if "M" in val: return int(float(val.replace("M","")) * 1_000_000)
            return int(float(val))
        except Exception: return 0

    rank_map = {"great": 25, "good": 18, "moderate": 10, "poor": 3}
    rank_pts = rank_map.get((rank or "").lower().strip(), 0)

    months = _months_since_booked(last_booked)
    if months is None:   urgency_pts = 30
    elif months > 36:    urgency_pts = 28
    elif months > 24:    urgency_pts = 22
    elif months > 12:    urgency_pts = 15
    elif months > 6:     urgency_pts = 8
    else:                urgency_pts = 3

    slr_f  = _parse_k(sheet_data.get("slr followers", ""))
    vrp_f  = _parse_k(sheet_data.get("vrp followers", ""))
    platform_pts = min(30, int((slr_f + vrp_f) / 4000))

    slr_sc = _parse_k(sheet_data.get("slr scenes", ""))
    vrp_v  = _parse_k(sheet_data.get("vrp views", ""))
    slr_v  = _parse_k(sheet_data.get("slr views", ""))
    activity_pts = min(15, int((slr_sc * 300 + vrp_v + slr_v) / 20000))

    return min(100, rank_pts + urgency_pts + platform_pts + activity_pts)

def _row_to_model(row: dict) -> ModelResponse:
    info = row.get("info", "") or ""
    parsed = _parse_info(info)
    rank = row.get("rank", "") or ""

    try:
        sheet_data = json.loads(row.get("raw_json") or "{}")
        if not isinstance(sheet_data, dict):
            sheet_data = {}
    except Exception:
        sheet_data = {}

    score = _opportunity_score(rank, parsed["last_booked"], sheet_data)

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
        sheet_data=sheet_data,
    )
