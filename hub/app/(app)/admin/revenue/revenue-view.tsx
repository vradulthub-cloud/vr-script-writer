"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { ArrowLeft, TrendingDown, TrendingUp, Calendar, Filter, Sparkles } from "lucide-react"
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

// Platform identity — reuses studio palette as anchors.
const PLATFORM_COLOR: Record<string, string> = {
  slr:    "var(--color-lime)",
  povr:   "var(--color-vrh)",
  vrporn: "var(--color-vra)",
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
  const [activeSection, setActiveSection] = useState<"top" | "cross">("top")
  const [platformFilter, setPlatformFilter] = useState<string | null>(null)
  const [studioFilter, setStudioFilter] = useState<StudioFilter>(null)
  const [dateRange, setDateRange] = useState<DateRange>("month")

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

  const refreshedAgo = (() => {
    try {
      const ts = new Date(dashboard.refreshed_at).getTime()
      const ageMin = Math.max(0, Math.round((Date.now() - ts) / 60_000))
      if (ageMin < 1)   return "just now"
      if (ageMin < 60)  return `${ageMin} min ago`
      const h = Math.round(ageMin / 60)
      return `${h}h ago`
    } catch {
      return "—"
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

  // Monthly trend: zero out non-selected platforms when a platform is filtered.
  const filteredMonthly = useMemo(() => {
    if (!platformFilter) return dashboard.monthly_trend
    return dashboard.monthly_trend.map(p => ({
      month: p.month,
      slr:    platformFilter === "slr"    ? p.slr    : 0,
      povr:   platformFilter === "povr"   ? p.povr   : 0,
      vrporn: platformFilter === "vrporn" ? p.vrporn : 0,
      total:  platformFilter === "slr" ? p.slr : platformFilter === "povr" ? p.povr : p.vrporn,
      mom_pct: p.mom_pct,
    }))
  }, [dashboard.monthly_trend, platformFilter])

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
      {/* Header */}
      <div>
        <Link href="/admin" style={{
          fontSize: 11, color: "var(--color-text-muted)", textDecoration: "none",
          letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 600,
        }}>
          <ArrowLeft size={11} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
          Admin
        </Link>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4 }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.18em", textTransform: "uppercase",
                          color: "var(--color-text-muted)" }}>
              Premium Breakdowns · SLR · POVR · VRPorn
            </div>
            <h1 style={{ fontFamily: "var(--font-display)", fontSize: 32, fontWeight: 600,
                         letterSpacing: "-0.015em", marginTop: 4 }}>
              Revenue
            </h1>
          </div>
          <div style={{ fontSize: 11, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)" }}>
            Refreshed {refreshedAgo}
          </div>
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
      <MonthlyHero points={filteredMonthly} platformFilter={platformFilter} />

      {/* Per-platform monthly cards — how each platform's portal shows it */}
      <PlatformMonthlyCards
        platforms={dashboard.platforms}
        monthly={dashboard.monthly_trend}
        platformFilter={platformFilter}
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
        : <CrossPlatformTable rows={filteredCrossPlatform} />}
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
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Calendar size={11} style={{ color: "var(--color-text-faint)" }} />
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                       textTransform: "uppercase", color: "var(--color-text-faint)" }}>
          Range
        </span>
        <div style={{ display: "flex", gap: 0 }}>
          {ranges.map(r => {
            const isActive = dateRange === r
            return (
              <button
                key={r}
                type="button"
                onClick={() => setDateRange(r)}
                style={{
                  padding: "4px 10px", fontSize: 11, fontWeight: 600,
                  background: isActive ? "var(--color-base)" : "transparent",
                  color: isActive ? "var(--color-text)" : "var(--color-text-muted)",
                  border: `1px solid ${isActive ? "var(--color-border)" : "transparent"}`,
                  cursor: "pointer",
                }}
              >
                {DATE_RANGE_LABELS[r]}
              </button>
            )
          })}
        </div>
      </div>

      <div style={{ height: 16, width: 1, background: "var(--color-border-subtle)" }} />

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Filter size={11} style={{ color: "var(--color-text-faint)" }} />
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                       textTransform: "uppercase", color: "var(--color-text-faint)" }}>
          Platform
        </span>
        <div style={{ display: "flex", gap: 0 }}>
          {([null, "slr", "povr", "vrporn"] as (string | null)[]).map(opt => {
            const isActive = platform === opt
            return (
              <button
                key={opt ?? "all"}
                type="button"
                onClick={() => setPlatform(opt)}
                style={{
                  padding: "4px 10px", fontSize: 11, fontWeight: 600,
                  background: isActive ? "var(--color-base)" : "transparent",
                  color: isActive ? "var(--color-text)" : "var(--color-text-muted)",
                  border: `1px solid ${isActive ? "var(--color-border)" : "transparent"}`,
                  cursor: "pointer",
                }}
              >
                {opt
                  ? <>
                      <span style={{
                        display: "inline-block", width: 6, height: 6, borderRadius: 1,
                        background: PLATFORM_COLOR[opt],
                        marginRight: 6, verticalAlign: "middle",
                      }} />
                      {PLATFORM_LABEL[opt]}
                    </>
                  : "All"}
              </button>
            )
          })}
        </div>
      </div>

      <div style={{ height: 16, width: 1, background: "var(--color-border-subtle)" }} />

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                       textTransform: "uppercase", color: "var(--color-text-faint)" }}>
          Studio
        </span>
        <div style={{ display: "flex", gap: 0 }}>
          {[null, ...STUDIOS].map(opt => {
            const isActive = studio === opt
            return (
              <button
                key={opt ?? "all"}
                type="button"
                onClick={() => setStudio(opt as StudioFilter)}
                style={{
                  padding: "4px 10px", fontSize: 11, fontWeight: 600,
                  background: isActive ? "var(--color-base)" : "transparent",
                  color: isActive ? "var(--color-text)" : "var(--color-text-muted)",
                  border: `1px solid ${isActive ? "var(--color-border)" : "transparent"}`,
                  cursor: "pointer",
                  fontFamily: opt ? "var(--font-mono)" : "inherit",
                }}
              >
                {opt ?? "All"}
              </button>
            )
          })}
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

  // Build tiles. Always 4-up so the strip stays rhythmic.
  const monthLabel = last ? fmtMonthLong(last.month) : "—"
  const tiles: KpiTile[] = [
    {
      kicker: matchesCurrent ? `${monthLabel} · MTD` : monthLabel,
      value:  fmtMoneyFull(last?.total ?? 0),
      delta:  last?.mom_pct ?? null,
      sub:    prev ? `vs ${fmtMonthLong(prev.month)} ${fmtMoney(prev.total, true)}` : "—",
      tint:   "default",
    },
    {
      kicker: matchesCurrent ? "Projected EOM" : "Last full month",
      value:  fmtMoneyFull(matchesCurrent ? projected : (prev?.total ?? 0)),
      delta:  matchesCurrent ? projVsPrev : null,
      sub:    matchesCurrent
        ? `${dayOfMonth}/${dim} days elapsed · linear pace`
        : prev ? `${fmtMonthLong(prev.month)} closed` : "—",
      tint:   "muted",
    },
    {
      kicker: yDate ? `Yesterday · ${prettyDate(yDate)}` : "Yesterday",
      value:  fmtMoneyFull(yTotal),
      delta:  wowPct,
      sub:    wowPct !== null ? `vs ${prettyDate(sevenBack)} ${fmtMoney(wowTotal, true)}` : feedLabel,
      tint:   "default",
    },
    {
      kicker: "Best day MTD",
      value:  bestTotal ? fmtMoneyFull(bestTotal) : "—",
      delta:  null,
      sub:    bestDate ? `${prettyDate(bestDate)} · ${feedLabel}` : "no daily rows",
      tint:   "muted",
    },
  ]

  // Footer line with grand totals — keeps the historical anchor visible.
  return (
    <div>
      <div style={{
        display: "grid",
        gridTemplateColumns: `repeat(${tiles.length}, minmax(0, 1fr))`,
        gap: 1,
        background: "var(--color-border-subtle)",
        border: "1px solid var(--color-border-subtle)",
      }}>
        {tiles.map((t, i) => (
          <KpiTileView key={i} tile={t} />
        ))}
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
  value:  string
  delta:  number | null
  sub:    string
  tint:   "default" | "muted"
}

