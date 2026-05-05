"""
Revenue API router.

Surfaces the "Premium Breakdowns" Google Sheet — our consolidated revenue
ledger across SLR, POVR, and VRPorn (sourced from each platform's partner
portal exports). Admin-only because this is sensitive financial data.

Sheet layout we depend on:
  - "_Data" tab           → long-form fact table:
        Platform | Studio | YearMonth | Year | MonthNum | Revenue | Downloads
  - "All Video Analytics" → per-scene fact table:
        Platform | Studio | Year | Video ID | Title | Views | Revenue $
  - "🔗 Cross-Platform"   → matched titles spanning ≥2 platforms (raw text grid)

Aggregations are computed in Python rather than read from the dashboard
tabs so we stay one source-of-truth removed from the human-curated views.

Caching: 1-hour in-memory TTL — sheet is refreshed monthly so a stale-by-an-
hour read is fine; a Sheets call here costs ~3-5s (16 tabs, ~80k cells).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.auth import require_revenue_viewer
from api.sheets_client import open_revenue, with_retry

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/revenue", tags=["revenue"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class PlatformTotal(BaseModel):
    platform: str
    all_time: float
    ytd: float
    yearly: dict[str, float]  # year-string → revenue


class MonthlyPoint(BaseModel):
    month: str           # "2026-03"
    slr: float = 0.0
    povr: float = 0.0
    vrporn: float = 0.0
    total: float = 0.0
    mom_pct: Optional[float] = None  # null on the first point
    # Per-studio breakdown — populated for platforms that report studio-level
    # data (currently only SLR). Frontend uses this when a studio filter is
    # active to recompute per-platform contributions. Keys are 4-letter
    # studio codes (FPVR/VRH/VRA/NJOI/BJN); inner dict is platform-keyed.
    by_studio: dict[str, dict[str, float]] = {}


class CatalogIntel(BaseModel):
    platform: str
    total_scenes: int
    avg_revenue_per_scene: float
    top_scene_revenue: float = 0.0


class RevenueDashboard(BaseModel):
    grand_total: float
    ytd_total: float
    platforms: list[PlatformTotal]
    monthly_trend: list[MonthlyPoint]   # last 12 months
    catalog: list[CatalogIntel]
    refreshed_at: str                   # ISO timestamp of cache fill


class SceneRow(BaseModel):
    platform: str
    studio: str
    video_id: str
    title: str
    year: str = ""
    views: int = 0
    revenue: float = 0.0


class CrossPlatformRow(BaseModel):
    title: str
    studio: str = ""
    platforms: list[str]
    lifetime_total: float
    slr_total: float = 0.0
    povr_total: float = 0.0
    vrporn_total: float = 0.0
    povr_views: int = 0
    slr_id: str = ""
    povr_id: str = ""


class DailyRow(BaseModel):
    """One row of daily revenue per (date, platform, studio)."""
    date: str       # ISO YYYY-MM-DD
    platform: str   # "vrporn" / "povr" / "slr"
    studio: str     # "All" or specific studio
    revenue: float


class DailySummary(BaseModel):
    """Pre-computed snapshot for the dashboard's daily cards."""
    yesterday: list[DailyRow]            # all rows for the most recent date
    yesterday_date: str                  # ISO date of "yesterday" (most recent)
    yesterday_total: float               # summed across platforms
    this_month: list[DailyRow]           # daily rows from start-of-month → yesterday
    this_month_total: float
    refreshed_at: str


# ---------------------------------------------------------------------------
# Cache layer — single in-memory snapshot of the (small-ish) sheet data
# ---------------------------------------------------------------------------
# 15 min TTL: the daily Windows scheduled task pushes fresh CSVs into the
# sheet every morning. With a 1h cache the dashboard would lag by up to an
# hour after the refresh; 15min gets new data visible quickly without
# hammering Sheets API on every page load. Manual ?refresh=true bust still
# works for "show me the absolute latest".
_CACHE_TTL = 900

_lock = threading.Lock()
_cache: dict | None = None
_cache_at: float = 0


def _parse_money(s: str) -> float:
    """Strip $, commas, em-dashes, parens; return 0 for empty cells."""
    if not s:
        return 0.0
    t = s.strip().replace("$", "").replace(",", "").replace("—", "").replace("–", "")
    if not t or t == "-":
        return 0.0
    # accounting-style negatives in parens
    neg = t.startswith("(") and t.endswith(")")
    if neg:
        t = t[1:-1]
    try:
        v = float(t)
        return -v if neg else v
    except ValueError:
        return 0.0


