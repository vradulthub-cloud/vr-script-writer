"use client"

import type { SceneStats } from "@/lib/api"
import { PageHeader } from "@/components/ui/page-header"
import { studioAbbr, studioColor } from "@/lib/studio-colors"

const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"] as const

/** Prototype-style overview for Missing Assets. Shows a stat cluster + studio
 *  strip; the legacy SceneGrid (filters, cards, view-transitions) renders
 *  inline below. Only rendered when Eclatech V2 flag is on. */
export function MissingV2View({ stats }: { stats: SceneStats }) {
  const totalMissing = stats.missing_any
  const complete = stats.complete
  const total = stats.total
  const completePct = total > 0 ? Math.round((complete / total) * 100) : 0

  return (
    <div>
      <PageHeader
        title="Studio Catalog"
        eyebrow={`MISSING ASSETS · ${totalMissing} OF ${total.toLocaleString()} SCENES`}
        subtitle={`${complete.toLocaleString()} complete · ${totalMissing.toLocaleString()} missing at least one asset · ${completePct}% complete`}
      />

      {/* KPI stat cluster */}
      <div className="ec-stats">
        <div className="s">
          <div className="k">TOTAL SCENES</div>
          <div className="v">{total.toLocaleString()}</div>
        </div>
        <div className="s">
          <div className="k">COMPLETE</div>
          <div className="v">{complete.toLocaleString()}</div>
          <div className="d">{completePct}% of catalog</div>
        </div>
        <div className="s">
          <div className="k">MISSING</div>
          <div className="v" style={{ color: "var(--color-warn)" }}>{totalMissing.toLocaleString()}</div>
          <div className="d">need at least one asset</div>
        </div>
        <div className="s">
          <div className="k">STUDIOS</div>
          <div className="v">{STUDIOS.length}</div>
          <div className="d">FPVR · VRH · VRA · NJOI</div>
        </div>
      </div>

      {/* Per-studio strip */}
      <section className="ec-block" style={{ marginBottom: 20 }}>
        <header>
          <h2>Production · by studio</h2>
          <div className="act"><span>{total.toLocaleString()} scenes total</span></div>
        </header>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${STUDIOS.length}, 1fr)`, padding: 0 }}>
          {STUDIOS.map((s, i) => {
            const count = stats.by_studio[s] ?? 0
            const abbr = studioAbbr(s)
            const color = studioColor(s)
            const isLast = i === STUDIOS.length - 1
            return (
              <div
                key={s}
                style={{
                  padding: "16px 18px",
                  borderRight: isLast ? undefined : "1px solid var(--color-border-subtle)",
                  borderLeft: `2px solid ${color}`,
                }}
              >
                <div style={{ fontSize: 10, letterSpacing: "0.18em", fontWeight: 700, color }}>{abbr}</div>
                <div style={{
                  fontSize: 28, fontWeight: 800, lineHeight: 1, marginTop: 4,
                  fontFamily: "var(--font-display-hero, var(--font-sans))",
                  letterSpacing: "-0.03em", color: "var(--color-text)",
                  fontVariantNumeric: "tabular-nums",
                }}>
                  {count.toLocaleString()}
                  <sup style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--color-text-muted)", marginLeft: 4, fontWeight: 700 }}>SCN</sup>
                </div>
              </div>
            )
          })}
        </div>
      </section>
    </div>
  )
}
