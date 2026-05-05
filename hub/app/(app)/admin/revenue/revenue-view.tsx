"use client"

import { useMemo, useState, useEffect } from "react"
import Link from "next/link"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { ArrowLeft, TrendingDown, TrendingUp, Calendar, Filter, AlertCircle } from "lucide-react"
import type {
  RevenueDashboard,
  SceneRevenueRow,
  CrossPlatformRevenueRow,
  RevenueMonthlyPoint,
  DailyRevenueSummary,
  DailyRevenueRow,
} from "@/lib/api"

// Date-range presets — affect daily-grain blocks only.
type DateRange = "yesterday" | "7d" | "30d" | "month" | "all"

const DATE_RANGE_LABELS: Record<DateRange, string> = {
  yesterday: "Yesterday",
  "7d":      "Last 7 days",
  "30d":     "Last 30 days",
  month:     "This month",
  all:       "All time",
}

type StudioFilter = string | null
const STUDIOS = ["FPVR", "VRH", "VRA", "NJOI"]

// Platform identity — uses the dedicated platform palette (sky / amber /
// emerald), kept separate from the studio palette so platform × studio
// filtering doesn't fight for the same colors. Lime is reserved for
// actions and stays out of platform identity.
const PLATFORM_COLOR: Record<string, string> = {
  slr:    "var(--color-platform-slr)",
  povr:   "var(--color-platform-povr)",
  vrporn: "var(--color-platform-vrporn)",
}

// Studio identity — used as overlay accents when a studio context is
// the subject. Available for filter-chip tinting and per-studio detail.
const STUDIO_COLOR: Record<string, string> = {
  FPVR: "var(--color-fpvr)",
  VRH:  "var(--color-vrh)",
  VRA:  "var(--color-vra)",
  NJOI: "var(--color-njoi)",
}

const PLATFORM_LABEL: Record<string, string> = {
  slr:    "SexLikeReal",
  povr:   "POVR",
  vrporn: "VRPorn",
}

const PLATFORM_SHORT: Record<string, string> = {
  slr:    "SLR",
  povr:   "POVR",
  vrporn: "VRPorn",
}

const MONTHS_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

function fmtMoney(n: number, dollarsOnly = false): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`
  if (n >= 10_000)    return `$${Math.round(n / 1000)}K`
  if (dollarsOnly)    return `$${Math.round(n).toLocaleString()}`
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtMoneyFull(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtPct(n: number | null): string {
  if (n === null || !isFinite(n)) return "—"
  const sign = n > 0 ? "+" : ""
  return `${sign}${n.toFixed(1)}%`
}

function fmtMonth(ym: string): string {
  // "2026-03" → "Mar '26"
  const [y, m] = ym.split("-")
  return `${MONTHS_SHORT[parseInt(m, 10) - 1]} '${y.slice(2)}`
}

function fmtMonthLong(ym: string): string {
  // "2026-03" → "March 2026"
  const [y, m] = ym.split("-")
  const long = ["January","February","March","April","May","June","July","August","September","October","November","December"]
  return `${long[parseInt(m, 10) - 1]} ${y}`
}

function prettyDate(iso: string): string {
  // "2026-04-30" → "Apr 30"
  if (!iso || iso.length < 10) return iso
  const [, m, d] = iso.split("-")
  return `${MONTHS_SHORT[parseInt(m, 10) - 1]} ${parseInt(d, 10)}`
}

function daysInMonth(ym: string): number {
  const [y, m] = ym.split("-").map(s => parseInt(s, 10))
  return new Date(Date.UTC(y, m, 0)).getUTCDate()
}

// "2026-04-12" minus 7 days → "2026-04-05"
function isoMinusDays(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00Z")
  d.setUTCDate(d.getUTCDate() - days)
  return d.toISOString().slice(0, 10)
}

function pctDelta(curr: number, prev: number): number | null {
  if (!prev) return null
  return ((curr - prev) / prev) * 100
}