def _parse_int(s: str) -> int:
    if not s:
        return 0
    t = s.strip().replace(",", "")
    try:
        return int(float(t))
    except (ValueError, TypeError):
        return 0


def _normalize_platform(raw: str) -> str:
    """Coerce sheet-name variants ('SLR', 'SexLikeReal', 'POVR', 'VRPorn') →
    canonical lower-case slugs the frontend uses."""
    r = (raw or "").strip().lower()
    if r in {"slr", "sexlikereal", "sex like real"}:
        return "slr"
    if r in {"povr"}:
        return "povr"
    if r in {"vrporn", "vrp"}:
        return "vrporn"
    return r


# Sheet uses long studio names ('FuckPassVR', 'VRHush'); UI uses 4-letter
# codes (FPVR, VRH). Normalizing here so studio filter can match per-studio
# monthly rollups end-to-end. Returns "" for non-studio rows (POVR/VRPorn
# aggregated rows that have studio == platform name) so they stay out of
# per-studio totals.
_STUDIO_NORMALIZE = {
    "fuckpassvr": "FPVR", "fpvr": "FPVR",
    "vrhush":     "VRH",  "vrh":  "VRH",
    "vrallure":   "VRA",  "vra":  "VRA",
    "naughtyjoi": "NJOI", "njoi": "NJOI", "nnjoi": "NJOI",
    "bjnow":      "BJN",  "bjn":  "BJN",
}


def _normalize_studio(raw: str) -> str:
    """Map studio names to 4-letter codes used by the UI. Empty string for
    platform-aggregated rows that don't represent a single studio (e.g.
    POVR's row.studio == 'POVR', VRPorn's row.studio == 'VRPorn')."""
    if not raw:
        return ""
    r = raw.strip().lower()
    return _STUDIO_NORMALIZE.get(r, "")


def _read_daily_rows(sh) -> list[DailyRow]:
    """Read the _DailyData tab. Returns [] if the tab doesn't exist yet."""
    try:
        ws = sh.worksheet("_DailyData")
    except Exception:
        return []
    rows = with_retry(lambda: ws.get_all_values())
    out: list[DailyRow] = []
    for r in rows[1:]:
        if len(r) < 4 or not r[0].strip():
            continue
        try:
            out.append(DailyRow(
                date=r[0].strip(),
                platform=r[1].strip().lower(),
                studio=r[2].strip(),
                revenue=_parse_money(r[3]),
            ))
        except Exception:
            continue
    return out