function KpiTileView({ tile }: { tile: KpiTile }) {
  const TrendIcon = tile.delta === null
    ? null
    : tile.delta >= 0 ? TrendingUp : TrendingDown
  const trendColor = tile.delta === null
    ? "var(--color-text-faint)"
    : tile.delta >= 0 ? "var(--color-ok)" : "var(--color-err)"
  return (
    <div style={{
      background: tile.tint === "muted" ? "var(--color-base)" : "var(--color-surface)",
      padding: "20px 20px",
      display: "flex", flexDirection: "column", gap: 4,
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
                    textTransform: "uppercase", color: "var(--color-text-faint)" }}>
        {tile.kicker}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <div style={{ fontFamily: "var(--font-display)", fontSize: 30, fontWeight: 600,
                      letterSpacing: "-0.015em", color: "var(--color-text)" }}>
          {tile.value}
        </div>
        {tile.delta !== null && TrendIcon && (
          <span style={{
            fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700,
            color: trendColor, display: "flex", alignItems: "center", gap: 2,
          }}>
            <TrendIcon size={12} style={{ verticalAlign: -1 }} />
            {fmtPct(tile.delta)}
          </span>
        )}
      </div>
      <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{tile.sub}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Monthly hero — taller, current-month highlighted, MoM% under each bar
// ---------------------------------------------------------------------------
function MonthlyHero({
  points, platformFilter,
}: {
  points: RevenueMonthlyPoint[]
  platformFilter: string | null
}) {
  // Trim leading-zero months when filtered to a platform that started
  // mid-period (e.g. VRPorn launched Sep 2025).
  const trimmed = useMemo(() => {
    if (!platformFilter) return points
    let i = 0
    while (i < points.length && points[i].total === 0) i++
    return points.slice(i)
  }, [points, platformFilter])

  if (trimmed.length === 0) {
    return (
      <Section title="Monthly trend" subtitle="No data in range">
        <Empty>No months match this filter.</Empty>
      </Section>
    )
  }

  const max = Math.max(1, ...trimmed.map(p => p.total))
  const lastIdx = trimmed.length - 1
  const subtitle = platformFilter
    ? `${PLATFORM_LABEL[platformFilter] ?? platformFilter} only · ${trimmed.length} months · current month highlighted`
    : `Stacked by platform · ${trimmed.length} months · current month highlighted`

  // Y-axis tick lines at 0 / 50% / 100% to give scale anchoring.
  const ticks = [0, 0.5, 1]
  const chartHeight = 240

  return (
    <Section title="Monthly trend" subtitle={subtitle}>
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
                {/* Stacked bars (column-reverse so SLR is at bottom) */}
                <div style={{
                  display: "flex", flexDirection: "column-reverse",
                  height: chartHeight - 60,
                  justifyContent: "flex-start",
                  position: "relative",
                  outline: isCurrent ? "1px solid var(--color-text)" : "none",
                  outlineOffset: 1,
                }}>
                  {p.slr > 0    && <div style={{ height: slrH,  background: PLATFORM_COLOR.slr,    opacity: isCurrent ? 1 : 0.85 }} title={`SLR ${fmtMoney(p.slr, true)}`} />}
                  {p.povr > 0   && <div style={{ height: povrH, background: PLATFORM_COLOR.povr,   opacity: isCurrent ? 1 : 0.85 }} title={`POVR ${fmtMoney(p.povr, true)}`} />}
                  {p.vrporn > 0 && <div style={{ height: vrpH,  background: PLATFORM_COLOR.vrporn, opacity: isCurrent ? 1 : 0.85 }} title={`VRPorn ${fmtMoney(p.vrporn, true)}`} />}
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
                {/* MoM% delta */}
                <div style={{
                  fontSize: 10, textAlign: "center",
                  color: p.mom_pct === null
                    ? "var(--color-text-faint)"
                    : p.mom_pct >= 0 ? "var(--color-ok)" : "var(--color-err)",
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
  platforms, monthly, platformFilter,
}: {
  platforms: RevenueDashboard["platforms"]
  monthly: RevenueMonthlyPoint[]
  platformFilter: string | null
}) {
  // Order: SLR, POVR, VRPorn (matches platform color sequence + chronology)
  const order = ["slr", "povr", "vrporn"]
  const ordered = order
    .map(slug => platforms.find(p => p.platform === slug))
    .filter(Boolean) as RevenueDashboard["platforms"]

  const visible = platformFilter ? ordered.filter(p => p.platform === platformFilter) : ordered
  if (visible.length === 0) return null

  return (
    <Section
      title="Per-platform"
      subtitle="This month vs last · 12-month sparkline · all-time anchor"
    >
      <div style={{
        display: "grid",
        gridTemplateColumns: `repeat(${visible.length}, minmax(0, 1fr))`,
        gap: 1,
        background: "var(--color-border-subtle)",
        margin: -16, // bleed into Section's padding for a cleaner edge-to-edge grid
      }}>
        {visible.map(p => (
          <PlatformCard key={p.platform} platform={p} monthly={monthly} />
        ))}
      </div>
    </Section>
  )
}

function PlatformCard({
  platform, monthly,
}: {
  platform: RevenueDashboard["platforms"][number]
  monthly: RevenueMonthlyPoint[]
}) {
  const slug = platform.platform
  const series = monthly.map(m => ({
    month: m.month,
    value: slug === "slr" ? m.slr : slug === "povr" ? m.povr : m.vrporn,
  }))
  // Trim leading zeros (e.g. VRPorn before launch).
  let firstNonZero = 0
  while (firstNonZero < series.length && series[firstNonZero].value === 0) firstNonZero++
  const trimmed = series.slice(firstNonZero)

  const last = trimmed[trimmed.length - 1]
  const prev = trimmed[trimmed.length - 2]
  const mom = prev?.value ? pctDelta(last?.value ?? 0, prev.value) : null
  const max = Math.max(1, ...trimmed.map(s => s.value))

  // Lifetime + recency stats
  const last3 = trimmed.slice(-3)
  const last3Avg = last3.length ? last3.reduce((a, s) => a + s.value, 0) / last3.length : 0

  const color = PLATFORM_COLOR[slug] ?? "var(--color-text-faint)"
  const TrendIcon = mom === null
    ? null
    : mom >= 0 ? TrendingUp : TrendingDown
  const trendColor = mom === null
    ? "var(--color-text-faint)"
    : mom >= 0 ? "var(--color-ok)" : "var(--color-err)"

  return (
    <div style={{
      background: "var(--color-surface)",
      padding: 18,
      display: "flex", flexDirection: "column", gap: 12,
    }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 10, height: 10, background: color, display: "inline-block" }} />
          <span style={{ fontWeight: 700, fontSize: 13, letterSpacing: "0.02em" }}>
            {PLATFORM_LABEL[slug]}
          </span>
        </div>
        <span style={{
          fontSize: 10, fontFamily: "var(--font-mono)",
          color: "var(--color-text-faint)", letterSpacing: "0.04em",
        }}>
          {trimmed.length} mo
        </span>
      </div>

      {/* This month $ + delta */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
                      textTransform: "uppercase", color: "var(--color-text-faint)" }}>
          {last ? fmtMonthLong(last.month) : "—"}
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 2 }}>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 26, fontWeight: 600,
                        letterSpacing: "-0.015em" }}>
            {fmtMoneyFull(last?.value ?? 0)}
          </div>
          {mom !== null && TrendIcon && (
            <span style={{
              fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700,
              color: trendColor, display: "flex", alignItems: "center", gap: 2,
            }}>
              <TrendIcon size={11} style={{ verticalAlign: -1 }} />
              {fmtPct(mom)}
            </span>
          )}
        </div>
        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2 }}>
          {prev ? `vs ${fmtMonthLong(prev.month)} ${fmtMoney(prev.value, true)}` : "—"}
        </div>
      </div>

      {/* Sparkline — last N months as mini bars */}
      <div>
        <div style={{
          display: "grid", gap: 2,
          gridTemplateColumns: `repeat(${trimmed.length}, minmax(0, 1fr))`,
          alignItems: "end", height: 44,
        }}>
          {trimmed.map((s, i) => {
            const h = (s.value / max) * 40
            const isLast = i === trimmed.length - 1
            return (
              <div key={s.month}
                   title={`${fmtMonth(s.month)} · ${fmtMoneyFull(s.value)}`}
                   style={{
                     height: Math.max(2, h),
                     background: color,
                     opacity: isLast ? 1 : 0.55,
                   }}
              />
            )
          })}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4,
                      fontSize: 10, fontFamily: "var(--font-mono)",
                      color: "var(--color-text-faint)" }}>
          <span>{trimmed[0] ? fmtMonth(trimmed[0].month) : ""}</span>
          <span>{last ? fmtMonth(last.month) : ""}</span>
        </div>
      </div>

      {/* Footer stats */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8,
        paddingTop: 10, borderTop: "1px solid var(--color-border-subtle)",
        fontSize: 11,
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
  // Group by date so the chart x-axis is one bar per day even when multiple
  // platforms contribute (today only VRPorn, but we render as if all could).
  const byDate = new Map<string, { date: string; total: number; rows: DailyRevenueRow[] }>()
  for (const r of daily.this_month) {
    const e = byDate.get(r.date) ?? { date: r.date, total: 0, rows: [] }
    e.total += r.revenue
    e.rows.push(r)
    byDate.set(r.date, e)
  }
  const days = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))

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

  return (
    <Section title="Daily detail" subtitle={subtitle}>
      {/* Quick stats line above chart */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
        gap: 1, background: "var(--color-border-subtle)",
        marginBottom: 12,
      }}>
        <MiniStat
          kicker="Range total"
          value={fmtMoneyFull(total)}
          sub={platformFilter ? PLATFORM_LABEL[platformFilter] : "All platforms (where reported)"}
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

      {/* Chart: bars + cumulative line overlay */}
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
            const h = (d.total / max) * 96
            const isBest = i === bestIdx
            return (
              <div key={d.date}
                title={`${prettyDate(d.date)} · ${fmtMoneyFull(d.total)}`}
                style={{
                  height: Math.max(2, h),
                  background: PLATFORM_COLOR.vrporn,
                  opacity: isBest ? 1 : 0.78,
                  outline: isBest ? "1px solid var(--color-text)" : "none",
                  outlineOffset: 0,
                }}
              />
            )
          })}
        </div>

        {/* Cumulative line overlay (SVG) */}
        <svg
          viewBox={`0 0 ${days.length} 100`}
          preserveAspectRatio="none"
          style={{ position: "absolute", inset: "0 0 40px 0", height: 100, width: "100%", pointerEvents: "none" }}
        >
          <polyline
            fill="none"
            stroke="var(--color-lime)"
            strokeWidth={1.4}
            vectorEffect="non-scaling-stroke"
            points={cumulative.map((c, i) => `${i + 0.5},${100 - (c.sum / maxCum) * 96}`).join(" ")}
          />
        </svg>

        {/* X-axis range labels */}
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0,
                      display: "flex", justifyContent: "space-between",
                      fontSize: 10, fontFamily: "var(--font-mono)",
                      color: "var(--color-text-faint)" }}>
          <span>{prettyDate(days[0].date)}</span>
          <span style={{ color: "var(--color-lime)" }}>
            <Sparkles size={9} style={{ display: "inline", verticalAlign: -1, marginRight: 4 }} />
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
function CrossPlatformTable({ rows }: { rows: CrossPlatformRevenueRow[] }) {
  if (rows.length === 0) {
    return <Section title="Cross-platform matches"><Empty>No cross-platform data yet.</Empty></Section>
  }
  return (
    <div style={{ border: "1px solid var(--color-border-subtle)" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead style={{ background: "var(--color-base)" }}>
          <tr>
            <th style={{ ...thStyle, textAlign: "left" }}>Title</th>
            <th style={{ ...thStyle, textAlign: "left", width: 70 }}>Studio</th>
            <th style={{ ...thStyle, textAlign: "left", width: 150 }}>Platforms</th>
            <th style={{ ...thStyle, textAlign: "right", width: 90 }}>SLR</th>
            <th style={{ ...thStyle, textAlign: "right", width: 100 }}>POVR</th>
            <th style={{ ...thStyle, textAlign: "right", width: 100 }}>VRPorn</th>
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
              <td style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)" }}>
                {r.slr_total ? fmtMoneyFull(r.slr_total) : <span style={{ color: "var(--color-text-faint)" }}>—</span>}
              </td>
              <td style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)" }}>
                {r.povr_total ? fmtMoneyFull(r.povr_total) : <span style={{ color: "var(--color-text-faint)" }}>—</span>}
              </td>
              <td style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)" }}>
                {r.vrporn_total ? fmtMoneyFull(r.vrporn_total) : <span style={{ color: "var(--color-text-faint)" }}>—</span>}
              </td>
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
function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, letterSpacing: "-0.005em" }}>{title}</h2>
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