export function RevenueView({
  dashboard,
  topScenes,
  crossPlatform,
  daily,
  error,
}: {
  dashboard: RevenueDashboard | null
  topScenes: SceneRevenueRow[]
  crossPlatform: CrossPlatformRevenueRow[]
  daily: DailyRevenueSummary | null
  error: string | null
}) {
  // Filter state hydrates from / writes to the URL so a configured view
  // can be shared or bookmarked (?range=7d&platform=povr&studio=VRH).
  // Garbage params are silently dropped — invalid ranges, platforms, or
  // studios fall back to defaults rather than rendering an error.
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const VALID_RANGES = new Set<DateRange>(["yesterday", "7d", "30d", "month", "all"])
  const VALID_PLATFORMS = new Set(["slr", "povr", "vrporn"])
  const VALID_STUDIOS = new Set(STUDIOS)

  const initialRange = (() => {
    const r = searchParams?.get("range") as DateRange | null
    return r && VALID_RANGES.has(r) ? r : "month"
  })()
  const initialPlatform = (() => {
    const p = searchParams?.get("platform")
    return p && VALID_PLATFORMS.has(p) ? p : null
  })()
  const initialStudio = (() => {
    const s = searchParams?.get("studio")
    return s && VALID_STUDIOS.has(s) ? s : null
  })()
  const initialSection: "top" | "cross" = searchParams?.get("section") === "cross" ? "cross" : "top"

  const [activeSection, setActiveSection] = useState<"top" | "cross">(initialSection)
  const [platformFilter, setPlatformFilter] = useState<string | null>(initialPlatform)
  const [studioFilter, setStudioFilter] = useState<StudioFilter>(initialStudio)
  const [dateRange, setDateRange] = useState<DateRange>(initialRange)

  // Push state to URL whenever it changes. Using `push` (not `replace`) so
  // the back button restores prior filter combos — Alex toggles filters
  // dozens of times a session and expects history to work.
  useEffect(() => {
    const q = new URLSearchParams()
    if (dateRange !== "month") q.set("range", dateRange)
    if (platformFilter)        q.set("platform", platformFilter)
    if (studioFilter)          q.set("studio", studioFilter)
    if (activeSection !== "top") q.set("section", activeSection)
    const next = q.toString() ? `${pathname}?${q.toString()}` : pathname
    router.push(next, { scroll: false })
  }, [router, pathname, dateRange, platformFilter, studioFilter, activeSection])

  if (error) {
    return (
      <div style={{ padding: 32 }}>
        <Link href="/admin" style={{ fontSize: 12, color: "var(--color-text-muted)", textDecoration: "none" }}>
          <ArrowLeft size={12} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
          Back to Admin
        </Link>
        <h1 style={{ marginTop: 12 }}>Revenue</h1>
        <p style={{ color: "var(--color-err)", fontSize: 13, marginTop: 8 }}>{error}</p>
      </div>
    )
  }
  if (!dashboard) {
    return (
      <div style={{ padding: 32, color: "var(--color-text-muted)" }}>Loading…</div>
    )
  }

  const refreshed = (() => {
    try {
      const ts = new Date(dashboard.refreshed_at).getTime()
      const ageMin = Math.max(0, Math.round((Date.now() - ts) / 60_000))
      const stale = ageMin >= 360   // 6h+ — overnight refresh missed
      let label: string
      if (ageMin < 1)        label = "just now"
      else if (ageMin < 60)  label = `${ageMin} min ago`
      else                   label = `${Math.round(ageMin / 60)}h ago`
      return { label, stale }
    } catch {
      return { label: "—", stale: false }
    }
  })()

  // ── Filtering wired across every filter-aware section ─────────────────────
  // Range filter shrinks daily-grain blocks. Platform/studio drop rows
  // everywhere applicable. The monthly-grain hero is unaffected by Range
  // (Range is a daily concept) but does honor Platform.

  const cutoffDate = useMemo(() => {
    if (dateRange === "all" || dateRange === "month") return null
    const days = dateRange === "yesterday" ? 1 : (dateRange === "7d" ? 7 : 30)
    const d = new Date()
    d.setUTCHours(0, 0, 0, 0)
    d.setUTCDate(d.getUTCDate() - days)
    return d.toISOString().slice(0, 10)
  }, [dateRange])

  const filteredTopScenes = useMemo(() => {
    let out = topScenes
    if (platformFilter) out = out.filter(s => s.platform === platformFilter)
    if (studioFilter)   out = out.filter(s => s.studio.toUpperCase() === studioFilter.toUpperCase())
    return out
  }, [topScenes, platformFilter, studioFilter])

  const filteredCrossPlatform = useMemo(() => {
    let out = crossPlatform
    if (studioFilter)   out = out.filter(r => r.studio.toUpperCase() === studioFilter.toUpperCase())
    if (platformFilter) {
      out = out.filter(r => {
        if (platformFilter === "slr")    return r.slr_total > 0
        if (platformFilter === "povr")   return r.povr_total > 0
        if (platformFilter === "vrporn") return r.vrporn_total > 0
        return true
      })
    }
    return out
  }, [crossPlatform, studioFilter, platformFilter])

  const filteredDaily = useMemo(() => {
    if (!daily) return null
    let yesterdayRows = daily.yesterday
    let monthRows = daily.this_month

    if (cutoffDate) monthRows = monthRows.filter(r => r.date >= cutoffDate)

    if (platformFilter) {
      yesterdayRows = yesterdayRows.filter(r => r.platform === platformFilter)
      monthRows     = monthRows.filter(r => r.platform === platformFilter)
    }
    if (studioFilter) {
      yesterdayRows = yesterdayRows.filter(r => r.studio.toUpperCase() === studioFilter.toUpperCase())
      monthRows     = monthRows.filter(r => r.studio.toUpperCase() === studioFilter.toUpperCase())
    }

    return {
      ...daily,
      yesterday: yesterdayRows,
      yesterday_total: yesterdayRows.reduce((acc, r) => acc + r.revenue, 0),
      this_month: monthRows,
      this_month_total: monthRows.reduce((acc, r) => acc + r.revenue, 0),
    }
  }, [daily, cutoffDate, platformFilter, studioFilter])

  // Monthly trend honors both filters. Studio filter uses the API's
  // by_studio rollup (SLR rows are real per-studio; POVR/VRPorn are
  // approximated via cross-platform shares — see api/routers/revenue.py).
  // Platform filter zeros out non-selected platforms after studio applies.
  const filteredMonthly = useMemo(() => {
    let series = dashboard.monthly_trend
    if (studioFilter) {
      series = series.map(p => {
        const slice = p.by_studio?.[studioFilter] ?? { slr: 0, povr: 0, vrporn: 0, total: 0 }
        // Recompute MoM at studio grain by anchoring it to studio total.
        return { ...p, slr: slice.slr, povr: slice.povr, vrporn: slice.vrporn, total: slice.total }
      })
      // Recompute MoM% at studio grain
      let prev: number | null = null
      series = series.map(p => {
        const mom = prev !== null && prev > 0 ? Math.round(((p.total - prev) / prev) * 1000) / 10 : null
        prev = p.total
        return { ...p, mom_pct: mom }
      })
    }
    if (platformFilter) {
      series = series.map(p => ({
        month: p.month,
        slr:    platformFilter === "slr"    ? p.slr    : 0,
        povr:   platformFilter === "povr"   ? p.povr   : 0,
        vrporn: platformFilter === "vrporn" ? p.vrporn : 0,
        total:  platformFilter === "slr" ? p.slr : platformFilter === "povr" ? p.povr : p.vrporn,
        mom_pct: p.mom_pct,
        by_studio: p.by_studio,
      }))
    }
    return series
  }, [dashboard.monthly_trend, platformFilter, studioFilter])

  // Whether monthly_trend has by_studio data for the selected studio.
  // Used to surface a "studio breakdown is approximate / partial" badge.
  const studioMonthlyAvailable = useMemo(() => {
    if (!studioFilter) return true
    return dashboard.monthly_trend.some(p => p.by_studio?.[studioFilter])
  }, [dashboard.monthly_trend, studioFilter])

  // Filter the YoY platform table.
  const filteredPlatforms = useMemo(() => {
    if (!platformFilter) return dashboard.platforms
    return dashboard.platforms.filter(p => p.platform === platformFilter)
  }, [dashboard.platforms, platformFilter])

  const filtersActive = !!(platformFilter || studioFilter || dateRange !== "month")
  function clearAllFilters() {
    setPlatformFilter(null)
    setStudioFilter(null)
    setDateRange("month")
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header — eyebrow links back to Admin; h1 carries the page weight. */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div>
          <Link href="/admin" style={{
            fontSize: 11, color: "var(--color-text-muted)", textDecoration: "none",
            letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 600,
          }}>
            <ArrowLeft size={11} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
            Admin
          </Link>
          <h1 style={{
            fontFamily: "var(--font-display-hero)",
            fontSize: "var(--text-display)",
            fontWeight: 700,
            letterSpacing: "-0.02em",
            marginTop: 6, lineHeight: 1.05,
          }}>
            Revenue
          </h1>
        </div>
        <div style={{
          fontSize: 11, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)",
          display: "inline-flex", alignItems: "center", gap: 6,
        }}
          title={refreshed.stale ? "Refresh is overdue — daily scrape may have failed" : "Last cache refresh"}
        >
          <span style={{
            width: 6, height: 6, borderRadius: "50%",
            background: refreshed.stale ? "var(--color-warn)" : "var(--color-ok)",
            opacity: 0.9,
          }} />
          Refreshed {refreshed.label}
        </div>
      </div>

      {/* Sticky filter bar */}
      <FilterBar
        dateRange={dateRange}
        setDateRange={setDateRange}
        studio={studioFilter}
        setStudio={setStudioFilter}
        platform={platformFilter}
        setPlatform={setPlatformFilter}
        active={filtersActive}
        onClear={clearAllFilters}
      />

      {/* Hero KPI band — month-led metrics */}
      <HeroKpis
        monthly={filteredMonthly}
        daily={filteredDaily}
        platformFilter={platformFilter}
        grandTotal={filteredPlatforms.reduce((acc, p) => acc + p.all_time, 0)}
        ytdTotal={filteredPlatforms.reduce((acc, p) => acc + p.ytd, 0)}
      />

      {/* Monthly hero — primary lens for cross-platform revenue */}
      <MonthlyHero
        points={filteredMonthly}
        platformFilter={platformFilter}
        studioFilter={studioFilter}
        studioApprox={!!studioFilter && studioMonthlyAvailable}
      />

      {/* Per-platform monthly cards — how each platform's portal shows it.
          When a studio is selected, cards use the studio's slice of each
          platform (real for SLR, approximated for POVR/VRPorn). */}
      <PlatformMonthlyCards
        platforms={dashboard.platforms}
        monthly={filteredMonthly}
        platformFilter={platformFilter}
        studioFilter={studioFilter}
      />

      {/* Daily detail — only fully populated for VRPorn today; honors Range */}
      {filteredDaily && (filteredDaily.this_month.length > 0 || filteredDaily.yesterday.length > 0) && (
        <DailyDetail
          daily={filteredDaily}
          dateRange={dateRange}
          platformFilter={platformFilter}
          studioFilter={studioFilter}
        />
      )}

      {/* Year-over-year reference table */}
      <PlatformComparison platforms={filteredPlatforms} platformFilter={platformFilter} />

      {/* Section toggle: Top scenes vs Cross-platform */}
      <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
        <SectionTab
          active={activeSection === "top"}
          onClick={() => setActiveSection("top")}
          label="Top earners"
          count={filteredTopScenes.length}
        />
        <SectionTab
          active={activeSection === "cross"}
          onClick={() => setActiveSection("cross")}
          label="Cross-platform matches"
          count={filteredCrossPlatform.length}
        />
      </div>

      {activeSection === "top"
        ? <TopScenesTable scenes={filteredTopScenes} />
        : <CrossPlatformTable rows={filteredCrossPlatform} platformFilter={platformFilter} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Filter bar — sticky under topbar, drives every section's data
// ---------------------------------------------------------------------------
function FilterBar({
  dateRange, setDateRange, studio, setStudio, platform, setPlatform,
  active, onClear,
}: {
  dateRange: DateRange
  setDateRange: (v: DateRange) => void
  studio: StudioFilter
  setStudio: (v: StudioFilter) => void
  platform: string | null
  setPlatform: (v: string | null) => void
  active: boolean
  onClear: () => void
}) {
  const ranges: DateRange[] = ["yesterday", "7d", "30d", "month", "all"]
  return (
    <div style={{
      position: "sticky", top: "var(--spacing-topbar)",
      zIndex: 10,
      background: "var(--color-surface)",
      border: "1px solid var(--color-border-subtle)",
      padding: "10px 14px",
      display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Calendar size={11} style={{ color: "var(--color-text-faint)" }} />
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                       textTransform: "uppercase", color: "var(--color-text-faint)" }}>
          Range
        </span>
        <div style={{ display: "flex", gap: 4 }}>
          {ranges.map(r => (
            <Chip
              key={r}
              isActive={dateRange === r}
              onClick={() => setDateRange(r)}
              label={DATE_RANGE_LABELS[r]}
            />
          ))}
        </div>
      </div>

      <div style={{ height: 16, width: 1, background: "var(--color-border-subtle)" }} />

      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Filter size={11} style={{ color: "var(--color-text-faint)" }} />
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                       textTransform: "uppercase", color: "var(--color-text-faint)" }}>
          Platform
        </span>
        <div style={{ display: "flex", gap: 4 }}>
          {([null, "slr", "povr", "vrporn"] as (string | null)[]).map(opt => (
            <Chip
              key={opt ?? "all"}
              isActive={platform === opt}
              onClick={() => setPlatform(opt)}
              accent={opt ? PLATFORM_COLOR[opt] : undefined}
              label={opt
                ? <>
                    <span style={{
                      display: "inline-block", width: 6, height: 6, borderRadius: 1,
                      background: PLATFORM_COLOR[opt],
                      marginRight: 6, verticalAlign: "middle",
                    }} />
                    {PLATFORM_LABEL[opt]}
                  </>
                : "All"}
            />
          ))}
        </div>
      </div>

      <div style={{ height: 16, width: 1, background: "var(--color-border-subtle)" }} />

      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                       textTransform: "uppercase", color: "var(--color-text-faint)" }}>
          Studio
        </span>
        <div style={{ display: "flex", gap: 4 }}>
          {[null, ...STUDIOS].map(opt => (
            <Chip
              key={opt ?? "all"}
              isActive={studio === opt}
              onClick={() => setStudio(opt as StudioFilter)}
              accent={opt ? STUDIO_COLOR[opt] : undefined}
              mono={!!opt}
              label={opt ?? "All"}
            />
          ))}
        </div>
      </div>

      {active && (
        <>
          <div style={{ flex: 1 }} />
          <button
            type="button"
            onClick={onClear}
            style={{
              padding: "4px 10px", fontSize: 11, fontWeight: 600,
              background: "transparent",
              color: "var(--color-lime)",
              border: "1px solid var(--color-lime)",
              cursor: "pointer",
              letterSpacing: "0.04em",
            }}
            title="Reset all filters to defaults"
          >
            Clear filters
          </button>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Hero KPI band — month-led metrics with deltas + projections
// ---------------------------------------------------------------------------
function HeroKpis({
  monthly, daily, platformFilter, grandTotal, ytdTotal,
}: {
  monthly: RevenueMonthlyPoint[]
  daily: DailyRevenueSummary | null
  platformFilter: string | null
  grandTotal: number
  ytdTotal: number
}) {
  // Latest two monthly points anchor the MTD KPI + MoM.
  const last = monthly[monthly.length - 1] ?? null
  const prev = monthly[monthly.length - 2] ?? null

  // Days elapsed in current month → projection.
  // We assume the current month is whatever today's UTC month is. If the
  // dataset is lagging (e.g. monthly_trend's last point is two months old),
  // we still compute against the actual calendar to keep the math honest.
  const today = new Date()
  const dayOfMonth = today.getUTCDate()
  const ymToday = `${today.getUTCFullYear()}-${String(today.getUTCMonth() + 1).padStart(2, "0")}`
  const matchesCurrent = last?.month === ymToday
  const dim = last ? daysInMonth(last.month) : 30
  const projected = matchesCurrent && dayOfMonth > 0 && last
    ? (last.total / dayOfMonth) * dim
    : last?.total ?? 0

  // Compare projection to previous full month
  const projVsPrev = prev?.total ? pctDelta(projected, prev.total) : null

  // Yesterday + WoW delta (only meaningful when daily is populated).
  const yTotal = daily?.yesterday_total ?? 0
  const yDate = daily?.yesterday_date ?? ""
  const sevenBack = yDate ? isoMinusDays(yDate, 7) : ""
  const wowRows = daily?.this_month.filter(r => r.date === sevenBack) ?? []
  const wowTotal = wowRows.reduce((acc, r) => acc + r.revenue, 0)
  const wowPct = wowTotal ? pctDelta(yTotal, wowTotal) : null

  // Best day MTD (from daily rows). Source label comes from whichever
  // platforms actually contribute rows in the current snapshot.
  const dailyByDate = new Map<string, number>()
  const dailyPlatformsPresent = new Set<string>()
  for (const r of daily?.this_month ?? []) {
    dailyByDate.set(r.date, (dailyByDate.get(r.date) ?? 0) + r.revenue)
    dailyPlatformsPresent.add(r.platform)
  }
  let bestDate = ""
  let bestTotal = 0
  for (const [d, v] of dailyByDate.entries()) {
    if (v > bestTotal) { bestDate = d; bestTotal = v }
  }

  // Human-readable label for "what platforms are contributing daily rows".
  // Used in the bottom-line subcopy of the daily-derived KPIs so the user
  // never wonders whether a number is partial.
  const feedLabel = (() => {
    if (platformFilter) return PLATFORM_LABEL[platformFilter] ?? platformFilter
    if (dailyPlatformsPresent.size === 0) return "no daily feed yet"
    if (dailyPlatformsPresent.size === 1) {
      const p = [...dailyPlatformsPresent][0]
      return `${PLATFORM_SHORT[p] ?? p}-only feed`
    }
    return [...dailyPlatformsPresent].sort()
      .map(p => PLATFORM_SHORT[p] ?? p).join(" + ")
  })()

  // Detect Yesterday == Best Day so the duplicate is acknowledged inline
  // instead of looking like a display bug ("why are these two numbers
  // identical?"). Tolerates floating-point fuzz.
  const yesterdayIsBest = bestTotal > 0 && Math.abs(yTotal - bestTotal) < 0.01

  // Build tiles. Lead = current MTD with bigger weight; mini = three
  // demoted tiles for projection / yesterday / best day.
  const monthLabel = last ? fmtMonthLong(last.month) : "—"
  const lead: KpiTile = {
    kicker: matchesCurrent ? `${monthLabel} · MTD` : monthLabel,
    help:   "Month-to-date total across all reporting platforms.",
    value:  fmtMoneyFull(last?.total ?? 0),
    delta:  last?.mom_pct ?? null,
    sub:    prev ? `vs ${fmtMonthLong(prev.month)} ${fmtMoney(prev.total, true)}` : "—",
  }
  const minis: KpiTile[] = [
    {
      kicker: matchesCurrent ? "Projected EOM" : "Last full month",
      help:   matchesCurrent
        ? "Linear extrapolation of MTD across all days in the month."
        : "Most recent full month's total.",
      value:  fmtMoney(matchesCurrent ? projected : (prev?.total ?? 0), true),
      delta:  matchesCurrent ? projVsPrev : null,
      sub:    matchesCurrent
        ? `${dayOfMonth}/${dim} days · linear pace`
        : prev ? `${fmtMonthLong(prev.month)} closed` : "—",
    },
    {
      kicker: yDate ? `Yesterday · ${prettyDate(yDate)}` : "Yesterday",
      help:   "Daily total for the most recent date in the daily feed.",
      value:  fmtMoney(yTotal, true),
      delta:  wowPct,
      sub:    wowPct !== null ? `vs ${prettyDate(sevenBack)} ${fmtMoney(wowTotal, true)}` : feedLabel,
    },
    {
      kicker: "Best day MTD",
      help:   "Highest single-day total in the current month.",
      value:  bestTotal ? fmtMoney(bestTotal, true) : "—",
      delta:  null,
      sub:    bestDate
        ? (yesterdayIsBest ? `${prettyDate(bestDate)} · = Yesterday` : `${prettyDate(bestDate)} · ${feedLabel}`)
        : "no daily rows",
      badge:  yesterdayIsBest ? "= Yesterday" : undefined,
    },
  ]

  return (
    <div>
      <div style={{
        display: "grid",
        // Lead = 2fr; three demoted = 1fr each. Keeps the four-tile rhythm
        // but lifts the MTD number to the eye first.
        gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr)",
        gap: 1,
        background: "var(--color-border-subtle)",
        border: "1px solid var(--color-border-subtle)",
      }}>
        <KpiLeadView tile={lead} />
        {minis.map((t, i) => <KpiMiniView key={i} tile={t} />)}
      </div>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "baseline",
        marginTop: 8, fontSize: 11, color: "var(--color-text-muted)",
      }}>
        <div>
          <span style={{ color: "var(--color-text-faint)", letterSpacing: "0.06em",
                          textTransform: "uppercase", fontWeight: 700, fontSize: 10 }}>
            All-time
          </span>{" "}
          <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--color-text)" }}>
            {fmtMoneyFull(grandTotal)}
          </span>
        </div>
        <div>
          <span style={{ color: "var(--color-text-faint)", letterSpacing: "0.06em",
                          textTransform: "uppercase", fontWeight: 700, fontSize: 10 }}>
            YTD
          </span>{" "}
          <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--color-text)" }}>
            {fmtMoneyFull(ytdTotal)}
          </span>
        </div>
      </div>
    </div>
  )
}