def _build_cache() -> dict:
    """Read the sheet once, build all aggregates we'll serve from. ~3-5s."""
    sh = open_revenue()

    # _Data — long-form (platform, studio, month) → revenue/downloads
    rows = with_retry(lambda: sh.worksheet("_Data").get_all_values())
    facts: list[dict] = []
    for r in rows[1:]:
        if len(r) < 6 or not r[0].strip():
            continue
        facts.append({
            "platform":  _normalize_platform(r[0]),
            "studio":    r[1].strip(),
            "year_month": r[2].strip(),
            "year":      _parse_int(r[3]),
            "revenue":   _parse_money(r[5]),
            "downloads": _parse_int(r[6]) if len(r) > 6 else 0,
        })

    # All Video Analytics — per-scene
    scene_rows = with_retry(lambda: sh.worksheet("All Video Analytics").get_all_values())
    scenes: list[SceneRow] = []
    for r in scene_rows[1:]:
        if len(r) < 7 or not r[0].strip():
            continue
        scenes.append(SceneRow(
            platform=_normalize_platform(r[0]),
            studio=r[1].strip(),
            year=r[2].strip(),
            video_id=r[3].strip(),
            title=r[4].strip(),
            views=_parse_int(r[5]),
            revenue=_parse_money(r[6]),
        ))

    # 🔗 Cross-Platform — multi-row text grid; first ~3 rows are header/blank,
    # then "Title|POVR ID|SLR ID|Studio|Platforms|POVR Share $|SLR Total $|
    # VRPorn $|Lifetime Total $|POVR Views|Scripts $|".
    xp_rows = with_retry(lambda: sh.worksheet("🔗 Cross-Platform").get_all_values())
    cross: list[CrossPlatformRow] = []
    in_data = False
    for r in xp_rows:
        if not r:
            continue
        first = (r[0] or "").strip()
        if first.lower().startswith("title") and "platform" in (r[4] or "").lower():
            in_data = True
            continue
        if not in_data or not first:
            continue
        # Stop at the next section header (e.g. "POVR-ONLY HIGH EARNERS")
        if first.isupper() and len(first) > 20:
            in_data = False
            continue
        cross.append(CrossPlatformRow(
            title=first,
            povr_id=(r[1] or "").strip(),
            slr_id=(r[2] or "").strip(),
            studio=(r[3] or "").strip(),
            platforms=[p.strip() for p in (r[4] or "").split(",") if p.strip()],
            povr_total=_parse_money(r[5]) if len(r) > 5 else 0.0,
            slr_total=_parse_money(r[6]) if len(r) > 6 else 0.0,
            vrporn_total=_parse_money(r[7]) if len(r) > 7 else 0.0,
            lifetime_total=_parse_money(r[8]) if len(r) > 8 else 0.0,
            povr_views=_parse_int(r[9]) if len(r) > 9 else 0,
        ))

    # ── Studio attribution for POVR/VRPorn ──────────────────────────────────
    # The _Data tab aggregates POVR + VRPorn revenue at the platform level
    # because the partner exports don't tag individual scenes with the studio
    # that produced them. The 🔗 Cross-Platform tab DOES carry studio info
    # per scene (1440 scenes, attributed by studio). We use that as a proxy
    # to derive platform → studio share, and apply it to monthly POVR/VRPorn
    # totals so the studio filter actually means something at monthly grain.
    #
    # Limitations: shares are derived from cross-platform-distributed scenes
    # only (not single-platform scenes). For studios that distribute heavily
    # cross-platform, this is accurate; for studios with platform-exclusive
    # content, it's a directional approximation. A platform_share field
    # surfaces this so the frontend can flag derived numbers.
    platform_shares: dict[str, dict[str, float]] = {"povr": {}, "vrporn": {}, "slr": {}}
    cross_totals = {"povr": 0.0, "vrporn": 0.0, "slr": 0.0}
    cross_by_studio = {
        "povr":   defaultdict(float),
        "vrporn": defaultdict(float),
        "slr":    defaultdict(float),
    }
    for cx in cross:
        scode = _normalize_studio(cx.studio)
        if not scode:
            continue
        if cx.povr_total > 0:
            cross_by_studio["povr"][scode] += cx.povr_total
            cross_totals["povr"] += cx.povr_total
        if cx.vrporn_total > 0:
            cross_by_studio["vrporn"][scode] += cx.vrporn_total
            cross_totals["vrporn"] += cx.vrporn_total
        if cx.slr_total > 0:
            cross_by_studio["slr"][scode] += cx.slr_total
            cross_totals["slr"] += cx.slr_total
    for plat in ("povr", "vrporn", "slr"):
        tot = cross_totals[plat]
        if tot > 0:
            for s, v in cross_by_studio[plat].items():
                platform_shares[plat][s] = v / tot

    # ── Aggregations ────────────────────────────────────────────────────────
    # Per-platform: all-time, YTD, yearly breakdown
    current_year = max((f["year"] for f in facts if f["year"]), default=2026)
    by_plat: dict[str, dict] = defaultdict(lambda: {"all_time": 0.0, "ytd": 0.0, "yearly": defaultdict(float)})
    for f in facts:
        p = f["platform"]
        by_plat[p]["all_time"] += f["revenue"]
        by_plat[p]["yearly"][str(f["year"])] += f["revenue"]
        if f["year"] == current_year:
            by_plat[p]["ytd"] += f["revenue"]

    platforms = [
        PlatformTotal(
            platform=p,
            all_time=round(d["all_time"], 2),
            ytd=round(d["ytd"], 2),
            yearly={y: round(v, 2) for y, v in sorted(d["yearly"].items())},
        )
        for p, d in by_plat.items()
    ]
    platforms.sort(key=lambda x: -x.all_time)

    # Last 12 months, summed across platforms with MoM delta.
    # _Data is the authoritative source (monthly partner-portal exports). When
    # a month is missing from _Data but present in _DailyData (e.g. the latest
    # in-progress month or a not-yet-imported one), we roll the daily rows up
    # so the chart stays current instead of stranded at the last imported
    # month.
    by_month: dict[str, dict[str, float]] = defaultdict(lambda: {"slr": 0.0, "povr": 0.0, "vrporn": 0.0})
    # Per-studio breakdown is built alongside the platform totals so the
    # frontend can drill into studio=VRH (etc.) at monthly grain. Schema:
    # {month: {studio_code: {platform: revenue}}}. For SLR (where _Data has
    # real per-studio rows) this is direct; for POVR/VRPorn (where _Data
    # rows are platform-aggregated) we apply platform_shares derived from
    # the Cross-Platform tab as a directional approximation.
    by_month_studio: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: {"slr": 0.0, "povr": 0.0, "vrporn": 0.0}))

    def _attribute_to_studios(month: str, plat: str, rev: float, raw_studio: str) -> None:
        """Record a (month, platform, revenue) into by_month_studio. If the
        row carries a real studio code (SLR's per-studio rows), credit it
        directly. If it's a platform-aggregated row (POVR/VRPorn), distribute
        the revenue across studios using cross-platform shares."""
        scode = _normalize_studio(raw_studio)
        if scode:
            by_month_studio[month][scode][plat] += rev
            return
        shares = platform_shares.get(plat) or {}
        if not shares:
            return  # No attribution available — leave it out of per-studio
        for sname, share in shares.items():
            by_month_studio[month][sname][plat] += rev * share

    for f in facts:
        ym = f["year_month"]
        if not ym or len(ym) < 7:
            continue
        by_month[ym][f["platform"]] = by_month[ym].get(f["platform"], 0.0) + f["revenue"]
        _attribute_to_studios(ym, f["platform"], f["revenue"], f["studio"])

    daily = _read_daily_rows(sh)
    months_in_data = set(by_month.keys())
    for r in daily:
        ym = r.date[:7] if r.date else ""
        if not ym or ym in months_in_data:
            continue  # _Data wins when both have the month
        by_month[ym][r.platform] = by_month[ym].get(r.platform, 0.0) + r.revenue
        _attribute_to_studios(ym, r.platform, r.revenue, r.studio)

    sorted_months = sorted(by_month.keys())[-12:]
    monthly: list[MonthlyPoint] = []
    prev_total: float | None = None
    for m in sorted_months:
        d = by_month[m]
        total = d["slr"] + d["povr"] + d["vrporn"]
        mom = None
        if prev_total is not None and prev_total > 0:
            mom = round(((total - prev_total) / prev_total) * 100, 1)
        # Per-studio breakdown for this month — round for the wire.
        bs_raw = by_month_studio.get(m, {})
        bs: dict[str, dict[str, float]] = {}
        for sname, plat_map in bs_raw.items():
            slr_v    = round(plat_map.get("slr", 0.0),    2)
            povr_v   = round(plat_map.get("povr", 0.0),   2)
            vrp_v    = round(plat_map.get("vrporn", 0.0), 2)
            stotal   = round(slr_v + povr_v + vrp_v,      2)
            if stotal <= 0:
                continue
            bs[sname] = {
                "slr":    slr_v,
                "povr":   povr_v,
                "vrporn": vrp_v,
                "total":  stotal,
            }
        monthly.append(MonthlyPoint(
            month=m,
            slr=round(d["slr"], 2),
            povr=round(d["povr"], 2),
            vrporn=round(d["vrporn"], 2),
            total=round(total, 2),
            mom_pct=mom,
            by_studio=bs,
        ))
        prev_total = total

    # Catalog intelligence — scenes + avg per scene per platform
    by_plat_scenes: dict[str, list[SceneRow]] = defaultdict(list)
    for s in scenes:
        by_plat_scenes[s.platform].append(s)
    catalog = []
    for p, lst in by_plat_scenes.items():
        if not lst:
            continue
        rev = sum(s.revenue for s in lst)
        top = max((s.revenue for s in lst), default=0.0)
        catalog.append(CatalogIntel(
            platform=p,
            total_scenes=len(lst),
            avg_revenue_per_scene=round(rev / max(1, len(lst)), 2),
            top_scene_revenue=round(top, 2),
        ))
    catalog.sort(key=lambda c: -c.total_scenes)

    grand_total = sum(p.all_time for p in platforms)
    ytd_total   = sum(p.ytd      for p in platforms)

    return {
        "scenes": scenes,
        "cross":  cross,
        "daily":  daily,
        "dashboard": RevenueDashboard(
            grand_total=round(grand_total, 2),
            ytd_total=round(ytd_total, 2),
            platforms=platforms,
            monthly_trend=monthly,
            catalog=catalog,
            refreshed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        ),
    }


