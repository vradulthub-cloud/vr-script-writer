"""
asset_tracker.py
Builds unified per-scene asset status by joining Grail + Scripts + MEGA scan + Approvals.
"""

import json
import logging as _log
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from google.oauth2.service_account import Credentials
import gspread

# ── Configuration ─────────────────────────────────────────────────────────────
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

GRAIL_SHEET_ID = "1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk"
SCRIPTS_SHEET_ID = "1cY-8zNHLmD-oWdyEa2Mt3VY3nsFXHLEeZx0n42uf3ZQ"
MEGA_SCAN_PATH = os.path.join(os.path.dirname(__file__), "mega_scan.json")

STUDIO_TABS = {
    "VRH": "VRHush",
    "FPVR": "FuckPassVR",
    "VRA": "VRAllure",
    "NNJOI": "NaughtyJOI",
}

STUDIO_MAP_SCRIPTS = {
    "FuckPassVR": "FPVR", "FuckpassVR": "FPVR", "fuckpassvr": "FPVR",
    "VRHush": "VRH", "vrhush": "VRH",
    "VRAllure": "VRA", "vrallure": "VRA",
    "NaughtyJOI": "NJOI", "naughtyjoi": "NJOI",
}

# All tracked asset types
ASSET_KEYS = [
    "has_title", "has_description", "has_categories",
    "has_tags", "has_videos", "has_thumbnail", "has_photos",
]

# Map Grail tab names to Scripts sheet studio codes
_TAB_TO_SCRIPT_CODE = {"NNJOI": "NJOI", "FPVR": "FPVR", "VRH": "VRH", "VRA": "VRA"}

# ── Sheet client ─────────────────────────────────────────────────────────────
_cached_client = None
_cached_at = 0


def _get_client():
    global _cached_client, _cached_at
    now = time.time()
    if _cached_client and (now - _cached_at) < 1800:
        return _cached_client
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    _cached_client = gspread.authorize(creds)
    _cached_at = now
    return _cached_client