type KpiTile = {
  kicker: string
  help?:  string                  // tooltip on hover — unpacks the jargon
  value:  string
  delta:  number | null
  sub:    string
  badge?: string                  // "= Yesterday" etc. — flags duplicate values
}

function KpiLeadView({ tile }: { tile: KpiTile }) {
  const TrendIcon = tile.delta === null
    ? null
    : tile.delta >= 0 ? TrendingUp : TrendingDown
  const trendColor = tile.delta === null
    ? "var(--color-text-faint)"
    : tile.delta >= 0 ? "var(--color-ok)" : "var(--color-err)"
  // Re-mount on value change so the cross-fade plays each filter swap.
  // Guarded by `prefers-reduced-motion` via the .ec-kpi-fade class
  // (defined in globals.css) so animation-averse users see snap-changes.
  return (
    <div style={{
      background: "var(--color-surface)",
      padding: "26px 28px",
      display: "flex", flexDirection: "column", gap: 6,
    }}>
      <div title={tile.help} style={{
        fontSize: 10, fontWeight: 700, letterSpacing: "0.14em",
        textTransform: "uppercase", color: "var(--color-text-faint)",
        cursor: tile.help ? "help" : "default",
      }}>
        {tile.kicker}
      </div>
      <div key={tile.value} className="ec-kpi-fade" style={{
        display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap",
      }}>
        <div style={{
          fontFamily: "var(--font-display-hero)", fontSize: 48, fontWeight: 700,
          letterSpacing: "-0.025em", color: "var(--color-text)", lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
        }}>
          {tile.value}
        </div>
        {tile.delta !== null && TrendIcon && (
          <span style={{
            fontFamily: "var(--font-mono)", fontSize: 14, fontWeight: 700,
            color: trendColor, display: "flex", alignItems: "center", gap: 3,
          }}>
            <TrendIcon size={14} style={{ verticalAlign: -1 }} />
            {fmtPct(tile.delta)}
          </span>
        )}
      </div>
      <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{tile.sub}</div>
    </div>
  )
}

