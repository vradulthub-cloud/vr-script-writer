"use client"

import { useMemo, useState } from "react"
import type { Shoot } from "@/lib/api"
import { PageHeader } from "@/components/ui/page-header"
import { MonthCalendar } from "@/components/ui/month-calendar"
import { ShootModal } from "@/components/ui/shoot-modal"

const AGING_OVERDUE_HOURS = 72

/** Prototype-style shoots overview. The top block is a month grid so editors
 *  can see every active shoot in the month before diving into per-asset
 *  validation. The asset board below owns per-shoot detail. */
export function ShootsV2View({ initialShoots }: { initialShoots: Shoot[] }) {
  const [monthOffset, setMonthOffset] = useState(0)
  const [selected, setSelected] = useState<Shoot | null>(null)

  const monthStart = useMemo(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth() + monthOffset, 1)
  }, [monthOffset])

  const monthEnd = useMemo(() => {
    return new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 1)
  }, [monthStart])

  const monthLabel = monthStart.toLocaleDateString("en-US", { month: "long", year: "numeric" }).toUpperCase()

  // Shoots active in this month. A shoot is "active" if its date falls within
  // the month OR it's still open (<100% assets validated) at the end of the
  // month — catches lingering post-production.
  const activeShoots = useMemo(() => {
    return initialShoots.filter(s => {
      const t = Date.parse(s.shoot_date || "")
      if (!Number.isFinite(t)) return false
      return t >= monthStart.getTime() && t < monthEnd.getTime()
    })
  }, [initialShoots, monthStart, monthEnd])

  const statusCounts = useMemo(() => {
    let inProgress = 0, overdue = 0, wrapped = 0
    for (const s of activeShoots) {
      const r = rollupShoot(s)
      if (r.progress === 100) wrapped += 1
      else if (r.isOverdue) overdue += 1
      else inProgress += 1
    }
    return { inProgress, overdue, wrapped }
  }, [activeShoots])

  return (
    <div>
      <PageHeader
        title="Shoot Tracker"
        eyebrow={`SCHEDULE · ${monthLabel} · ${activeShoots.length} SHOOTS`}
        subtitle={`${statusCounts.inProgress} in progress · ${statusCounts.overdue} overdue · ${statusCounts.wrapped} wrapped`}
      />

      <section className="ec-block" style={{ marginBottom: 20 }}>
        <header>
          <h2>
            <span className="num">{monthStart.toLocaleDateString("en-US", { month: "short" }).toUpperCase()}</span>
            {monthLabel}
          </h2>
          <div className="act">
            <a onClick={() => setMonthOffset(m => m - 1)} style={{ cursor: "pointer" }}>‹ Prev</a>
            {monthOffset !== 0 && (
              <a onClick={() => setMonthOffset(0)} style={{ cursor: "pointer" }}>Today</a>
            )}
            <a onClick={() => setMonthOffset(m => m + 1)} style={{ cursor: "pointer" }}>Next ›</a>
          </div>
        </header>
        <div style={{ padding: 0 }}>
          {activeShoots.length === 0 ? (
            <div
              style={{
                padding: "40px 16px",
                textAlign: "center",
                color: "var(--color-text-faint)",
                fontSize: 12,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              No shoots scheduled this month
            </div>
          ) : (
            <MonthCalendar
              shoots={activeShoots}
              monthStart={monthStart}
              onSelect={setSelected}
            />
          )}
        </div>
      </section>

      {selected && <ShootModal shoot={selected} onClose={() => setSelected(null)} />}
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
