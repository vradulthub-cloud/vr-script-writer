"use client"

import { useMemo, useState } from "react"
import type { Shoot } from "@/lib/api"
import { studioAbbr, studioColor } from "@/lib/studio-colors"
import { PageHeader } from "@/components/ui/page-header"
import { WeekCalendar } from "@/components/ui/week-calendar"

const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"] as const
type StudioKey = (typeof STUDIOS)[number] | "All"
type StatusFilter = "All" | "InProgress" | "Overdue" | "Wrapped"

const AGING_OVERDUE_HOURS = 72

/** Prototype-style shoots page: filters + big week calendar + roster ctab.
 *  Only rendered when Eclatech V2 flag is on. Legacy ShootBoard (asset-edit
 *  grid) is still available with flag off. */
export function ShootsV2View({ initialShoots }: { initialShoots: Shoot[] }) {
  const [studio, setStudio] = useState<StudioKey>("All")
  const [status, setStatus] = useState<StatusFilter>("All")
  const [weekOffset, setWeekOffset] = useState(0)

  const weekStart = useMemo(() => {
    const s = startOfWeek(new Date())
    s.setDate(s.getDate() + weekOffset * 7)
    return s
  }, [weekOffset])
  const weekEnd = useMemo(() => {
    const e = new Date(weekStart)
    e.setDate(e.getDate() + 7)
    return e
  }, [weekStart])

  // Studio counts across all shoots (not filtered by week) to feed the chip bar
  const studioCounts = useMemo(() => {
    const out: Record<string, number> = { All: initialShoots.length }
    for (const s of STUDIOS) out[s] = 0
    for (const s of initialShoots) {
      const primary = s.scenes[0]?.studio
      if (primary && out[primary] !== undefined) out[primary] += 1
    }
    return out
  }, [initialShoots])

  // Apply studio + status filters
  const filtered = useMemo(() => {
    return initialShoots.filter(s => {
      if (studio !== "All" && s.scenes[0]?.studio !== studio) return false
      const rollup = rollupShoot(s)
      if (status === "InProgress" && !(rollup.progress > 0 && rollup.progress < 100)) return false
      if (status === "Overdue" && !(rollup.isOverdue)) return false
      if (status === "Wrapped" && !(rollup.progress === 100)) return false
      return true
    })
  }, [initialShoots, studio, status])

  const statusCounts = useMemo(() => {
    let inProgress = 0, overdue = 0, wrapped = 0
    for (const s of initialShoots) {
      const r = rollupShoot(s)
      if (r.progress === 100) wrapped += 1
      else if (r.isOverdue) overdue += 1
      else if (r.progress > 0) inProgress += 1
    }
    return { inProgress, overdue, wrapped }
  }, [initialShoots])

  const weekLabel = `${formatMonthDay(weekStart)} → ${formatMonthDay(new Date(weekEnd.getTime() - 1))}`
  const weekNumber = getWeekNumber(weekStart)

  return (
    <div>
      <PageHeader
        title="Shoot Tracker"
        eyebrow={`SCHEDULE · WEEK ${weekNumber} · ${initialShoots.length} SHOOTS`}
        subtitle={`${statusCounts.inProgress} in progress · ${statusCounts.overdue} overdue · ${statusCounts.wrapped} wrapped · asset grid below`}
      />

      {/* Chip filter bar */}
      <div className="ec-filters" style={{ marginBottom: 14 }}>
        <button type="button" className="ec-chip" data-on={studio === "All" ? "" : undefined} onClick={() => setStudio("All")}>
          All studios <span className="c">{studioCounts.All}</span>
        </button>
        {STUDIOS.map(s => (
          <button key={s} type="button" className="ec-chip" data-on={studio === s ? "" : undefined} onClick={() => setStudio(s)}>
            {studioAbbr(s)} <span className="c">{studioCounts[s] ?? 0}</span>
          </button>
        ))}
        <span style={{ flex: 1 }} />
        <button type="button" className="ec-chip" data-on={status === "InProgress" ? "" : undefined} onClick={() => setStatus(status === "InProgress" ? "All" : "InProgress")}>
          In progress <span className="c">{statusCounts.inProgress}</span>
        </button>
        <button type="button" className="ec-chip" data-on={status === "Overdue" ? "" : undefined} onClick={() => setStatus(status === "Overdue" ? "All" : "Overdue")}>
          Overdue <span className="c">{statusCounts.overdue}</span>
        </button>
        <button type="button" className="ec-chip" data-on={status === "Wrapped" ? "" : undefined} onClick={() => setStatus(status === "Wrapped" ? "All" : "Wrapped")}>
          Wrapped <span className="c">{statusCounts.wrapped}</span>
        </button>
      </div>

      {/* Big calendar block with week stepper */}
      <section className="ec-block" style={{ marginBottom: 20 }}>
        <header>
          <h2>
            <span className="num">W{weekNumber}</span>
            {weekLabel}
          </h2>
          <div className="act">
            <a onClick={() => setWeekOffset(w => w - 1)} style={{ cursor: "pointer" }}>‹ Prev</a>
            {weekOffset !== 0 && (
              <a onClick={() => setWeekOffset(0)} style={{ cursor: "pointer" }}>Today</a>
            )}
            <a onClick={() => setWeekOffset(w => w + 1)} style={{ cursor: "pointer" }}>Next ›</a>
          </div>
        </header>
        <div style={{ padding: 0 }}>
          <CalendarOrEmpty shoots={filtered} weekStart={weekStart} />
        </div>
      </section>

      {/* Active shoots roster */}
      <section className="ec-block">
        <header>
          <h2>Active shoots · Roster</h2>
          <div className="act">
            <span>{filtered.length} match{filtered.length === 1 ? "" : "es"}</span>
          </div>
        </header>
        {filtered.length === 0 ? (
          <div style={{ padding: "28px 16px", textAlign: "center", color: "var(--color-text-faint)", fontSize: 12 }}>
            No shoots match the current filters.
          </div>
        ) : (
          <RosterTable shoots={filtered} />
        )}
      </section>
    </div>
  )
}