function KpiMiniView({ tile }: { tile: KpiTile }) {
  const TrendIcon = tile.delta === null
    ? null
    : tile.delta >= 0 ? TrendingUp : TrendingDown
  const trendColor = tile.delta === null
    ? "var(--color-text-faint)"
    : tile.delta >= 0 ? "var(--color-ok)" : "var(--color-err)"
  return (
    <div style={{
      background: "var(--color-base)",
      padding: "16px 16px",
      display: "flex", flexDirection: "column", gap: 4, justifyContent: "space-between",
    }}>
      <div title={tile.help} style={{
        fontSize: 9, fontWeight: 700, letterSpacing: "0.12em",
        textTransform: "uppercase", color: "var(--color-text-faint)",
        display: "flex", justifyContent: "space-between", gap: 8,
        cursor: tile.help ? "help" : "default",
      }}>
        <span>{tile.kicker}</span>
        {tile.badge && (
          <span style={{
            fontSize: 8, fontWeight: 700, padding: "1px 5px",
            background: "color-mix(in srgb, var(--color-text-faint) 18%, transparent)",
            color: "var(--color-text-muted)",
            letterSpacing: "0.06em",
          }}>
            {tile.badge}
          </span>
        )}
      </div>
      <div key={tile.value} className="ec-kpi-fade" style={{
        display: "flex", alignItems: "baseline", gap: 6, flexWrap: "wrap",
      }}>
        <div style={{
          fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 700,
          letterSpacing: "-0.015em", color: "var(--color-text)", lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
        }}>
          {tile.value}
        </div>
        {tile.delta !== null && TrendIcon && (
          <span style={{
            fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700,
            color: trendColor, display: "flex", alignItems: "center", gap: 2,
          }}>
            <TrendIcon size={10} style={{ verticalAlign: -1 }} />
            {fmtPct(tile.delta)}
          </span>
        )}
      </div>
      <div style={{ fontSize: 10, color: "var(--color-text-muted)" }}>{tile.sub}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Monthly hero — taller, current-month highlighted, MoM% under each bar
// ---------------------------------------------------------------------------
function MonthlyHero({
  points, platformFilter, studioFilter, studioApprox,
}: {
  points: RevenueMonthlyPoint[]
  platformFilter: string | null
  studioFilter: StudioFilter
  studioApprox: boolean   // POVR/VRPorn studio breakdowns are derived
}) {
  // Trim leading-zero months when filtered to a platform/studio that
  // started mid-period (e.g. VRPorn launched Sep 2025; a new studio).
  const trimmed = useMemo(() => {
    if (!platformFilter && !studioFilter) return points
    let i = 0
    while (i < points.length && points[i].total === 0) i++
    return points.slice(i)
  }, [points, platformFilter, studioFilter])

  if (trimmed.length === 0) {
    return (
      <Section title="Monthly trend" subtitle="No data in range">
        <Empty>No months match this filter.</Empty>
      </Section>
    )
  }

  const max = Math.max(1, ...trimmed.map(p => p.total))
  const lastIdx = trimmed.length - 1
  const segments: string[] = []
  if (studioFilter)   segments.push(`${studioFilter} slice`)
  if (platformFilter) segments.push(`${PLATFORM_LABEL[platformFilter] ?? platformFilter} only`)
  const subtitle = `${segments.length ? segments.join(" · ") + " · " : "Stacked by platform · "}${trimmed.length} months · current month highlighted`

  // Y-axis tick lines at 0 / 50% / 100% to give scale anchoring.
  const ticks = [0, 0.5, 1]
  const chartHeight = 240

  // Approximate badge: shown when a studio filter is active AND any of
  // its non-SLR contributions came from cross-platform share derivation
  // (POVR/VRPorn). Tells the user "this is directional, not authoritative."
  const badge = studioFilter && studioApprox
    ? <FeedBadge label="POVR & VRPorn shares derived from cross-platform tab" tone="info" />
    : undefined

  return (
    <Section title="Monthly trend" subtitle={subtitle} badge={badge}>
      <div style={{ position: "relative", padding: "8px 0 0 0" }}>
        {/* Y-axis backdrop lines */}
        <div style={{ position: "absolute", inset: "8px 0 70px 0", pointerEvents: "none" }}>
          {ticks.map((t, i) => (
            <div key={i} style={{
              position: "absolute", left: 0, right: 0,
              bottom: `${t * 100}%`,
              borderTop: i === 0
                ? "1px solid var(--color-border-subtle)"
                : "1px dashed var(--color-border-subtle)",
              opacity: i === 0 ? 1 : 0.5,
            }} />
          ))}
          <div style={{
            position: "absolute", left: 0, top: 0, fontSize: 9,
            fontFamily: "var(--font-mono)", color: "var(--color-text-faint)",
          }}>
            {fmtMoney(max, true)}
          </div>
          <div style={{
            position: "absolute", left: 0, top: "50%", fontSize: 9,
            fontFamily: "var(--font-mono)", color: "var(--color-text-faint)",
            transform: "translateY(-50%)",
          }}>
            {fmtMoney(max / 2, true)}
          </div>
        </div>

        {/* Bars */}
        <div style={{
          display: "grid",
          gridTemplateColumns: `repeat(${trimmed.length}, minmax(0, 1fr))`,
          gap: 6, alignItems: "end",
          paddingLeft: 36, // room for y-axis labels
          height: chartHeight,
        }}>
          {trimmed.map((p, i) => {
            const isCurrent = i === lastIdx
            const slrH  = (p.slr  / max) * (chartHeight - 60)
            const povrH = (p.povr / max) * (chartHeight - 60)
            const vrpH  = (p.vrporn / max) * (chartHeight - 60)
            return (
              <div key={p.month} style={{ display: "flex", flexDirection: "column", alignItems: "stretch", gap: 4 }}>
                {/* Total label above bar */}
                <div style={{
                  fontSize: isCurrent ? 11 : 10,
                  color: isCurrent ? "var(--color-text)" : "var(--color-text-muted)",
                  textAlign: "center",
                  fontFamily: "var(--font-mono)",
                  fontWeight: isCurrent ? 700 : 600,
                  letterSpacing: isCurrent ? "-0.005em" : 0,
                }}>
                  {fmtMoney(p.total, true)}
                </div>
                {/* Stacked bars (column-reverse so SLR is at bottom).
                    Heights snap on filter change — animating height triggers
                    layout recalc per frame; the comparison matters more than
                    the morph. Opacity still transitions to mark the active
                    column on hover/highlight. */}
                <div style={{
                  display: "flex", flexDirection: "column-reverse",
                  height: chartHeight - 60,
                  justifyContent: "flex-start",
                  position: "relative",
                  outline: isCurrent ? "1px solid var(--color-text)" : "none",
                  outlineOffset: 1,
                }}>
                  {p.slr > 0    && <div style={{ height: slrH,  background: PLATFORM_COLOR.slr,    opacity: isCurrent ? 1 : 0.85, transition: "opacity 200ms ease" }} title={`SLR ${fmtMoney(p.slr, true)}`} />}
                  {p.povr > 0   && <div style={{ height: povrH, background: PLATFORM_COLOR.povr,   opacity: isCurrent ? 1 : 0.85, transition: "opacity 200ms ease" }} title={`POVR ${fmtMoney(p.povr, true)}`} />}
                  {p.vrporn > 0 && <div style={{ height: vrpH,  background: PLATFORM_COLOR.vrporn, opacity: isCurrent ? 1 : 0.85, transition: "opacity 200ms ease" }} title={`VRPorn ${fmtMoney(p.vrporn, true)}`} />}
                </div>
                {/* Month label */}
                <div style={{
                  fontSize: 10,
                  color: isCurrent ? "var(--color-text)" : "var(--color-text-muted)",
                  fontWeight: isCurrent ? 700 : 500,
                  textAlign: "center",
                }}>
                  {fmtMonth(p.month)}
                </div>
                {/* MoM% delta — only the current month gets full red/green
                    saturation. Prior months stay muted so the chart doesn't
                    read as a wall of red during normal seasonal swings. */}
                <div style={{
                  fontSize: 10, textAlign: "center",
                  color: p.mom_pct === null
                    ? "var(--color-text-faint)"
                    : isCurrent
                      ? (p.mom_pct >= 0 ? "var(--color-ok)" : "var(--color-err)")
                      : "var(--color-text-faint)",
                  fontFamily: "var(--font-mono)",
                  fontWeight: isCurrent ? 700 : 500,
                }}>
                  {p.mom_pct !== null && (p.mom_pct >= 0
                    ? <TrendingUp size={9} style={{ display: "inline", verticalAlign: -1, marginRight: 2 }} />
                    : <TrendingDown size={9} style={{ display: "inline", verticalAlign: -1, marginRight: 2 }} />)}
                  {fmtPct(p.mom_pct)}
                </div>
              </div>
            )
          })}
        </div>
      </div>
      {/* Legend */}
      <div style={{ display: "flex", gap: 16, fontSize: 11, color: "var(--color-text-muted)",
                    paddingTop: 12, marginTop: 8, borderTop: "1px solid var(--color-border-subtle)" }}>
        {(["slr", "povr", "vrporn"] as const).map(p => (
          <span key={p} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 10, height: 10, background: PLATFORM_COLOR[p], display: "inline-block" }} />
            {PLATFORM_LABEL[p]}
          </span>
        ))}
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
          <span style={{ display: "inline-block", width: 10, height: 10, border: "1px solid var(--color-text)",
                         marginRight: 6, verticalAlign: "middle" }} />
          current month
        </span>
      </div>
    </Section>
  )
}

