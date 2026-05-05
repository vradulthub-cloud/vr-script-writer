"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { ArrowLeft, TrendingDown, TrendingUp, Calendar, Filter } from "lucide-react"
import type {
  RevenueDashboard,
  SceneRevenueRow,
  CrossPlatformRevenueRow,
  RevenueMonthlyPoint,
  DailyRevenueSummary,
  DailyRevenueRow,
} from "@/lib/api"

// Date-range presets for the daily view. Values are ISO offsets from "today";
// "all" means: don't filter, show whatever the API returned.
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

// Studio identity colors — the brand spec keeps these as contextual anchors.
// Platform tints reuse the studio palette: SLR ≈ lime (default), POVR purple,
// VRPorn pink. Reasonable substitutes that don't collide with status colors.
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
  if (n === null) return "—"
  const sign = n > 0 ? "+" : ""
  return `${sign}${n.toFixed(1)}%`
}

function fmtMonth(ym: string): string {
  // "2026-03" → "Mar '26"
  const [y, m] = ym.split("-")
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
  return `${months[parseInt(m, 10) - 1]} '${y.slice(2)}`
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

  const filteredTopScenes = useMemo(() => {
    let out = topScenes
    if (platformFilter) out = out.filter(s => s.platform === platformFilter)
    if (studioFilter)   out = out.filter(s => s.studio.toUpperCase() === studioFilter.toUpperCase())
    return out
  }, [topScenes, platformFilter, studioFilter])

  const filteredCrossPlatform = useMemo(() => {
    if (!studioFilter) return crossPlatform
    return crossPlatform.filter(r => r.studio.toUpperCase() === studioFilter.toUpperCase())
  }, [crossPlatform, studioFilter])

  // Apply date-range + platform filter to the daily payload. The API
  // already sliced "yesterday" + "this month"; for "Last 7"/"Last 30"/
  // "All" we re-derive from `daily.this_month` (today = ~20 most-recent
  // rows). Studio filter is intentionally NOT applied because daily rows
  // currently always carry studio="All" — once per-studio scrape lands
  // we can extend this.
  const filteredDaily = useMemo(() => {
    if (!daily) return null
    let yesterdayRows = daily.yesterday
    let monthRows = daily.this_month

    // Date-range filter — shrink monthRows to the window
    if (dateRange === "7d" || dateRange === "30d") {
      const days = dateRange === "7d" ? 7 : 30
      const cutoff = (() => {
        const d = new Date()
        d.setUTCHours(0, 0, 0, 0)
        d.setUTCDate(d.getUTCDate() - days)
        return d.toISOString().slice(0, 10)
      })()
      monthRows = monthRows.filter(r => r.date >= cutoff)
    }

    // Platform filter — when set, drop rows from other platforms
    if (platformFilter) {
      yesterdayRows = yesterdayRows.filter(r => r.platform === platformFilter)
      monthRows     = monthRows.filter(r => r.platform === platformFilter)
    }

    return {
      ...daily,
      yesterday: yesterdayRows,
      yesterday_total: yesterdayRows.reduce((acc, r) => acc + r.revenue, 0),
      this_month: monthRows,
      this_month_total: monthRows.reduce((acc, r) => acc + r.revenue, 0),
    }
  }, [daily, dateRange, platformFilter])

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

      {/* Sticky filter bar — single source of truth for date range, studio,
          platform across all sections. Sticks under the topbar so
          adjustments stay visible while you scroll the dense tables below. */}
      <FilterBar
        dateRange={dateRange}
        setDateRange={setDateRange}
        studio={studioFilter}
        setStudio={setStudioFilter}
        platform={platformFilter}
        setPlatform={setPlatformFilter}
      />

      {/* Totals strip */}
      <TotalsStrip dashboard={dashboard} />

      {/* Daily snapshot — only renders when _DailyData has data. */}
      {filteredDaily && filteredDaily.yesterday.length > 0 && (
        <DailySnapshot daily={filteredDaily} dateRange={dateRange} />
      )}

      {/* Per-platform comparison */}
      <PlatformComparison dashboard={dashboard} />

      {/* 12-month trend */}
      <MonthlyTrend points={dashboard.monthly_trend} />

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
}: {
  dateRange: DateRange
  setDateRange: (v: DateRange) => void
  studio: StudioFilter
  setStudio: (v: StudioFilter) => void
  platform: string | null
  setPlatform: (v: string | null) => void
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
      {/* Date range */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Calendar size={11} style={{ color: "var(--color-text-faint)" }} />
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                       textTransform: "uppercase", color: "var(--color-text-faint)" }}>
          Range
        </span>
        <div style={{ display: "flex", gap: 0 }}>
          {ranges.map(r => {
            const active = dateRange === r
            return (
              <button
                key={r}
                type="button"
                onClick={() => setDateRange(r)}
                style={{
                  padding: "4px 10px", fontSize: 11, fontWeight: 600,
                  background: active ? "var(--color-base)" : "transparent",
                  color: active ? "var(--color-text)" : "var(--color-text-muted)",
                  border: `1px solid ${active ? "var(--color-border)" : "transparent"}`,
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

      {/* Platform */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Filter size={11} style={{ color: "var(--color-text-faint)" }} />
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                       textTransform: "uppercase", color: "var(--color-text-faint)" }}>
          Platform
        </span>
        <div style={{ display: "flex", gap: 0 }}>
          {([null, "slr", "povr", "vrporn"] as (string | null)[]).map(opt => {
            const active = platform === opt
            return (
              <button
                key={opt ?? "all"}
                type="button"
                onClick={() => setPlatform(opt)}
                style={{
                  padding: "4px 10px", fontSize: 11, fontWeight: 600,
                  background: active ? "var(--color-base)" : "transparent",
                  color: active ? "var(--color-text)" : "var(--color-text-muted)",
                  border: `1px solid ${active ? "var(--color-border)" : "transparent"}`,
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

      {/* Studio */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                       textTransform: "uppercase", color: "var(--color-text-faint)" }}>
          Studio
        </span>
        <div style={{ display: "flex", gap: 0 }}>
          {[null, ...STUDIOS].map(opt => {
            const active = studio === opt
            return (
              <button
                key={opt ?? "all"}
                type="button"
                onClick={() => setStudio(opt as StudioFilter)}
                style={{
                  padding: "4px 10px", fontSize: 11, fontWeight: 600,
                  background: active ? "var(--color-base)" : "transparent",
                  color: active ? "var(--color-text)" : "var(--color-text-muted)",
                  border: `1px solid ${active ? "var(--color-border)" : "transparent"}`,
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
    </div>
  )
}

// ---------------------------------------------------------------------------
// Top totals strip — 4 huge $$$ tiles
// ---------------------------------------------------------------------------
function TotalsStrip({ dashboard }: { dashboard: RevenueDashboard }) {
  const tiles = [
    { label: "Grand Total",  value: dashboard.grand_total, sub: "all platforms · all time" },
    { label: "2026 YTD",     value: dashboard.ytd_total,    sub: "Jan – present" },
    ...dashboard.platforms.slice(0, 2).map(p => ({
      label: PLATFORM_LABEL[p.platform] ?? p.platform,
      value: p.all_time,
      sub: `2026 YTD ${fmtMoney(p.ytd, true)}`,
    })),
  ]
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 1,
      background: "var(--color-border-subtle)",
      border: "1px solid var(--color-border-subtle)",
    }}>
      {tiles.map((t, i) => (
        <div key={i} style={{
          background: "var(--color-surface)", padding: "20px 20px",
          display: "flex", flexDirection: "column", gap: 4,
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
                        textTransform: "uppercase", color: "var(--color-text-faint)" }}>
            {t.label}
          </div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 28, fontWeight: 600,
                        letterSpacing: "-0.015em", color: "var(--color-text)" }}>
            {fmtMoney(t.value)}
          </div>
          <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{t.sub}</div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Daily snapshot — yesterday's $ + this-month-daily mini chart
// ---------------------------------------------------------------------------
function DailySnapshot({ daily, dateRange }: { daily: DailyRevenueSummary; dateRange: DateRange }) {
  // Group daily rows by date so the mini-chart x-axis is one bar per day,
  // even when multiple platforms contribute (currently only VRPorn).
  const byDate = new Map<string, { date: string; total: number; rows: DailyRevenueRow[] }>()
  for (const r of daily.this_month) {
    const e = byDate.get(r.date) ?? { date: r.date, total: 0, rows: [] }
    e.total += r.revenue
    e.rows.push(r)
    byDate.set(r.date, e)
  }
  const days = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
  const max = Math.max(1, ...days.map(d => d.total))

  // Yesterday's per-platform breakdown (could be one row "All / vrporn" today
  // and grow to three rows once POVR + SLR daily land in _DailyData).
  const ySorted = [...daily.yesterday].sort((a, b) => b.revenue - a.revenue)

  return (
    <Section
      title="Daily snapshot"
      subtitle={`Yesterday · ${prettyDate(daily.yesterday_date)}`}
    >
      <div style={{ display: "grid", gridTemplateColumns: "minmax(160px, 220px) 1fr", gap: 24, alignItems: "center" }}>
        {/* Yesterday tile — big number + per-platform breakdown */}
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
                        textTransform: "uppercase", color: "var(--color-text-faint)" }}>
            Yesterday
          </div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 32, fontWeight: 600,
                        letterSpacing: "-0.015em", color: "var(--color-text)", marginTop: 4 }}>
            {fmtMoneyFull(daily.yesterday_total)}
          </div>
          <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 6 }}>
            {ySorted.map((r, i) => (
              <div key={`${r.platform}-${r.studio}-${i}`} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span>
                  <span style={{
                    display: "inline-block", width: 6, height: 6, borderRadius: 1,
                    background: PLATFORM_COLOR[r.platform] ?? "var(--color-text-faint)",
                    marginRight: 6, verticalAlign: "middle",
                  }} />
                  {PLATFORM_LABEL[r.platform] ?? r.platform}
                  {r.studio && r.studio !== "All" && <span style={{ color: "var(--color-text-faint)" }}> / {r.studio}</span>}
                </span>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{fmtMoneyFull(r.revenue)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* This-month daily bar chart */}
        <div style={{ borderLeft: "1px solid var(--color-border-subtle)", paddingLeft: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
                          textTransform: "uppercase", color: "var(--color-text-faint)" }}>
              {dateRange === "month"
                ? `This month · ${fmtMonth(daily.yesterday_date.slice(0, 7))}`
                : DATE_RANGE_LABELS[dateRange]}
              <span style={{ marginLeft: 8, color: "var(--color-text-faint)", fontWeight: 500, letterSpacing: 0 }}>
                · {days.length} days
              </span>
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600 }}>
              {fmtMoneyFull(daily.this_month_total)}
            </div>
          </div>
          {days.length === 0 ? (
            <Empty>No daily rows yet for this month.</Empty>
          ) : (
            <div style={{
              display: "grid", gap: 3,
              gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))`,
              alignItems: "end", height: 80,
            }}>
              {days.map(d => {
                const h = (d.total / max) * 76
                return (
                  <div key={d.date}
                    title={`${prettyDate(d.date)} · ${fmtMoneyFull(d.total)}`}
                    style={{
                      height: Math.max(2, h),
                      background: PLATFORM_COLOR.vrporn,
                      opacity: 0.85,
                      transition: "opacity 120ms ease",
                    }}
                  />
                )
              })}
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4,
                        fontSize: 10, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)" }}>
            <span>{days.length > 0 ? prettyDate(days[0].date) : ""}</span>
            <span>{days.length > 0 ? prettyDate(days[days.length - 1].date) : ""}</span>
          </div>
        </div>
      </div>
    </Section>
  )
}

function prettyDate(iso: string): string {
  // "2026-04-30" → "Apr 30"
  if (!iso || iso.length < 10) return iso
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
  const [y, m, d] = iso.split("-")
  void y
  return `${months[parseInt(m, 10) - 1]} ${parseInt(d, 10)}`
}

// ---------------------------------------------------------------------------
// Per-platform comparison: all-time, YTD, and YoY across all years
// ---------------------------------------------------------------------------
function PlatformComparison({ dashboard }: { dashboard: RevenueDashboard }) {
  // Years across all platforms, sorted ascending
  const years = useMemo(() => {
    const s = new Set<string>()
    for (const p of dashboard.platforms) for (const y of Object.keys(p.yearly)) s.add(y)
    return [...s].sort()
  }, [dashboard.platforms])

  return (
    <Section title="Platform comparison" subtitle="Year-over-year revenue per platform · totals row at bottom">
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
            {dashboard.platforms.map(p => (
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
            {/* Totals row */}
            <tr style={{ borderTop: "2px solid var(--color-border)", background: "var(--color-base)" }}>
              <td style={{ ...tdStyle, fontWeight: 700, textTransform: "uppercase",
                            letterSpacing: "0.08em", fontSize: 11 }}>
                Total
              </td>
              <td style={{ ...tdStyle, textAlign: "right", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                {fmtMoneyFull(dashboard.grand_total)}
              </td>
              {years.map(y => {
                const total = dashboard.platforms.reduce((acc, p) => acc + (p.yearly[y] ?? 0), 0)
                return (
                  <td key={y} style={{ ...tdStyle, textAlign: "right", fontWeight: 600,
                                        fontFamily: "var(--font-mono)" }}>
                    {fmtMoney(total, true)}
                  </td>
                )
              })}
            </tr>
          </tbody>
        </table>
      </div>
    </Section>
  )
}

// ---------------------------------------------------------------------------
// 12-month rolling trend — stacked bars + MoM delta
// ---------------------------------------------------------------------------
function MonthlyTrend({ points }: { points: RevenueMonthlyPoint[] }) {
  const max = Math.max(1, ...points.map(p => p.total))
  return (
    <Section title="12-month trend" subtitle="Stacked monthly revenue · MoM delta below each bar">
      <div style={{
        display: "grid",
        gridTemplateColumns: `repeat(${points.length}, minmax(0, 1fr))`,
        gap: 8, alignItems: "end",
        padding: "16px 0", minHeight: 220,
      }}>
        {points.map(p => {
          const slrH = (p.slr / max) * 160
          const povrH = (p.povr / max) * 160
          const vrpH = (p.vrporn / max) * 160
          return (
            <div key={p.month} style={{ display: "flex", flexDirection: "column", alignItems: "stretch", gap: 4 }}>
              <div style={{ fontSize: 10, color: "var(--color-text)", textAlign: "center",
                            fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                {fmtMoney(p.total, true)}
              </div>
              <div style={{ display: "flex", flexDirection: "column-reverse", height: 160,
                            justifyContent: "flex-start" }}>
                {p.slr > 0    && <div style={{ height: slrH,  background: PLATFORM_COLOR.slr }}    title={`SLR ${fmtMoney(p.slr, true)}`} />}
                {p.povr > 0   && <div style={{ height: povrH, background: PLATFORM_COLOR.povr }}   title={`POVR ${fmtMoney(p.povr, true)}`} />}
                {p.vrporn > 0 && <div style={{ height: vrpH,  background: PLATFORM_COLOR.vrporn }} title={`VRPorn ${fmtMoney(p.vrporn, true)}`} />}
              </div>
              <div style={{ fontSize: 10, color: "var(--color-text-muted)", textAlign: "center" }}>
                {fmtMonth(p.month)}
              </div>
              <div style={{ fontSize: 10, textAlign: "center",
                            color: p.mom_pct === null
                              ? "var(--color-text-faint)"
                              : p.mom_pct >= 0 ? "var(--color-ok)" : "var(--color-err)",
                            fontFamily: "var(--font-mono)" }}>
                {p.mom_pct !== null && (p.mom_pct >= 0
                  ? <TrendingUp size={9} style={{ display: "inline", verticalAlign: -1, marginRight: 2 }} />
                  : <TrendingDown size={9} style={{ display: "inline", verticalAlign: -1, marginRight: 2 }} />)}
                {fmtPct(p.mom_pct)}
              </div>
            </div>
          )
        })}
      </div>
      {/* Legend */}
      <div style={{ display: "flex", gap: 16, fontSize: 11, color: "var(--color-text-muted)",
                    paddingTop: 8, borderTop: "1px solid var(--color-border-subtle)" }}>
        {(["slr", "povr", "vrporn"] as const).map(p => (
          <span key={p} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 10, height: 10, background: PLATFORM_COLOR[p], display: "inline-block" }} />
            {PLATFORM_LABEL[p]}
          </span>
        ))}
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
                {PLATFORM_LABEL[s.platform] ?? s.platform}
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
