"""
booking_history.py — loads pre-built booking cache, provides query + scoring functions.
Cache file: booking_history_cache.json (in same directory as this script)
"""
import json, os, re
from datetime import datetime, date
from typing import Optional

_CACHE: dict = {}
_LOADED = False

def _load():
    global _CACHE, _LOADED
    if _LOADED:
        return
    _path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "booking_history_cache.json")
    if os.path.exists(_path):
        with open(_path, "r", encoding="utf-8") as f:
            _CACHE = json.load(f)
    _LOADED = True

def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", name.lower().strip())

def get_booking_history(name: str) -> Optional[dict]:
    """Return booking history dict for a performer, or None if not found."""
    _load()
    return _CACHE.get(_norm(name))

def _parse_k(val: str) -> int:
    """Parse '89.3K' or '89,300' or '89300' to int."""
    if not val:
        return 0
    val = str(val).upper().replace(",", "")
    try:
        if "K" in val:
            return int(float(val.replace("K", "")) * 1000)
        elif "M" in val:
            return int(float(val.replace("M", "")) * 1_000_000)
        return int(float(val))
    except Exception:
        return 0

def compute_opportunity_score(name: str, bk_data: dict) -> int:
    """
    Compute 0-100 opportunity score for booking a performer.
    bk_data: the data dict from the internal booking sheet (keys like 'slr followers', 'rank', etc.)

    Components:
    - Platform pull (0-30): SLR + VRPorn followers
    - Booking urgency (0-30): time since last booked with our studio (never = max)
    - Performance rank (0-25): great/good/moderate/poor from booking sheet
    - Platform activity (0-15): SLR scenes + VRPorn views
    """
    _load()
    hist = _CACHE.get(_norm(name), {})

    # 1. Platform pull (0-30)
    slr_f = _parse_k(bk_data.get("slr followers", "") or "")
    vrp_f = _parse_k(bk_data.get("vrp followers", "") or "")
    total_f = slr_f + vrp_f
    platform_pts = min(30, int(total_f / 4000))  # 120k followers = max 30pts

    # 2. Booking urgency (0-30)
    if not hist:
        urgency_pts = 30  # never booked = max urgency
    else:
        try:
            last = datetime.fromisoformat(hist["last_date"])
            months_ago = (datetime.now() - last).days / 30.44
            if months_ago > 36:   urgency_pts = 28
            elif months_ago > 24: urgency_pts = 22
            elif months_ago > 12: urgency_pts = 15
            elif months_ago > 6:  urgency_pts = 8
            else:                 urgency_pts = 3  # recently booked = low urgency
        except Exception:
            urgency_pts = 15

    # 3. Performance rank (0-25)
    rank_map = {"great": 25, "good": 18, "moderate": 10, "poor": 3}
    rank_pts = rank_map.get((bk_data.get("rank") or "").lower().strip(), 0)

    # 4. Platform activity (0-15)
    slr_scenes = _parse_k(bk_data.get("slr scenes", "") or "")
    vrp_views  = _parse_k(bk_data.get("vrp views", "") or "")
    slr_views  = _parse_k(bk_data.get("slr views", "") or "")
    activity_raw = slr_scenes * 300 + vrp_views + slr_views
    activity_pts = min(15, int(activity_raw / 20000))

    return min(100, platform_pts + urgency_pts + rank_pts + activity_pts)

def get_competitor_scenes(scenes: list, our_studios: set = None) -> list:
    """
    Filter a scenes list to only competitor studios.
    scenes: list of scene dicts with 'studio' key
    Returns list of {studio, title, date} for competitor bookings.
    """
    if our_studios is None:
        our_studios = {"fuckpassvr", "vrhush", "vrallure", "blowjobnow", "fpvr", "vr hush"}
    result = []
    seen_studios = {}
    for sc in scenes:
        studio = (sc.get("studio") or "").strip()
        if not studio:
            continue
        studio_key = studio.lower().replace(" ", "")
        if any(o in studio_key for o in our_studios):
            continue
        # Deduplicate: keep most recent per studio
        sc_date = sc.get("date", "")
        if studio not in seen_studios or sc_date > seen_studios[studio].get("date", ""):
            seen_studios[studio] = {"studio": studio, "title": sc.get("title", ""), "date": sc_date}
    result = sorted(seen_studios.values(), key=lambda x: x["date"], reverse=True)
    return result[:8]  # top 8 competitor studios