// ---------------------------------------------------------------------------
// Per-platform monthly cards — one card per platform (SLR, POVR, VRPorn)
// ---------------------------------------------------------------------------
function PlatformMonthlyCards({
  platforms, monthly, platformFilter, studioFilter,
}: {
  platforms: RevenueDashboard["platforms"]
  monthly: RevenueMonthlyPoint[]
  platformFilter: string | null
  studioFilter: StudioFilter
}) {
  // Order: SLR, POVR, VRPorn
  const order = ["slr", "povr", "vrporn"]
  const ordered = order
    .map(slug => platforms.find(p => p.platform === slug))
    .filter(Boolean) as RevenueDashboard["platforms"]
  const visible = platformFilter ? ordered.filter(p => p.platform === platformFilter) : ordered
  if (visible.length === 0) return null

  const subtitle = studioFilter
    ? `${studioFilter} slice · this month vs last · 12-month sparkline`
    : "This month vs last · 12-month sparkline · all-time anchor"

  return (
    <Section title="Per-platform" subtitle={subtitle}>
      <div style={{
        display: "grid", gap: 1,
        background: "var(--color-border-subtle)",
        border: "1px solid var(--color-border-subtle)",
      }}>
        {visible.map(p => (
          <PlatformRow key={p.platform} platform={p} monthly={monthly} studioFilter={studioFilter} />
        ))}
      </div>
    </Section>
  )
}

// PlatformRow — compact horizontal layout: name+swatch+$ | sparkline | stats.
// Replaced the previous 280px-tall card stack to recover ~400px of vertical
// space and resolve the 26px headline competing with the global 48px lead.
function PlatformRow({
  platform, monthly, studioFilter,
}: {
  platform: RevenueDashboard["platforms"][number]
  monthly: RevenueMonthlyPoint[]
  studioFilter: StudioFilter
}) {
  const slug = platform.platform
  const series = monthly.map(m => ({
    month: m.month,
    // Studio-filtered series already replaced top-level slr/povr/vrporn
    // with the studio's slice for that month, so reading the platform key
    // here gives the right value in either filter mode.
    value: slug === "slr" ? m.slr : slug === "povr" ? m.povr : m.vrporn,
  }))
  // Trim leading zeros (e.g. VRPorn before launch, or a studio's first month)
  let firstNonZero = 0
  while (firstNonZero < series.length && series[firstNonZero].value === 0) firstNonZero++
  const trimmed = series.slice(firstNonZero)

  const last = trimmed[trimmed.length - 1]
  const prev = trimmed[trimmed.length - 2]
  const mom = prev?.value ? pctDelta(last?.value ?? 0, prev.value) : null
  const max = Math.max(1, ...trimmed.map(s => s.value))
  const last3 = trimmed.slice(-3)
  const last3Avg = last3.length ? last3.reduce((a, s) => a + s.value, 0) / last3.length : 0

  const color = PLATFORM_COLOR[slug] ?? "var(--color-text-faint)"
  const TrendIcon = mom === null ? null : mom >= 0 ? TrendingUp : TrendingDown
  const trendColor = mom === null
    ? "var(--color-text-faint)"
    : mom >= 0 ? "var(--color-ok)" : "var(--color-err)"

  // When a studio is selected and this platform has no data for that
  // studio (current state for POVR/VRPorn studios outside the cross-
  // platform-derived shares), surface that explicitly.
  const slugOk = !studioFilter || trimmed.some(s => s.value > 0)

  return (
    <div style={{
      background: "var(--color-surface)",
      display: "grid",
      // Three-zone layout: identity (240) · sparkline (1fr) · stats (260)
      gridTemplateColumns: "minmax(220px, 240px) minmax(0, 1fr) minmax(240px, 280px)",
      gap: 16, padding: "12px 16px", alignItems: "center",
    }}>
      {/* Identity zone: swatch + name + this-month $ + delta */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ width: 8, height: 28, background: color, display: "inline-block" }} />
        <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: "0.02em" }}>
            {PLATFORM_LABEL[slug]}
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{
              fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700,
              letterSpacing: "-0.01em",
            }}>
              {fmtMoney(last?.value ?? 0, true)}
            </span>
            {mom !== null && TrendIcon && (
              <span style={{
                fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 700,
                color: trendColor, display: "inline-flex", alignItems: "center", gap: 1,
              }}>
                <TrendIcon size={9} style={{ verticalAlign: -1 }} />
                {fmtPct(mom)}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Sparkline zone */}
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {slugOk ? (
          <>
            <div style={{
              display: "grid", gap: 2,
              gridTemplateColumns: `repeat(${trimmed.length}, minmax(0, 1fr))`,
              alignItems: "end", height: 36,
            }}>
              {trimmed.map((s, i) => {
                const h = (s.value / max) * 32
                const isLast = i === trimmed.length - 1
                return (
                  <div key={s.month}
                       title={`${fmtMonth(s.month)} · ${fmtMoneyFull(s.value)}`}
                       style={{
                         height: Math.max(2, h),
                         background: color,
                         opacity: isLast ? 1 : 0.55,
                         transition: "opacity 220ms ease",
                       }}
                  />
                )
              })}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between",
                          fontSize: 9, fontFamily: "var(--font-mono)",
                          color: "var(--color-text-faint)" }}>
              <span>{trimmed[0] ? fmtMonth(trimmed[0].month) : ""}</span>
              <span>{last ? fmtMonth(last.month) : ""}</span>
            </div>
          </>
        ) : (
          <div style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
            No data for {studioFilter} on this platform.
          </div>
        )}
      </div>

      {/* Stats zone — inline stats, replaces the previous 3-stat footer grid */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8,
        fontSize: 10,
      }}>
        <Stat label="All-time" value={fmtMoney(platform.all_time, true)} />
        <Stat label="YTD" value={fmtMoney(platform.ytd, true)} />
        <Stat label="3-mo avg" value={fmtMoney(last3Avg, true)} />
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.1em",
                      textTransform: "uppercase", color: "var(--color-text-faint)" }}>
        {label}
      </span>
      <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, fontSize: 12 }}>
        {value}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Daily detail — bars per day + cumulative MTD line; honors Range filter
