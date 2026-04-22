"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import nextDynamic from "next/dynamic"
import { api, type Shoot } from "@/lib/api"
import { PageHeader } from "@/components/ui/page-header"
import { MonthCalendar } from "@/components/ui/month-calendar"
import { ShootModal } from "@/components/ui/shoot-modal"
import { AddEventModal } from "@/components/ui/add-event-modal"
import { studioColor } from "@/lib/studio-colors"
import { rowToEvent, type CalendarEvent } from "@/lib/calendar-events"

const ShootBoard = nextDynamic(() => import("./shoot-board").then(m => m.ShootBoard))

const AGING_OVERDUE_HOURS = 72
const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"] as const
type StudioFilter = "All" | (typeof STUDIOS)[number]

/** Prototype-style shoots overview. The studio filter lives at the top of
 *  the page and drives BOTH the calendar and the roster below — one pick,
 *  both views update.
 */
export function ShootsV2View({
  initialShoots,
  idToken,
  boardError,
}: {
  initialShoots: Shoot[]
  idToken?: string
  boardError: string | null
}) {
  const [monthOffset, setMonthOffset] = useState(0)
  const [selected, setSelected] = useState<Shoot | null>(null)
  const [studioFilter, setStudioFilter] = useState<StudioFilter>("All")
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [addEventDate, setAddEventDate] = useState<string | null>(null)
  const [eventsError, setEventsError] = useState<string | null>(null)

  const client = useMemo(() => api(idToken ?? null), [idToken])

  const refreshEvents = useCallback(async () => {
    try {
      const rows = await client.calendarEvents.list()
      setEvents(rows.map(rowToEvent))
      setEventsError(null)
    } catch (err) {
      // Non-fatal — the calendar still shows shoots + holidays, and the user
      // can retry by creating/deleting an event (which also refreshes).
      setEventsError(err instanceof Error ? err.message : "Failed to load events")
    }
  }, [client])

  useEffect(() => { refreshEvents() }, [refreshEvents])

  // Viewport-aware view mode. The 7×5 month grid is unreadable on a narrow
  // phone — each cell becomes a ~50px postage stamp. On mobile we default
  // to a single-week row (the current week), with an override toggle for
  // users who want the full month anyway.
  const [viewMode, setViewMode] = useState<"month" | "week">("month")
  const [userOverrodeView, setUserOverrodeView] = useState(false)
  useEffect(() => {
    if (typeof window === "undefined") return
    const mq = window.matchMedia("(max-width: 640px)")
    const apply = () => {
      if (userOverrodeView) return
      setViewMode(mq.matches ? "week" : "month")
    }
    apply()
    mq.addEventListener("change", apply)
    return () => mq.removeEventListener("change", apply)
  }, [userOverrodeView])

  const monthStart = useMemo(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth() + monthOffset, 1)
  }, [monthOffset])

  const monthEnd = useMemo(() => {
    return new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 1)
  }, [monthStart])

  const monthLabel = monthStart.toLocaleDateString("en-US", { month: "long", year: "numeric" }).toUpperCase()

  // Shoots active in this month AND matching the current studio filter. The
  // calendar and the roster below both read from this — a single filter
  // controls the whole page.
  const monthShoots = useMemo(() => {
    return initialShoots.filter(s => {
      const t = Date.parse(s.shoot_date || "")
      if (!Number.isFinite(t)) return false
      return t >= monthStart.getTime() && t < monthEnd.getTime()
    })
  }, [initialShoots, monthStart, monthEnd])

  const calendarShoots = useMemo(() => {
    if (studioFilter === "All") return monthShoots
    return monthShoots.filter(s => s.scenes.some(sc => sc.studio === studioFilter))
  }, [monthShoots, studioFilter])

  const counts = useMemo(() => {
    const c: Record<string, number> = { All: monthShoots.length }
    for (const st of STUDIOS) {
      c[st] = monthShoots.filter(s => s.scenes.some(sc => sc.studio === st)).length
    }
    return c
  }, [monthShoots])

  const statusCounts = useMemo(() => {
    let inProgress = 0, overdue = 0, wrapped = 0
    for (const s of calendarShoots) {
      const r = rollupShoot(s)
      if (r.progress === 100) wrapped += 1
      else if (r.isOverdue) overdue += 1
      else inProgress += 1
    }
    return { inProgress, overdue, wrapped }
  }, [calendarShoots])

  return (
    <div>
      <PageHeader
        title="Shoot Tracker"
        eyebrow={`SCHEDULE · ${monthLabel} · ${calendarShoots.length} SHOOTS`}
        subtitle={`${statusCounts.inProgress} in progress · ${statusCounts.overdue} overdue · ${statusCounts.wrapped} wrapped`}
        studioAccent={studioFilter !== "All" ? studioFilter : undefined}
        actions={
          <div
            className="flex items-center gap-1 rounded-md"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", padding: "3px" }}
          >
            {(["All", ...STUDIOS] as const).map(st => {
              const active = studioFilter === st
              const color = st === "All" ? "var(--color-lime)" : studioColor(st)
              return (
                <button
                  key={st}
                  type="button"
                  onClick={() => setStudioFilter(st)}
                  aria-pressed={active}
                  className="rounded px-2 py-1 transition-colors"
                  style={{
                    fontSize: 11,
                    fontWeight: active ? 600 : 400,
                    background: active ? "var(--color-elevated)" : "transparent",
                    color: active ? color : "var(--color-text-muted)",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  {st} <span className="tabular-nums" style={{ opacity: 0.7 }}>{counts[st] ?? 0}</span>
                </button>
              )
            })}
          </div>
        }
      />

      <section className="ec-block" style={{ marginBottom: 20 }}>
        <header>
          <h2>
            <span className="num">{monthStart.toLocaleDateString("en-US", { month: "short" }).toUpperCase()}</span>
            {monthLabel}
          </h2>
          <div className="act" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              type="button"
              onClick={() => { setUserOverrodeView(true); setViewMode(v => v === "month" ? "week" : "month") }}
              style={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                background: "transparent",
                color: "var(--color-text-muted)",
                border: "1px solid var(--color-border)",
                padding: "3px 8px",
                cursor: "pointer",
              }}
              aria-pressed={viewMode === "week"}
            >
              {viewMode === "month" ? "Week" : "Month"}
            </button>
            <a onClick={() => setMonthOffset(m => m - 1)} style={{ cursor: "pointer" }}>‹ Prev</a>
            {monthOffset !== 0 && (
              <a onClick={() => setMonthOffset(0)} style={{ cursor: "pointer" }}>Today</a>
            )}
            <a onClick={() => setMonthOffset(m => m + 1)} style={{ cursor: "pointer" }}>Next ›</a>
          </div>
        </header>
        <div style={{ padding: 0 }}>
          <MonthCalendar
            shoots={calendarShoots}
            monthStart={monthStart}
            onSelect={setSelected}
            viewMode={viewMode}
            events={events}
            onAddEvent={(date) => setAddEventDate(date)}
            onRemoveEvent={async (id) => {
              // Optimistic: drop from UI immediately so the popover row
              // disappears on click. Reconcile from server on completion.
              setEvents(prev => prev.filter(e => e.id !== id))
              try { await client.calendarEvents.remove(id) } catch {}
              refreshEvents()
            }}
          />
          {calendarShoots.length === 0 && (
            <div
              style={{
                padding: "16px",
                textAlign: "center",
                color: "var(--color-text-faint)",
                fontSize: 11,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                borderTop: "1px solid var(--color-border-subtle)",
              }}
            >
              {studioFilter === "All"
                ? "No shoots scheduled this month"
                : `No ${studioFilter} shoots this month`}
            </div>
          )}
          {eventsError && (
            <div
              role="status"
              style={{
                padding: "8px 12px",
                fontSize: 11,
                color: "var(--color-text-muted)",
                borderTop: "1px solid var(--color-border-subtle)",
                background: "color-mix(in srgb, var(--color-red, #ef4444) 6%, transparent)",
              }}
            >
              Calendar events unavailable: {eventsError}
            </div>
          )}
        </div>
      </section>

      {/* Roster below — receives the same filter so picks stay in sync. */}
      <div className="ec-embed-board">
        <ShootBoard
          initialShoots={initialShoots}
          error={boardError}
          idToken={idToken}
          variant="v2"
          studioFilter={studioFilter}
          hideHeader
        />
      </div>

      {selected && <ShootModal shoot={selected} onClose={() => setSelected(null)} />}
      {addEventDate && (
        <AddEventModal
          date={addEventDate}
          onSave={async (ev) => {
            try {
              const row = await client.calendarEvents.create({
                date: ev.date,
                title: ev.title,
                kind: ev.kind,
                color: ev.color,
                notes: ev.notes,
              })
              setEvents(prev => [...prev, rowToEvent(row)])
            } catch (err) {
              setEventsError(err instanceof Error ? err.message : "Failed to save event")
            }
          }}
          onClose={() => setAddEventDate(null)}
        />
      )}
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
