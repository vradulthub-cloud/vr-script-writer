"use client"

import { useMemo, useState } from "react"
import type { Shoot } from "@/lib/api"
import { PageHeader } from "@/components/ui/page-header"
import { WeekCalendar } from "@/components/ui/week-calendar"

const AGING_OVERDUE_HOURS = 72

/** Prototype-style shoots overview: a big week calendar on top so editors see
 *  what's happening before diving into per-asset validation. The asset grid
 *  below is the single source of shoot-row truth — no duplicate roster. */
export function ShootsV2View({ initialShoots }: { initialShoots: Shoot[] }) {
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
        subtitle={`${statusCounts.inProgress} in progress · ${statusCounts.overdue} overdue · ${statusCounts.wrapped} wrapped`}
      />

      {/* Big calendar block with week stepper — unique overview surface. */}
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
          <CalendarOrEmpty shoots={initialShoots} weekStart={weekStart} />
        </div>
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

function getWeekNumber(d: Date): number {
  const tmp = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  tmp.setUTCDate(tmp.getUTCDate() + 4 - (tmp.getUTCDay() || 7))
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1))
  return Math.ceil(((tmp.getTime() - yearStart.getTime()) / 86400000 + 1) / 7)
}