// ---------------------------------------------------------------------------
function DailyDetail({
  daily, dateRange, platformFilter, studioFilter,
}: {
  daily: DailyRevenueSummary
  dateRange: DateRange
  platformFilter: string | null
  studioFilter: StudioFilter
}) {
  void studioFilter
  // Group by (date, platform) so each day's bar is a stack reflecting which
  // platforms contributed — this is the honest visual when daily feeds are
  // partial across SLR/POVR/VRPorn. Aggregating across all three would hide
  // which platform is silent on a given day.
  type DayCol = { date: string; total: number; byPlatform: Record<string, number> }
  const byDate = new Map<string, DayCol>()
  const platformsPresent = new Set<string>()
  for (const r of daily.this_month) {
    const e = byDate.get(r.date) ?? { date: r.date, total: 0, byPlatform: {} }
    e.total += r.revenue
    e.byPlatform[r.platform] = (e.byPlatform[r.platform] ?? 0) + r.revenue
    byDate.set(r.date, e)
    platformsPresent.add(r.platform)
  }
  const days = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))

  // Honesty marker: which platforms are reporting daily, and which aren't.
  // Distinct from filteredDaily.this_month being empty — this badge stays
  // visible even when data exists, so the user never assumes completeness.
  const ALL_DAILY = ["slr", "povr", "vrporn"] as const
  // Honesty marker: render based on data shape, not user intent. Even when
  // a platform filter is active, if the underlying daily feed is partial
  // we surface that — the user shouldn't have to undo their filter to learn
  // the data behind the number is incomplete.
  const missing = ALL_DAILY.filter(p => !platformsPresent.has(p))
  const feedBadgeLabel = (() => {
    if (missing.length === 0) return null
    if (platformsPresent.size === 0) return "no daily feed"
    const have = [...platformsPresent].sort().map(p => PLATFORM_SHORT[p] ?? p).join(" + ")
    const lacking = missing.map(p => PLATFORM_SHORT[p]).join(" + ")
    return `${have} feed · ${lacking} pending`
  })()

  if (days.length === 0) {
    return (
      <Section title="Daily detail" subtitle="No daily rows in this range">
        <Empty>Daily data resumes when scrapes land. (POVR & SLR daily are still being wired.)</Empty>
      </Section>
    )
  }

  const max = Math.max(1, ...days.map(d => d.total))
  // Cumulative running total
  let runSum = 0
  const cumulative = days.map(d => { runSum += d.total; return { date: d.date, sum: runSum } })
  const maxCum = Math.max(1, runSum)

  // Stats banner for this range
  const total = days.reduce((acc, d) => acc + d.total, 0)
  const avg = total / days.length
  const bestIdx = days.reduce((a, d, i) => d.total > days[a].total ? i : a, 0)

  const subtitle = dateRange === "month"
    ? `${days.length} days · daily bars + cumulative MTD line`
    : `${DATE_RANGE_LABELS[dateRange]} · ${days.length} days · daily bars + cumulative line`

  // Build the SVG path (round joins) and end-cap dot for the cumulative line.
  // Using a `path` with linejoin=round renders cleaner than polyline.
  const cumPath = cumulative
    .map((c, i) => `${i === 0 ? "M" : "L"}${i + 0.5},${100 - (c.sum / maxCum) * 96}`)
    .join(" ")
  const lastCum = cumulative[cumulative.length - 1]
  const lastX = (cumulative.length - 1) + 0.5
  const lastY = 100 - (lastCum.sum / maxCum) * 96

  return (
    <Section
      title="Daily detail"
      subtitle={subtitle}
      badge={feedBadgeLabel ? <FeedBadge label={feedBadgeLabel} /> : undefined}
    >
      {/* Compact stats inline with subtitle. The global KPI band already
          shows Yesterday + Best Day MTD when range="month", so we don't
          repeat them here — the previous 4-tile row was duplicating the
          hero KPIs in the same viewport. When range != "month", the
          stats below are unique to the visible range and stay full. */}
      {dateRange === "month" ? (
        <div style={{
          display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap",
          fontSize: 11, color: "var(--color-text-muted)",
          padding: "8px 12px", marginBottom: 8,
          background: "var(--color-base)",
          border: "1px solid var(--color-border-subtle)",
        }}>
          <span>
            <span style={{ color: "var(--color-text-faint)", textTransform: "uppercase",
                            letterSpacing: "0.08em", fontWeight: 700, fontSize: 9 }}>
              MTD
            </span>{" "}
            <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text)", fontWeight: 700 }}>
              {fmtMoneyFull(total)}
            </span>
          </span>
          <span style={{ color: "var(--color-border)" }}>·</span>
          <span>
            <span style={{ color: "var(--color-text-faint)", textTransform: "uppercase",
                            letterSpacing: "0.08em", fontWeight: 700, fontSize: 9 }}>
              Daily avg
            </span>{" "}
            <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text)", fontWeight: 700 }}>
              {fmtMoneyFull(avg)}
            </span>{" "}
            <span style={{ color: "var(--color-text-faint)" }}>across {days.length} days</span>
          </span>
        </div>
      ) : (
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
          gap: 1, background: "var(--color-border-subtle)",
          marginBottom: 12,
        }}>
          <MiniStat
            kicker="Range total"
            value={fmtMoneyFull(total)}
            sub={platformFilter
              ? PLATFORM_LABEL[platformFilter]
              : `${[...platformsPresent].sort().map(p => PLATFORM_SHORT[p] ?? p).join(" + ")}${missing.length ? ` · ${missing.map(p => PLATFORM_SHORT[p]).join("+")} pending` : ""}`}
          />
          <MiniStat
            kicker="Daily avg"
            value={fmtMoneyFull(avg)}
            sub={`across ${days.length} days`}
          />
          <MiniStat
            kicker="Best day"
            value={fmtMoneyFull(days[bestIdx].total)}
            sub={prettyDate(days[bestIdx].date)}
            tone="ok"
          />
          <MiniStat
            kicker="Yesterday"
            value={fmtMoneyFull(daily.yesterday_total)}
            sub={prettyDate(daily.yesterday_date)}
          />
        </div>
      )}

      {/* Chart: stacked bars (per-platform contribution per day) + cumulative line */}
      <div style={{ position: "relative", height: 140 }}>
        {/* Y-axis baseline */}
        <div style={{
          position: "absolute", left: 0, right: 0, bottom: 22,
          height: 1, background: "var(--color-border-subtle)",
        }} />

        {/* Bars */}
        <div style={{
          display: "grid", gap: 2,
          gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))`,
          alignItems: "end",
          height: 100,
          position: "relative",
        }}>
          {days.map((d, i) => {
            const isBest = i === bestIdx
            const slr  = d.byPlatform.slr    ?? 0
            const povr = d.byPlatform.povr   ?? 0
            const vrp  = d.byPlatform.vrporn ?? 0
            const totalH = (d.total / max) * 96
            const tip = `${prettyDate(d.date)} · ${fmtMoneyFull(d.total)}`
              + (slr  ? `\nSLR ${fmtMoney(slr, true)}`    : "")
              + (povr ? `\nPOVR ${fmtMoney(povr, true)}`  : "")
              + (vrp  ? `\nVRPorn ${fmtMoney(vrp, true)}` : "")
            // Best-day differentiation: full opacity + lifted 2px (clarify
            // pass — was an outline that collided with MonthlyHero's
            // current-month outline meaning).
            return (
              <div key={d.date}
                title={tip}
                style={{
                  display: "flex", flexDirection: "column-reverse",
                  height: Math.max(2, totalH),
                  marginBottom: isBest ? -2 : 0,
                  opacity: isBest ? 1 : 0.78,
                  transition: "opacity 180ms ease",
                }}
              >
                {slr  > 0 && <div style={{ flex: slr,  background: PLATFORM_COLOR.slr    }} />}
                {povr > 0 && <div style={{ flex: povr, background: PLATFORM_COLOR.povr   }} />}
                {vrp  > 0 && <div style={{ flex: vrp,  background: PLATFORM_COLOR.vrporn }} />}
              </div>
            )
          })}
        </div>

        {/* Cumulative line — neutral text-muted (was lime, but lime is reserved
            for action affordances per CLAUDE.md). The line is information,
            not a CTA. */}
        <svg
          viewBox={`0 0 ${Math.max(1, days.length)} 100`}
          preserveAspectRatio="none"
          style={{ position: "absolute", inset: "0 0 40px 0", height: 100, width: "100%", pointerEvents: "none" }}
        >
          <path
            d={cumPath}
            fill="none"
            stroke="var(--color-text-muted)"
            strokeWidth={1.4}
            strokeLinejoin="round"
            strokeLinecap="round"
            strokeDasharray="3 2"
            vectorEffect="non-scaling-stroke"
            opacity={0.85}
          />
          <circle
            cx={lastX}
            cy={lastY}
            r={2.2}
            fill="var(--color-text)"
            stroke="var(--color-base)"
            strokeWidth={0.8}
            vectorEffect="non-scaling-stroke"
          />
        </svg>

        {/* X-axis range labels — cumulative readout uses small caps + weight,
            not color, to stay distinct without burning the action color. */}
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0,
                      display: "flex", justifyContent: "space-between",
                      fontSize: 10, fontFamily: "var(--font-mono)",
                      color: "var(--color-text-faint)" }}>
          <span>{prettyDate(days[0].date)}</span>
          <span style={{
            display: "flex", alignItems: "center", gap: 6,
            color: "var(--color-text-muted)",
            fontVariant: "small-caps",
            letterSpacing: "0.06em",
            fontWeight: 700,
          }}>
            <span style={{
              width: 10, height: 0,
              borderTop: "1.4px dashed var(--color-text-muted)",
              display: "inline-block",
            }} />
            cumulative {fmtMoney(runSum, true)}
          </span>
          <span>{prettyDate(days[days.length - 1].date)}</span>
        </div>
      </div>
    </Section>
  )
}

function MiniStat({ kicker, value, sub, tone }: {
  kicker: string; value: string; sub: string; tone?: "ok"
}) {
  return (
    <div style={{ background: "var(--color-surface)", padding: "10px 12px" }}>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.1em",
                    textTransform: "uppercase", color: "var(--color-text-faint)" }}>
        {kicker}
      </div>
      <div style={{
        fontFamily: "var(--font-mono)", fontSize: 14, fontWeight: 700,
        color: tone === "ok" ? "var(--color-ok)" : "var(--color-text)",
        marginTop: 2,
      }}>
        {value}
      </div>
      <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 2 }}>
        {sub}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Per-platform comparison: all-time, YTD, and YoY across all years
// ---------------------------------------------------------------------------
function PlatformComparison({
  platforms, platformFilter,
}: {
  platforms: RevenueDashboard["platforms"]
  platformFilter: string | null
}) {
  const years = useMemo(() => {
    const s = new Set<string>()
    for (const p of platforms) for (const y of Object.keys(p.yearly)) s.add(y)
    return [...s].sort()
  }, [platforms])

  // Empty state — was missing; an empty `platforms` produced an empty
  // tbody under just the header row, which read as a render bug.
  if (platforms.length === 0) {
    return (
      <Section title="Year-over-year" subtitle="No platforms in current filter">
        <Empty>No platform data matches this filter.</Empty>
      </Section>
    )
  }

  return (
    <Section title="Year-over-year" subtitle="Lifetime reference · totals row at bottom">
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
              <th style={{ ...thStyle, textAlign: "left" }}>Platform</th>
              <th style={{ ...thStyle, textAlign: "right" }}>All time</th>
              {years.map(y => (
                <th key={y} style={{ ...thStyle, textAlign: "right" }}>{y}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {platforms.map(p => (
              <tr key={p.platform} style={{ borderBottom: "1px solid var(--color-border-subtle)" }}>
                <td style={{ ...tdStyle, fontWeight: 600 }}>
                  <span style={{
                    display: "inline-block", width: 8, height: 8, borderRadius: 2,
                    background: PLATFORM_COLOR[p.platform] ?? "var(--color-text-faint)",
                    marginRight: 8, verticalAlign: "middle",
                  }} />
                  {PLATFORM_LABEL[p.platform] ?? p.platform}
                </td>
                <td style={{ ...tdStyle, textAlign: "right", fontWeight: 600, fontFamily: "var(--font-mono)" }}>
                  {fmtMoneyFull(p.all_time)}
                </td>
                {years.map(y => {
                  const v = p.yearly[y]
                  return (
                    <td key={y} style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)",
                                          color: v ? "var(--color-text)" : "var(--color-text-faint)" }}>
                      {v ? fmtMoney(v, true) : "—"}
                    </td>
                  )
                })}
              </tr>
            ))}
            {!platformFilter && platforms.length > 1 && (
              <tr style={{ borderTop: "2px solid var(--color-border)", background: "var(--color-base)" }}>
                <td style={{ ...tdStyle, fontWeight: 700, textTransform: "uppercase",
                              letterSpacing: "0.08em", fontSize: 11 }}>
                  Total
                </td>
                <td style={{ ...tdStyle, textAlign: "right", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                  {fmtMoneyFull(platforms.reduce((acc, p) => acc + p.all_time, 0))}
                </td>
                {years.map(y => {
                  const total = platforms.reduce((acc, p) => acc + (p.yearly[y] ?? 0), 0)
                  return (
                    <td key={y} style={{ ...tdStyle, textAlign: "right", fontWeight: 600,
                                          fontFamily: "var(--font-mono)" }}>
                      {fmtMoney(total, true)}
                    </td>
                  )
                })}
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Section>
  )
}

// ---------------------------------------------------------------------------
// Top earners table
// ---------------------------------------------------------------------------
function TopScenesTable({ scenes }: { scenes: SceneRevenueRow[] }) {
  if (scenes.length === 0) {
    return <Section title="Top earners"><Empty>No scenes match this filter.</Empty></Section>
  }
  return (
    <div style={{ border: "1px solid var(--color-border-subtle)" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead style={{ background: "var(--color-base)" }}>
          <tr>
            <th style={{ ...thStyle, textAlign: "left", width: 36 }}>#</th>
            <th style={{ ...thStyle, textAlign: "left" }}>Title</th>
            <th style={{ ...thStyle, textAlign: "left", width: 80 }}>Studio</th>
            <th style={{ ...thStyle, textAlign: "left", width: 100 }}>Platform</th>
            <th style={{ ...thStyle, textAlign: "right", width: 90 }}>Views</th>
            <th style={{ ...thStyle, textAlign: "right", width: 110 }}>Revenue</th>
          </tr>
        </thead>
        <tbody>
          {scenes.map((s, i) => (
            <tr key={`${s.platform}-${s.video_id}-${i}`}
                style={{ borderBottom: "1px solid var(--color-border-subtle)" }}>
              <td style={{ ...tdStyle, color: "var(--color-text-faint)" }}>{i + 1}</td>
              <td style={{ ...tdStyle, fontWeight: 500, maxWidth: 0, overflow: "hidden",
                            textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {s.title || s.video_id}
              </td>
              <td style={{ ...tdStyle, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                {s.studio || "—"}
              </td>
              <td style={{ ...tdStyle }}>
                <span style={{
                  display: "inline-block", width: 8, height: 8, borderRadius: 2,
                  background: PLATFORM_COLOR[s.platform] ?? "var(--color-text-faint)",
                  marginRight: 6, verticalAlign: "middle",
                }} />
                {PLATFORM_SHORT[s.platform] ?? s.platform}
              </td>
              <td style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)",
                            color: "var(--color-text-muted)" }}>
                {s.views ? s.views.toLocaleString() : "—"}
              </td>
              <td style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)",
                            fontWeight: 600 }}>
                {fmtMoneyFull(s.revenue)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Cross-platform matches table
// ---------------------------------------------------------------------------
function CrossPlatformTable({ rows, platformFilter }: {
  rows: CrossPlatformRevenueRow[]
  platformFilter: string | null
}) {
  if (rows.length === 0) {
    return <Section title="Cross-platform matches"><Empty>No cross-platform data yet.</Empty></Section>
  }
  // When a single platform is selected, hide the columns for the other
  // platforms — they'd be wasted whitespace since the filter already
  // restricted the row set.
  const showCol = (p: "slr" | "povr" | "vrporn") => !platformFilter || platformFilter === p
  return (
    <div style={{ border: "1px solid var(--color-border-subtle)" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead style={{ background: "var(--color-base)" }}>
          <tr>
            <th style={{ ...thStyle, textAlign: "left" }}>Title</th>
            <th style={{ ...thStyle, textAlign: "left", width: 70 }}>Studio</th>
            <th style={{ ...thStyle, textAlign: "left", width: 150 }}>Platforms</th>
            {showCol("slr")    && <th style={{ ...thStyle, textAlign: "right", width: 90 }}>SLR</th>}
            {showCol("povr")   && <th style={{ ...thStyle, textAlign: "right", width: 100 }}>POVR</th>}
            {showCol("vrporn") && <th style={{ ...thStyle, textAlign: "right", width: 100 }}>VRPorn</th>}
            <th style={{ ...thStyle, textAlign: "right", width: 110 }}>Lifetime</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.title}-${i}`}
                style={{ borderBottom: "1px solid var(--color-border-subtle)" }}>
              <td style={{ ...tdStyle, fontWeight: 500, maxWidth: 0, overflow: "hidden",
                            textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {r.title}
              </td>
              <td style={{ ...tdStyle, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                {r.studio || "—"}
              </td>
              <td style={{ ...tdStyle, color: "var(--color-text-muted)", fontSize: 11 }}>
                {r.platforms.join(" · ")}
              </td>
              {showCol("slr") && (
                <td style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)" }}>
                  {r.slr_total ? fmtMoneyFull(r.slr_total) : <span style={{ color: "var(--color-text-faint)" }}>—</span>}
                </td>
              )}
              {showCol("povr") && (
                <td style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)" }}>
                  {r.povr_total ? fmtMoneyFull(r.povr_total) : <span style={{ color: "var(--color-text-faint)" }}>—</span>}
                </td>
              )}
              {showCol("vrporn") && (
                <td style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)" }}>
                  {r.vrporn_total ? fmtMoneyFull(r.vrporn_total) : <span style={{ color: "var(--color-text-faint)" }}>—</span>}
                </td>
              )}
              <td style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)",
                            fontWeight: 700 }}>
                {fmtMoneyFull(r.lifetime_total)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Reusable bits
// ---------------------------------------------------------------------------
function Section({
  title, subtitle, children, badge,
}: {
  title: string
  subtitle?: string
  children: React.ReactNode
  badge?: React.ReactNode
}) {
  return (
    <section>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline",
                    marginBottom: 10, gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, minWidth: 0 }}>
          <h2 style={{
            fontFamily: "var(--font-display)",
            fontSize: 19, fontWeight: 700, letterSpacing: "-0.012em",
          }}>
            {title}
          </h2>
          {badge}
        </div>
        {subtitle && (
          <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{subtitle}</span>
        )}
      </div>
      <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border-subtle)",
                    padding: 16 }}>
        {children}
      </div>
    </section>
  )
}