def _retry_api(func, max_retries=3, base_sleep=5):
    """Retry a gspread call on 429 quota errors with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func()
        except gspread.exceptions.APIError as exc:
            if "429" in str(exc) and attempt < max_retries - 1:
                wait = base_sleep * (2 ** attempt)  # 5, 10, 20 seconds
                _log.warning("Sheets 429 – waiting %ds (attempt %d)", wait, attempt + 1)
                time.sleep(wait)
            else:
                raise


# ── Data loaders ─────────────────────────────────────────────────────────────

def bust_caches():
    """Reset all module-level caches. Called when user clicks Refresh."""
    global _scripts_cache, _scripts_cache_at, _mega_cache, _mega_cache_at
    _scripts_cache = None
    _scripts_cache_at = 0
    _mega_cache = None
    _mega_cache_at = 0

_scripts_cache = None
_scripts_cache_at = 0
_SCRIPTS_TTL = 600  # 10 min — scripts change infrequently


def _load_scripts_lookup():
    """Build lookup of (studio|female) → {plot, theme, script_title} from Scripts sheet.
    Cached at module level for 10 minutes to avoid redundant API calls."""
    global _scripts_cache, _scripts_cache_at
    now = time.time()
    if _scripts_cache is not None and (now - _scripts_cache_at) < _SCRIPTS_TTL:
        return _scripts_cache

    gc = _get_client()
    sh = _retry_api(lambda: gc.open_by_key(SCRIPTS_SHEET_ID))
    lookup = {}

    today = date.today()
    months = [today.strftime("%B %Y")]
    prev = today.replace(day=1) - timedelta(days=1)
    months.append(prev.strftime("%B %Y"))

    for month_name in months:
        try:
            ws = sh.worksheet(month_name)
            rows = _retry_api(ws.get_all_values)
            for r in rows[1:]:
                studio_raw = r[1].strip() if len(r) > 1 else ""
                female = r[4].strip() if len(r) > 4 else ""
                theme = r[6].strip() if len(r) > 6 else ""
                plot = r[9].strip() if len(r) > 9 else ""
                title = r[10].strip() if len(r) > 10 else ""
                if female:
                    scode = STUDIO_MAP_SCRIPTS.get(studio_raw, studio_raw.upper())
                    data = {"plot": plot, "theme": theme, "script_title": title}
                    if plot:
                        lookup[f"{scode}|{female.lower()}"] = data
                    lookup[female.lower()] = data
        except Exception:
            pass
    _scripts_cache = lookup
    _scripts_cache_at = time.time()
    return lookup


_mega_cache = None
_mega_cache_at = 0
_MEGA_TTL = 3600  # 1 hour — scan runs once daily, no need to re-read often


def _load_mega_scan():
    """Load MEGA scan data into a lookup by scene_id. Cached for 1 hour."""
    global _mega_cache, _mega_cache_at
    now = time.time()
    if _mega_cache is not None and (now - _mega_cache_at) < _MEGA_TTL:
        return _mega_cache

    lookup = {}
    scan_date = ""
    try:
        if os.path.exists(MEGA_SCAN_PATH):
            with open(MEGA_SCAN_PATH) as f:
                scan = json.load(f)
            scan_date = scan.get("scanned_at", "")[:10]
            for s in scan.get("scenes", []):
                sid = s.get("scene_id", s.get("id", ""))
                lookup[sid] = s
                if sid:
                    lookup[sid.lower()] = s
    except Exception:
        pass
    result = (lookup, scan_date)
    _mega_cache = result
    _mega_cache_at = time.time()
    return result


def _find_mega_entry(mega_lookup, site_code, tab, scene_num):
    """Try various ID formats to find a MEGA scan entry."""
    sid = f"{site_code}{scene_num}"
    for try_id in [sid, sid.lower(), f"{tab}{scene_num}", f"{tab.lower()}{scene_num}"]:
        if try_id in mega_lookup:
            return mega_lookup[try_id]
    if scene_num:
        padded = scene_num.zfill(4)
        for try_id in [f"{site_code}{padded}", f"{tab}{padded}",
                        f"{site_code.lower()}{padded}", f"{tab.lower()}{padded}"]:
            if try_id in mega_lookup:
                return mega_lookup[try_id]
    return None


def _load_pending_approvals():
    """Load pending approvals indexed by scene_id."""
    try:
        import approval_tools
        pending = approval_tools.load_approvals(status_filter="Pending")
        by_scene = {}
        for a in pending:
            sid = a["scene_id"]
            by_scene.setdefault(sid, []).append(a)
        return by_scene
    except Exception:
        return {}


# ── Main loader ──────────────────────────────────────────────────────────────

def load_asset_status(studios=None, limit_per_studio=20, cached_approvals=None):
    """Build unified asset status for recent scenes across all studios.

    Args:
        cached_approvals: Pre-loaded approvals list to avoid redundant API call.
                          If None, loads from approval_tools directly.

    Returns: {
        "VRH": [{"scene_id": ..., "has_script": True, ...}, ...],
        "FPVR": [...],
        "_meta": {"scan_date": "2026-04-08"}
    }
    """
    gc = _get_client()
    grail = _retry_api(lambda: gc.open_by_key(GRAIL_SHEET_ID))

    # Load scripts, mega, and approvals — scripts may hit API so run in parallel
    mega_lookup, scan_date = _load_mega_scan()  # cached, instant after first call
    if cached_approvals is not None:
        pending_by_scene = {}
        for a in cached_approvals:
            if a.get("status") == "Pending":
                sid = a["scene_id"]
                pending_by_scene.setdefault(sid, []).append(a)
    else:
        pending_by_scene = _load_pending_approvals()

    studio_list = studios or list(STUDIO_TABS.keys())

    # Fetch all Grail studio tabs in parallel — biggest performance win
    def _fetch_tab(tab_name):
        try:
            ws = _retry_api(lambda: grail.worksheet(tab_name))
            return tab_name, _retry_api(ws.get_all_values)
        except Exception:
            return tab_name, None

    with ThreadPoolExecutor(max_workers=len(studio_list)) as pool:
        # Run scripts lookup concurrently with Grail reads
        scripts_future = pool.submit(_load_scripts_lookup)
        tab_futures = {tab: pool.submit(_fetch_tab, tab) for tab in studio_list}
        plot_lookup = scripts_future.result()
        tab_data = {tab: fut.result() for tab, fut in tab_futures.items()}

    results = {"_meta": {"scan_date": scan_date}}

    for tab in studio_list:
        _, all_rows = tab_data.get(tab, (tab, None))
        if all_rows is None:
            results[tab] = []
            continue
        studio_name = STUDIO_TABS.get(tab, tab)
        try:
            data_rows = [(i, r) for i, r in enumerate(all_rows[1:], start=2)
                         if len(r) > 1 and r[1].strip()]
            recent = data_rows[-limit_per_studio:]

            scenes = []
            for row_num, r in recent:
                site_code = r[0].strip().upper() if r[0] else tab
                scene_num = r[1].strip() if len(r) > 1 else ""
                sid = f"{site_code}{scene_num}"
                release_date = r[2].strip() if len(r) > 2 else ""
                title = r[3].strip() if len(r) > 3 else ""
                performers = r[4].strip() if len(r) > 4 else ""
                cats = r[5].strip() if len(r) > 5 else ""
                tags = r[6].strip() if len(r) > 6 else ""
                female = performers.split(",")[0].strip() if performers else ""
                perf_count = len([p.strip() for p in performers.split(",") if p.strip()])

                # Detect compilations: "Vol." in title or 4+ performers
                is_comp = ("Vol." in title) or (perf_count >= 4)

                # Scripts sheet lookup (use mapped code for NNJOI→NJOI etc.)
                _script_code = _TAB_TO_SCRIPT_CODE.get(tab, tab)
                script_data = plot_lookup.get(f"{_script_code}|{female.lower()}",
                              plot_lookup.get(f"{tab}|{female.lower()}", {}))

                # MEGA scan lookup
                mega_entry = _find_mega_entry(mega_lookup, site_code, tab, scene_num)

                # Build asset status
                has_title = bool(title)
                has_cats = bool(cats)
                has_tags = bool(tags)
                has_desc = bool(mega_entry.get("has_description")) if mega_entry else False
                has_videos = bool(mega_entry.get("has_videos")) if mega_entry else False
                has_thumbnail = bool(mega_entry.get("has_thumbnail")) if mega_entry else False
                has_photos = bool(mega_entry.get("has_photos")) if mega_entry else False
                # Count completed assets
                asset_checks = [
                    has_title, has_desc, has_cats,
                    has_tags, has_videos, has_thumbnail, has_photos,
                ]
                completed = sum(asset_checks)
                total = len(asset_checks)

                # Missing list
                missing = []
                if not has_title:      missing.append("title")
                if not has_desc:       missing.append("description")
                if not has_cats:       missing.append("categories")
                if not has_tags:       missing.append("tags")
                if not has_videos:     missing.append("videos")
                if not has_thumbnail:  missing.append("thumbnail")
                if not has_photos:     missing.append("photos")

                # File details from mega scan
                mega_files = mega_entry.get("files", {}) if mega_entry else {}
                thumb_files = mega_files.get("thumbnail", [])
                video_files = mega_files.get("videos", [])
                photo_files = mega_files.get("photos", [])
                desc_files = mega_files.get("description", [])
                story_files = mega_files.get("storyboard", [])

                scenes.append({
                    "scene_id": sid,
                    "scene_num": scene_num,
                    "studio": tab,
                    "studio_name": studio_name,
                    "release_date": release_date,
                    "performers": performers,
                    "female": female,
                    "title": title,
                    "is_compilation": is_comp,
                    "theme": script_data.get("theme", ""),
                    "plot_preview": script_data.get("plot", "")[:100],
                    # Asset booleans
                    "has_title": has_title,
                    "has_description": has_desc,
                    "has_categories": has_cats,
                    "has_tags": has_tags,
                    "categories_raw": cats,
                    "tags_raw": tags,
                    "has_videos": has_videos,
                    "has_thumbnail": has_thumbnail,
                    "has_photos": has_photos,
                    # Counts
                    "completed": completed,
                    "total": total,
                    "missing": missing,
                    # File details
                    "mega_files": {
                        "thumbnail": thumb_files,
                        "videos": video_files,
                        "photos": photo_files,
                        "description": desc_files,
                        "storyboard": story_files,
                    },
                    "video_count": mega_entry.get("video_count", 0) if mega_entry else 0,
                    "storyboard_count": mega_entry.get("storyboard_count", 0) if mega_entry else 0,
                    # Pending approvals
                    "pending_approvals": pending_by_scene.get(sid, []),
                    # Row refs for linking
                    "grail_row": row_num,
                    "grail_tab": tab,
                })
            results[tab] = scenes
        except Exception as e:
            results[tab] = []

    return results
