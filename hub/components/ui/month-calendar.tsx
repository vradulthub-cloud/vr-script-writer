"use client"

import { useState, useMemo, useEffect } from "react"
import { createPortal } from "react-dom"
import type { Shoot } from "@/lib/api"
import { studioAbbr, studioColor } from "@/lib/studio-colors"
import { holidayMap } from "@/lib/usa-holidays"
import { type CalendarEvent } from "@/lib/calendar-events"

/** Month grid: 7 columns × 5-6 rows of day cells. Each cell lists every
 *  shoot on that day as a studio-coloured pill. Click a pill to open the
 *  shoot modal.
 *  When `viewMode="week"` we collapse to just the row containing the current
 *  day — the month grid reads terribly on small viewports and the current
 *  week is the practical unit on set.
 */
export function MonthCalendar({
  shoots,
  monthStart,
  onSelect,
  viewMode = "month",
  events = [],
  onAddEvent,
  onRemoveEvent,
}: {
  shoots: Shoot[]
  monthStart: Date
  onSelect: (shoot: Shoot) => void
  viewMode?: "month" | "week"
  events?: CalendarEvent[]
  onAddEvent?: (date: string) => void
  onRemoveEvent?: (id: string) => void
}) {
  const [hoverDate, setHoverDate] = useState<string | null>(null)
  const [overflowDate, setOverflowDate] = useState<string | null>(null)

  const gridStart = useMemo(() => {
    const d = new Date(monthStart)
    d.setDate(1)
    d.setHours(0, 0, 0, 0)
    d.setDate(d.getDate() - d.getDay())
    return d
  }, [monthStart])

  const weeks = useMemo(() => {
    const monthEnd = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0)
    const totalDays = Math.ceil((monthEnd.getTime() - gridStart.getTime()) / 86400000) + 1
    const rowCount = Math.ceil(totalDays / 7)
    const rows: Date[][] = []
    for (let r = 0; r < rowCount; r++) {
      const row: Date[] = []
      for (let c = 0; c < 7; c++) {
        const d = new Date(gridStart)
        d.setDate(d.getDate() + r * 7 + c)
        row.push(d)
      }
      rows.push(row)
    }
    // Week mode: return only the row containing today (or the first row if
    // today falls outside the month being shown — happens when the user
    // navigates Prev/Next).
    if (viewMode === "week") {
      const todayMs = new Date().setHours(0, 0, 0, 0)
      const currentRow = rows.find(row =>
        row.some(d => {
          const dt = new Date(d).setHours(0, 0, 0, 0)
          return dt === todayMs
        }),
      )
      return currentRow ? [currentRow] : [rows[0]]
    }
    return rows
  }, [gridStart, monthStart, viewMode])

  const shootsByDate = useMemo(() => {
    const map: Record<string, Shoot[]> = {}
    for (const s of shoots) {
      const key = (s.shoot_date || "").slice(0, 10)
      if (!key) continue
      ;(map[key] ??= []).push(s)
    }
    return map
  }, [shoots])

  const eventsByDate = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {}
    for (const e of events) (map[e.date] ??= []).push(e)
    return map
  }, [events])

  const holidays = useMemo(() => holidayMap(monthStart.getFullYear()), [monthStart])

  const todayKey = new Date().toISOString().slice(0, 10)
  const monthIdx = monthStart.getMonth()

  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  const overflowShoots = overflowDate ? shootsByDate[overflowDate] ?? [] : []
  const overflowEvents = overflowDate ? eventsByDate[overflowDate] ?? [] : []
  const overflowHoliday = overflowDate ? holidays.get(overflowDate) : undefined
  const overflowCountTotal = overflowShoots.length + overflowEvents.length
  const overflowLabel = overflowDate
    ? new Date(overflowDate + "T00:00:00").toLocaleDateString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
      })
    : ""

  return (
    <>
    <div
      style={{
        border: "1px solid var(--color-border)",
        background: "var(--color-surface)",
        overflow: "hidden",
      }}
    >
      {/* Weekday header */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, 1fr)",
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-elevated)",
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: "var(--color-text-muted)",
        }}
      >
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d, i) => (
          <div
            key={d}
            style={{
              padding: "8px 10px",
              borderRight: i === 6 ? undefined : "1px solid var(--color-border-subtle)",
            }}
          >
            {d}
          </div>
        ))}
      </div>

      {/* Day grid */}
      {weeks.map((row, r) => (
        <div
          key={r}
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(7, 1fr)",
            borderBottom: r === weeks.length - 1 ? undefined : "1px solid var(--color-border-subtle)",
          }}
        >
          {row.map((d, c) => {
            const key = d.toISOString().slice(0, 10)
            const cellShoots = shootsByDate[key] ?? []
            const cellEvents = eventsByDate[key] ?? []
            const holiday = holidays.get(key)
            const totalChips = cellShoots.length + cellEvents.length
            const visibleShoots = cellShoots.slice(0, Math.min(2, cellShoots.length))
            const remainingSlots = Math.max(0, 2 - visibleShoots.length)
            const visibleEvents = cellEvents.slice(0, remainingSlots)
            const overflowCount = totalChips - visibleShoots.length - visibleEvents.length
            const inMonth = d.getMonth() === monthIdx
            const isToday = key === todayKey
            return (
              <div
                key={c}
                onMouseEnter={() => setHoverDate(key)}
                onMouseLeave={() => setHoverDate(prev => (prev === key ? null : prev))}
                style={{
                  // Hard height — rows must stay uniform regardless of how
                  // many shoots land in a given day, otherwise long talent
                  // names stretch every cell in the row. Max 2 chips fit,
                  // anything above shows the "+N more" roll-up.
                  height: 104,
                  padding: "6px 6px 8px",
                  borderRight: c === 6 ? undefined : "1px solid var(--color-border-subtle)",
                  background: hoverDate === key && inMonth
                    ? "color-mix(in srgb, var(--color-lime) 3%, transparent)"
                    : "transparent",
                  opacity: inMonth ? 1 : 0.35,
                  display: "flex",
                  flexDirection: "column",
                  gap: 3,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: 2,
                  }}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-display-hero)",
                      fontWeight: 700,
                      fontSize: 14,
                      color: isToday ? "var(--color-lime)" : "var(--color-text)",
                      letterSpacing: "-0.02em",
                    }}
                  >
                    {d.getDate()}
                  </span>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    {holiday && (
                      <span
                        title={holiday.name}
                        style={{
                          fontSize: 8,
                          fontWeight: 800,
                          letterSpacing: "0.08em",
                          color: "var(--color-text-faint)",
                          padding: "1px 4px",
                          border: "1px solid var(--color-border)",
                          textTransform: "uppercase",
                        }}
                      >
                        {holiday.short}
                      </span>
                    )}
                    {onAddEvent && inMonth && (hoverDate === key) && (
                      <button
                        type="button"
                        onClick={() => onAddEvent(key)}
                        title="Add event"
                        aria-label={`Add event on ${key}`}
                        style={{
                          background: "transparent",
                          border: "1px solid var(--color-border)",
                          color: "var(--color-text-muted)",
                          fontSize: 10,
                          lineHeight: 1,
                          padding: "1px 5px",
                          cursor: "pointer",
                        }}
                      >
                        +
                      </button>
                    )}
                    {cellShoots.length > 0 && !holiday && (
                      <span
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          letterSpacing: "0.08em",
                          color: "var(--color-text-faint)",
                        }}
                      >
                        {cellShoots.length}
                      </span>
                    )}
                  </div>
                </div>
                {visibleShoots.map(s => {
                  const studio = s.scenes[0]?.studio ?? ""
                  const color = studioColor(studio)
                  const abbr = studioAbbr(studio) || "—"
                  const talent = [s.female_talent, s.male_talent].filter(Boolean).join(" / ") || s.shoot_id
                  return (
                    <button
                      key={s.shoot_id}
                      type="button"
                      onClick={() => onSelect(s)}
                      title={`${abbr} · ${talent}`}
                      style={{
                        textAlign: "left",
                        padding: "2px 6px",
                        background: `color-mix(in srgb, ${color} 34%, transparent)`,
                        color: "var(--color-text)",
                        fontSize: 10,
                        fontWeight: 600,
                        lineHeight: 1.2,
                        cursor: "pointer",
                        display: "grid",
                        gridTemplateColumns: "auto minmax(0, 1fr)",
                        alignItems: "center",
                        gap: 4,
                        border: 0,
                        height: 20,
                        flexShrink: 0,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 8,
                          fontWeight: 800,
                          letterSpacing: "0.06em",
                          color,
                          flexShrink: 0,
                        }}
                      >
                        {abbr}
                      </span>
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 }}>
                        {talent}
                      </span>
                    </button>
                  )
                })}
                {visibleEvents.map(ev => (
                  <button
                    key={ev.id}
                    type="button"
                    onClick={() => setOverflowDate(key)}
                    title={ev.notes ? `${ev.title} — ${ev.notes}` : ev.title}
                    style={{
                      textAlign: "left",
                      padding: "2px 6px",
                      background: "transparent",
                      border: "1px dashed var(--color-border)",
                      color: "var(--color-text-muted)",
                      fontSize: 10,
                      fontWeight: 500,
                      lineHeight: 1.2,
                      cursor: "pointer",
                      display: "grid",
                      gridTemplateColumns: "auto minmax(0, 1fr)",
                      alignItems: "center",
                      gap: 4,
                      height: 20,
                      flexShrink: 0,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 8,
                        fontWeight: 800,
                        letterSpacing: "0.06em",
                        color: "var(--color-text-faint)",
                        flexShrink: 0,
                      }}
                    >
                      {(ev.kind || "EVT").slice(0, 4).toUpperCase()}
                    </span>
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 }}>
                      {ev.title}
                    </span>
                  </button>
                ))}
                {overflowCount > 0 && (
                  <button
                    type="button"
                    onClick={() => setOverflowDate(key)}
                    style={{
                      background: "transparent",
                      border: 0,
                      textAlign: "left",
                      padding: "0 6px",
                      fontSize: 9,
                      color: "var(--color-text-faint)",
                      letterSpacing: "0.04em",
                      cursor: "pointer",
                    }}
                    title={`Show all ${totalChips} items on this day`}
                  >
                    +{overflowCount} more
                  </button>
                )}
              </div>
            )
          })}
        </div>
      ))}
    </div>
    {mounted && overflowDate && createPortal(
      <div
        role="dialog"
        aria-label={`Shoots on ${overflowLabel}`}
        onClick={() => setOverflowDate(null)}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.55)",
          zIndex: 1100,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 16,
        }}
      >
        <div
          onClick={e => e.stopPropagation()}
          style={{
            width: "min(380px, 100%)",
            maxHeight: "min(70vh, 100dvh - 60px)",
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <header
            style={{
              padding: "12px 14px",
              borderBottom: "1px solid var(--color-border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
            }}
          >
            <div>
              <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--color-text-muted)" }}>
                {overflowCountTotal} {overflowCountTotal === 1 ? "Item" : "Items"}
                {overflowHoliday && <span style={{ marginLeft: 8, color: "var(--color-lime)" }}>· {overflowHoliday.name.toUpperCase()}</span>}
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)" }}>
                {overflowLabel}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOverflowDate(null)}
              aria-label="Close"
              style={{
                background: "transparent",
                border: "1px solid var(--color-border)",
                color: "var(--color-text-muted)",
                fontSize: 14,
                lineHeight: 1,
                padding: "4px 8px",
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          </header>
          <div style={{ overflowY: "auto", flex: "1 1 auto", minHeight: 0 }}>
            {overflowShoots.map(s => {
              const studio = s.scenes[0]?.studio ?? ""
              const color = studioColor(studio)
              const abbr = studioAbbr(studio) || "—"
              const talent = [s.female_talent, s.male_talent].filter(Boolean).join(" / ") || s.shoot_id
              return (
                <button
                  key={s.shoot_id}
                  type="button"
                  onClick={() => { setOverflowDate(null); onSelect(s) }}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "auto 1fr",
                    alignItems: "center",
                    gap: 10,
                    width: "100%",
                    textAlign: "left",
                    padding: "10px 14px",
                    background: "transparent",
                    border: 0,
                    borderBottom: "1px solid var(--color-border-subtle)",
                    cursor: "pointer",
                    color: "var(--color-text)",
                  }}
                >
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: 800,
                      letterSpacing: "0.08em",
                      color,
                      padding: "3px 6px",
                      background: `color-mix(in srgb, ${color} 18%, transparent)`,
                    }}
                  >
                    {abbr}
                  </span>
                  <span style={{ fontSize: 13, fontWeight: 500 }}>{talent}</span>
                </button>
              )
            })}
            {overflowEvents.map(ev => (
              <div
                key={ev.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto 1fr auto",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 14px",
                  borderBottom: "1px solid var(--color-border-subtle)",
                }}
              >
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 800,
                    letterSpacing: "0.08em",
                    color: "var(--color-text-muted)",
                    padding: "3px 6px",
                    border: "1px dashed var(--color-border)",
                  }}
                >
                  {(ev.kind || "EVT").slice(0, 4).toUpperCase()}
                </span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "var(--color-text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {ev.title}
                  </div>
                  {ev.notes && (
                    <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2 }}>
                      {ev.notes}
                    </div>
                  )}
                </div>
                {onRemoveEvent && (
                  <button
                    type="button"
                    onClick={() => onRemoveEvent(ev.id)}
                    aria-label="Delete event"
                    style={{
                      background: "transparent",
                      border: "1px solid var(--color-border)",
                      color: "var(--color-text-muted)",
                      fontSize: 10,
                      lineHeight: 1,
                      padding: "4px 6px",
                      cursor: "pointer",
                    }}
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
            {onAddEvent && overflowDate && (
              <button
                type="button"
                onClick={() => { const d = overflowDate; setOverflowDate(null); onAddEvent(d) }}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: "10px 14px",
                  background: "transparent",
                  border: 0,
                  color: "var(--color-lime)",
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  cursor: "pointer",
                }}
              >
                + Add Event
              </button>
            )}
          </div>
        </div>
      </div>,
      document.body,
    )}
    </>
  )
}