// FeedBadge — a persistent honesty marker shown next to a section title
// when the underlying feed is partial. Distinct from the empty state, which
// only renders when there's no data; this one renders ALONGSIDE real data
// so the user never assumes "all platforms" when only one is reporting.
function FeedBadge({ label, tone = "warn" }: { label: string; tone?: "warn" | "info" }) {
  const color = tone === "warn" ? "var(--color-warn)" : "var(--color-text-muted)"
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontSize: 10, fontWeight: 700, letterSpacing: "0.04em",
      padding: "2px 8px",
      background: "color-mix(in srgb, var(--color-warn) 12%, transparent)",
      color,
      border: `1px solid color-mix(in srgb, ${color} 40%, transparent)`,
    }}>
      <AlertCircle size={10} />
      {label}
    </span>
  )
}

// Chip — used for filter buttons. Inactive state has a subtle border so
// it reads as a control. Active state gets a 2px lime underline (the
// "you are here" pattern from Linear) and a stronger text color. An
// optional `accent` color tints the underline to the platform/studio's
// own identity color when applicable, so an active POVR chip reads as
// "POVR is selected" without re-introducing lime confusion.
function Chip({
  isActive, onClick, label, accent, mono,
}: {
  isActive: boolean
  onClick: () => void
  label: React.ReactNode
  accent?: string
  mono?: boolean
}) {
  // Chip affordance:
  //   inactive  → subtle border so it reads as a button
  //   active    → keep border subtle (no double affordance) + 2px underline
  //               in the option's accent color (or lime for "All" / "All time")
  // The underline is the source of truth; we don't change the border on
  // activation, since the previous design did both jobs at once.
  const underline = isActive
    ? (accent ?? "var(--color-lime)")
    : "transparent"
  return (
    <button
      type="button"
      onClick={onClick}
      className={isActive ? "ec-chip-pulse" : undefined}
      style={{
        padding: "4px 10px", fontSize: 11, fontWeight: 600,
        background: isActive ? "var(--color-base)" : "transparent",
        color: isActive ? "var(--color-text)" : "var(--color-text-muted)",
        border: "1px solid var(--color-border-subtle)",
        boxShadow: `inset 0 -2px 0 ${underline}`,
        cursor: "pointer",
        fontFamily: mono ? "var(--font-mono)" : "inherit",
        transition: "color 100ms ease, background 100ms ease, box-shadow 180ms ease",
      }}
    >
      {label}
    </button>
  )
}

function SectionTab({ active, onClick, label, count }: {
  active: boolean; onClick: () => void; label: string; count: number
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: "6px 14px",
        fontSize: 12, fontWeight: 600,
        background: active ? "var(--color-surface)" : "transparent",
        color: active ? "var(--color-text)" : "var(--color-text-muted)",
        border: `1px solid ${active ? "var(--color-border)" : "var(--color-border-subtle)"}`,
        borderBottom: active ? "1px solid var(--color-surface)" : "1px solid var(--color-border-subtle)",
        cursor: "pointer",
        marginBottom: -1,
      }}
    >
      {label}
      <span style={{ marginLeft: 6, color: "var(--color-text-faint)", fontWeight: 500 }}>{count}</span>
    </button>
  )
}


function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: 32, textAlign: "center", color: "var(--color-text-faint)", fontSize: 13 }}>
      {children}
    </div>
  )
}

const thStyle: React.CSSProperties = {
  fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase",
  color: "var(--color-text-faint)", padding: "10px 12px",
}
const tdStyle: React.CSSProperties = {
  padding: "10px 12px", verticalAlign: "middle",
}