def _get_cache(force: bool = False) -> dict:
    """Return the cached aggregate, refreshing on TTL miss or force=True."""
    global _cache, _cache_at
    now = time.time()
    if not force and _cache and (now - _cache_at) < _CACHE_TTL:
        return _cache
    with _lock:
        now = time.time()
        if not force and _cache and (now - _cache_at) < _CACHE_TTL:
            return _cache
        _log.info("Refreshing revenue cache from Premium Breakdowns sheet...")
        _cache = _build_cache()
        _cache_at = now
        _log.info("Revenue cache refreshed (%d scene rows, %d cross-platform rows)",
                  len(_cache.get("scenes", [])), len(_cache.get("cross", [])))
        return _cache


# ---------------------------------------------------------------------------
# Routes — all admin-only
# ---------------------------------------------------------------------------
@router.get("/dashboard", response_model=RevenueDashboard)
async def get_dashboard(
    refresh: bool = Query(default=False, description="Bypass cache"),
    _admin: dict = Depends(require_revenue_viewer),
):
    """High-level revenue dashboard — totals, YoY, 12-month trend, catalog."""
    return _get_cache(force=refresh)["dashboard"]


@router.get("/scenes", response_model=list[SceneRow])
async def get_scenes(
    platform: Optional[str] = Query(default=None, description="slr | povr | vrporn"),
    studio: Optional[str] = Query(default=None, description="VRH | FPVR | VRA | NJOI | …"),
    order: str = Query(default="top", pattern="^(top|bottom)$"),
    limit: int = Query(default=50, le=500),
    _admin: dict = Depends(require_revenue_viewer),
):
    """Top or bottom scenes by revenue, optionally filtered by platform/studio."""
    scenes: list[SceneRow] = _get_cache()["scenes"]
    out = scenes
    if platform:
        p = _normalize_platform(platform)
        out = [s for s in out if s.platform == p]
    if studio:
        out = [s for s in out if s.studio.lower() == studio.lower()]
    out.sort(key=lambda s: s.revenue, reverse=(order == "top"))
    return out[:limit]