/* ─── Sub-components ─────────────────────────────────────────────────── */

function CalendarOrEmpty({ shoots, weekStart }: { shoots: Shoot[]; weekStart: Date }) {
  // If no shoots fall in this week, WeekCalendar returns null — we want to
  // show an explicit empty slot inside the block rather than collapse it.
  const hasAny = shoots.some(s => {
    const t = Date.parse(s.shoot_date || "")
    const end = weekStart.getTime() + 7 * 86400000
    return Number.isFinite(t) && t >= weekStart.getTime() && t < end
  })
  if (!hasAny) {
    return (
      <div style={{ padding: "40px 16px", textAlign: "center", color: "var(--color-text-faint)", fontSize: 12, letterSpacing: "0.1em", textTransform: "uppercase" }}>
        No shoots scheduled this week
      </div>
    )
  }
  return <WeekCalendar shoots={shoots} weekStart={weekStart} showHeader={false} />
}

function RosterTable({ shoots }: { shoots: Shoot[] }) {
  const sorted = useMemo(
    () => [...shoots].sort((a, b) => (b.shoot_date || "").localeCompare(a.shoot_date || "")),
    [shoots]
  )
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="ec-ctab">
        <thead>
          <tr>
            <th>Studio</th>
            <th>Date</th>
            <th>Talent</th>
            <th className="num">Scenes</th>
            <th className="num">Progress</th>
            <th>Aging</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(s => {
            const rollup = rollupShoot(s)
            const primary = s.scenes[0]?.studio ?? ""
            const abbr = primary ? studioAbbr(primary) : "—"
            return (
              <tr key={s.shoot_id}>
                <td>
                  {primary && <span className={`ec-studio-chip ${abbr.toLowerCase()}`}>{abbr}</span>}
                </td>
                <td className="serif">{formatShortDate(s.shoot_date)}</td>
                <td>
                  <span style={{ color: "var(--color-text)" }}>{s.female_talent || "—"}</span>
                  {s.male_talent && <span className="dim"> / {s.male_talent}</span>}
                </td>
                <td className="num">{s.scenes.length}</td>
                <td className="num">
                  <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "flex-end" }}>
                    <span>{rollup.progress}%</span>
                    <div className="ec-bar" style={{ width: 60 }}>
                      <div
                        className={`seg-bar ${abbr.toLowerCase()}`}
                        style={{ width: `${rollup.progress}%`, background: studioColor(primary) }}
                      />
                    </div>
                  </div>
                </td>
                <td>
                  {rollup.isOverdue ? (
                    <span className="ec-age" data-hot>{Math.floor(s.aging_hours / 24)}d</span>
                  ) : (
                    <span className="ec-age">{s.aging_hours > 0 ? `${Math.floor(s.aging_hours / 24)}d` : "fresh"}</span>
                  )}
                </td>
                <td>
                  <span className={`ec-pill`} data-s={rollup.progress === 100 ? "ok" : rollup.isOverdue ? "err" : "progress"}>
                    <span className="d" />
                    {rollup.progress === 100 ? "WRAPPED" : rollup.isOverdue ? "OVERDUE" : "ACTIVE"}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/* ─── Helpers ────────────────────────────────────────────────────────── */

function rollupShoot(s: Shoot): { progress: number; isOverdue: boolean } {
  let validated = 0, total = 0
  for (const sc of s.scenes) {
    for (const a of sc.assets) {
      total += 1
      if (a.status === "validated") validated += 1
    }
  }
  const progress = total > 0 ? Math.round((validated / total) * 100) : 0
  const isOverdue = s.aging_hours >= AGING_OVERDUE_HOURS && progress < 100
  return { progress, isOverdue }
}

function startOfWeek(d: Date): Date {
  const out = new Date(d)
  out.setHours(0, 0, 0, 0)
  out.setDate(out.getDate() - out.getDay())
  return out
}

function formatMonthDay(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

function formatShortDate(raw: string): string {
  const t = Date.parse(raw)
  if (!Number.isFinite(t)) return raw || "—"
  return new Date(t).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })
}

function getWeekNumber(d: Date): number {
  const tmp = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  tmp.setUTCDate(tmp.getUTCDate() + 4 - (tmp.getUTCDay() || 7))
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1))
  return Math.ceil(((tmp.getTime() - yearStart.getTime()) / 86400000 + 1) / 7)
}
