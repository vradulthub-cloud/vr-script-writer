"use client"

import { useState } from "react"
import type { Shoot } from "@/lib/api"
import { studioAbbr } from "@/lib/studio-colors"
import { ShootModal } from "@/components/ui/shoot-modal"

/** Week-view timeline using the v2 `.ec-cal` primitive.
 *  Shows 4 studio lanes with a bar per shoot positioned across the 7-day week.
 *  Clicking an event opens a modal with the shoot's details. */
export function WeekCalendar({
  shoots,
  weekStart,
  showHeader = true,
  studios = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"],
}: {
  shoots: Shoot[]
  weekStart?: Date
  showHeader?: boolean
  studios?: string[]
}) {
  const [selected, setSelected] = useState<Shoot | null>(null)

  const start = weekStart ?? startOfWeek(new Date())
  const end = new Date(start)
  end.setDate(end.getDate() + 7)

  const lanes = studios.map(studio => {
    const laneEvents = shoots
      .filter(s => {
        if (s.scenes.length === 0) return false
        if (s.scenes[0].studio !== studio) return false
        const t = Date.parse(s.shoot_date || "")
        return Number.isFinite(t) && t >= start.getTime() && t < end.getTime()
      })
      .map(s => {
        const t = Date.parse(s.shoot_date)
        const dayIdx = Math.floor((t - start.getTime()) / (24 * 60 * 60 * 1000))
        const left = (dayIdx / 7) * 100
        const right = ((dayIdx + 1) / 7) * 100
        const talent = [s.female_talent, s.male_talent].filter(Boolean).join(" / ")
        return { shoot: s, left, right, talent }
      })
    return { studio, abbr: studioAbbr(studio), events: laneEvents }
  })

  if (lanes.every(l => l.events.length === 0)) return null

  const weekLabel = `${formatMonthDay(start)} → ${formatMonthDay(new Date(end.getTime() - 1))}`

  return (
    <div>
      {showHeader && (
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            marginBottom: 8,
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--color-text-muted)",
          }}
        >
          <span>This Week on Set</span>
          <span style={{ fontSize: 10, color: "var(--color-text-faint)", letterSpacing: "0.14em" }}>
            {weekLabel}
          </span>
        </div>
      )}
      <section className="ec-cal">
        <div className="cal-head">
          <div>Studio</div>
          {Array.from({ length: 7 }).map((_, i) => {
            const d = new Date(start)
            d.setDate(d.getDate() + i)
            const wd = d.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase()
            return (
              <div key={i}>
                <span className="dnum">{d.getDate()}</span>
                {wd}
              </div>
            )
          })}
        </div>
        {lanes.map(lane => (
          <div key={lane.studio} className="lane">
            <div className="label">
              <div className="who">{lane.studio}</div>
              <div>{lane.abbr}</div>
            </div>
            <div className="track">
              {lane.events.map(e => {
                const cls = lane.abbr.toLowerCase()
                const sceneTitle = e.shoot.scenes[0]?.title || `${e.shoot.scenes.length} scene${e.shoot.scenes.length === 1 ? "" : "s"}`
                return (
                  <button
                    key={e.shoot.shoot_id}
                    type="button"
                    onClick={() => setSelected(e.shoot)}
                    className={`ev ${cls}`}
                    style={{
                      left: `${e.left}%`,
                      right: `${100 - e.right}%`,
                      cursor: "pointer",
                      textAlign: "left",
                      font: "inherit",
                    }}
                    title={`${lane.studio} · ${e.talent || ""}`}
                    aria-label={`Open details for ${sceneTitle}`}
                  >
                    <div className="t">{sceneTitle}</div>
                    <div className="m">{e.talent || e.shoot.shoot_id}</div>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </section>

      {selected && <ShootModal shoot={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

function formatMonthDay(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

function startOfWeek(d: Date): Date {
  const out = new Date(d)
  out.setHours(0, 0, 0, 0)
  out.setDate(out.getDate() - out.getDay())
  return out
}
