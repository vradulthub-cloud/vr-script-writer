"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { X } from "lucide-react"
import type { Shoot } from "@/lib/api"
import { studioAbbr, studioColor } from "@/lib/studio-colors"

/** Week-view timeline using the v2 `.ec-cal` primitive.
 *  Shows 4 studio lanes with a bar per shoot positioned across the 7-day week.
 *  Clicking an event opens a modal with the shoot's details. */
export function WeekCalendar({
  shoots,
  weekStart,
  showHeader = true,
}: {
  shoots: Shoot[]
  weekStart?: Date
  showHeader?: boolean
}) {
  const [selected, setSelected] = useState<Shoot | null>(null)

  const start = weekStart ?? startOfWeek(new Date())
  const end = new Date(start)
  end.setDate(end.getDate() + 7)

  const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"] as const
  const lanes = STUDIOS.map(studio => {
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
  }).filter(l => l.events.length > 0)

  if (lanes.length === 0) return null

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

/* ─── Modal ────────────────────────────────────────────────────────────── */

function ShootModal({ shoot, onClose }: { shoot: Shoot; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  const primaryStudio = shoot.scenes[0]?.studio ?? ""
  const accent = primaryStudio ? studioColor(primaryStudio) : "var(--color-text-muted)"
  const abbr = primaryStudio ? studioAbbr(primaryStudio) : "—"
  const dateDisplay = formatFullDate(shoot.shoot_date)

  // Aggregate asset progress across all scenes in the shoot.
  let validated = 0
  let total = 0
  for (const sc of shoot.scenes) {
    for (const a of sc.assets) {
      total += 1
      if (a.status === "validated") validated += 1
    }
  }
  const pct = total > 0 ? Math.round((validated / total) * 100) : 0
  const days = Math.floor(shoot.aging_hours / 24)

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="shoot-modal-title"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "rgba(0, 0, 0, 0.72)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        animation: "fadeIn var(--duration-base) var(--ease-out-expo) both",
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: "min(640px, 100%)",
          maxHeight: "80vh",
          overflow: "auto",
          background: "var(--color-surface)",
          border: `1px solid var(--color-border)`,
          borderLeft: `3px solid ${accent}`,
          boxShadow: "0 24px 60px rgba(0,0,0,0.5)",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 16,
            padding: "20px 24px 16px",
            borderBottom: "1px solid var(--color-border)",
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: accent,
                marginBottom: 6,
              }}
            >
              {abbr} · {dateDisplay}
            </div>
            <h2
              id="shoot-modal-title"
              style={{
                fontFamily: "var(--font-display-hero)",
                fontWeight: 800,
                fontSize: 28,
                lineHeight: 1.05,
                letterSpacing: "-0.02em",
                color: "var(--color-text)",
                margin: 0,
              }}
            >
              {shoot.female_talent || shoot.shoot_id}
              {shoot.male_talent && (
                <span style={{ color: "var(--color-text-muted)", fontWeight: 500 }}> / {shoot.male_talent}</span>
              )}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              padding: 6,
              background: "transparent",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-muted)",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "18px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
          {/* Key facts row */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
            <ModalStat label="Progress" value={`${pct}%`} sub={`${validated}/${total} assets`} />
            <ModalStat label="Aging" value={days > 0 ? `${days}d` : "—"} sub={shoot.aging_hours > 0 ? `${shoot.aging_hours}h total` : "fresh"} />
            <ModalStat label="Scenes" value={String(shoot.scenes.length)} sub={shoot.source_tab || "—"} />
          </div>

          {/* Talent + agencies */}
          {(shoot.female_agency || shoot.male_agency) && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <SectionLabel>Talent</SectionLabel>
              <div style={{ display: "grid", gap: 6, fontSize: 12 }}>
                {shoot.female_talent && (
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
                    <span style={{ color: "var(--color-text)" }}>{shoot.female_talent}</span>
                    <span style={{ color: "var(--color-text-muted)" }}>{shoot.female_agency || "—"}</span>
                  </div>
                )}
                {shoot.male_talent && (
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
                    <span style={{ color: "var(--color-text)" }}>{shoot.male_talent}</span>
                    <span style={{ color: "var(--color-text-muted)" }}>{shoot.male_agency || "—"}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Location */}
          {(shoot.destination || shoot.location || shoot.home_owner) && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <SectionLabel>Location</SectionLabel>
              <div style={{ fontSize: 12, color: "var(--color-text)", lineHeight: 1.6 }}>
                {shoot.destination && <div>{shoot.destination}</div>}
                {shoot.location && <div style={{ color: "var(--color-text-muted)" }}>{shoot.location}</div>}
                {shoot.home_owner && (
                  <div style={{ color: "var(--color-text-faint)", marginTop: 4 }}>
                    Host: {shoot.home_owner}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Scenes */}
          {shoot.scenes.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <SectionLabel>Scenes</SectionLabel>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {shoot.scenes.map((sc, idx) => {
                  let sceneVal = 0
                  let sceneTot = 0
                  for (const a of sc.assets) { sceneTot += 1; if (a.status === "validated") sceneVal += 1 }
                  const scenePct = sceneTot ? Math.round((sceneVal / sceneTot) * 100) : 0
                  return (
                    <div
                      key={`${sc.scene_id || "scene"}-${idx}`}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "auto 1fr auto",
                        gap: 10,
                        alignItems: "center",
                        padding: "8px 10px",
                        background: "var(--color-elevated)",
                        border: "1px solid var(--color-border)",
                      }}
                    >
                      <span
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 10,
                          letterSpacing: "0.08em",
                          color: studioColor(sc.studio),
                          fontWeight: 700,
                        }}
                      >
                        {sc.scene_id || sc.scene_type || `#${idx + 1}`}
                      </span>
                      <span style={{ fontSize: 12, color: "var(--color-text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {sc.title || sc.scene_type}
                      </span>
                      <span style={{ fontSize: 10, color: "var(--color-text-muted)", fontVariantNumeric: "tabular-nums" }}>
                        {sceneVal}/{sceneTot} · {scenePct}%
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: "transparent",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              cursor: "pointer",
            }}
          >
            Close
          </button>
          <Link
            href="/shoots"
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: "var(--color-lime)",
              color: "#0d0d0d",
              textDecoration: "none",
              border: "1px solid var(--color-lime)",
            }}
          >
            Open in Shoots →
          </Link>
        </div>
      </div>
    </div>
  )
}

function ModalStat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--color-text-faint)" }}>
        {label}
      </div>
      <div
        style={{
          marginTop: 4,
          fontFamily: "var(--font-display-hero)",
          fontWeight: 800,
          fontSize: 22,
          letterSpacing: "-0.02em",
          color: "var(--color-text)",
        }}
      >
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 2 }}>
          {sub}
        </div>
      )}
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: "var(--color-text-faint)",
      }}
    >
      {children}
    </div>
  )
}

function formatMonthDay(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

function formatFullDate(raw: string): string {
  const t = Date.parse(raw)
  if (!Number.isFinite(t)) return raw || "—"
  return new Date(t).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function startOfWeek(d: Date): Date {
  const out = new Date(d)
  out.setHours(0, 0, 0, 0)
  out.setDate(out.getDate() - out.getDay())
  return out
}