@router.get("/cross-platform", response_model=list[CrossPlatformRow])
async def get_cross_platform(
    limit: int = Query(default=100, le=500),
    _admin: dict = Depends(require_revenue_viewer),
):
    """Scenes that appear on 2+ platforms with lifetime earnings."""
    cross: list[CrossPlatformRow] = _get_cache()["cross"]
    cross_sorted = sorted(cross, key=lambda c: c.lifetime_total, reverse=True)
    return cross_sorted[:limit]


@router.get("/scene/lookup", response_model=list[SceneRow])
async def lookup_scene_revenue(
    title: Optional[str] = Query(default=None, description="Substring match on title"),
    studio: Optional[str] = Query(default=None),
    _admin: dict = Depends(require_revenue_viewer),
):
    """Find revenue rows for a given title (used by scene-detail cross-link)."""
    scenes: list[SceneRow] = _get_cache()["scenes"]
    out = scenes
    if title:
        needle = title.lower()
        out = [s for s in out if needle in s.title.lower()]
    if studio:
        out = [s for s in out if s.studio.lower() == studio.lower()]
    out.sort(key=lambda s: s.revenue, reverse=True)
    return out[:50]


@router.get("/daily", response_model=DailySummary)
async def get_daily_summary(_admin: dict = Depends(require_revenue_viewer)):
    """Daily-granularity snapshot for the dashboard:
       - yesterday: rows for the most recent date in _DailyData
       - this_month: rows from start-of-current-month to yesterday

    Source: the _DailyData tab. Currently populated by VRPorn only;
    POVR/SLR daily wiring is in flight."""
    cache = _get_cache()
    daily: list[DailyRow] = cache.get("daily", [])

    if not daily:
        return DailySummary(
            yesterday=[], yesterday_date="", yesterday_total=0.0,
            this_month=[], this_month_total=0.0,
            refreshed_at=cache["dashboard"].refreshed_at,
        )

    # Yesterday = most-recent date in the data
    most_recent = max(d.date for d in daily)
    y_rows = [d for d in daily if d.date == most_recent]
    y_total = round(sum(d.revenue for d in y_rows), 2)

    # This month = same year-month prefix as most_recent
    ym_prefix = most_recent[:7]  # "YYYY-MM"
    month_rows = [d for d in daily if d.date.startswith(ym_prefix)]
    month_total = round(sum(d.revenue for d in month_rows), 2)
    month_rows_sorted = sorted(month_rows, key=lambda d: d.date)

    return DailySummary(
        yesterday=y_rows,
        yesterday_date=most_recent,
        yesterday_total=y_total,
        this_month=month_rows_sorted,
        this_month_total=month_total,
        refreshed_at=cache["dashboard"].refreshed_at,
    )
