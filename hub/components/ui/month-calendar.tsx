"use client"

import { useState, useMemo } from "react"
import type { Shoot } from "@/lib/api"
import { studioAbbr, studioColor } from "@/lib/studio-colors"

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
}: {
  shoots: Shoot[]
  monthStart: Date
  onSelect: (shoot: Shoot) => void
  viewMode?: "month" | "week"
}) {
  const [hoverDate, setHoverDate] = useState<string | null>(null)

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

  const todayKey = new Date().toISOString().slice(0, 10)
  const monthIdx = monthStart.getMonth()

  return (
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
                  {cellShoots.length > 0 && (
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
                {cellShoots.slice(0, 2).map(s => {
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
                {cellShoots.length > 2 && (
                  <button
                    type="button"
                    onClick={() => onSelect(cellShoots[2])}
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
                    title={`${cellShoots.length - 2} more shoot${cellShoots.length - 2 === 1 ? "" : "s"} on this day`}
                  >
                    +{cellShoots.length - 2} more
                  </button>
                )}
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}
