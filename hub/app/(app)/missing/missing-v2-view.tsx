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
      <div className="ec-stat-cluster" style={{ marginBottom: 14 }}>
        <div className="ec-stat">
          <div className="l">TOTAL SCENES</div>
          <div className="v">{total.toLocaleString()}</div>
        </div>
        <div className="ec-stat">
          <div className="l">COMPLETE</div>
          <div className="v">{complete.toLocaleString()}</div>
          <div className="s">{completePct}% of catalog</div>
        </div>
        <div className="ec-stat">
          <div className="l">MISSING</div>
          <div className="v" data-warn>{totalMissing.toLocaleString()}</div>
          <div className="s">scenes need at least one asset</div>
        </div>
        <div className="ec-stat">
          <div className="l">STUDIOS</div>
          <div className="v">{STUDIOS.length}</div>
          <div className="s">FPVR · VRH · VRA · NJOI</div>
        </div>
      </div>

      {/* Per-studio strip */}
      <section className="ec-block" style={{ marginBottom: 20 }}>
        <header>
          <h2>Production · by studio</h2>
          <div className="act"><span>{total.toLocaleString()} scenes total</span></div>
        </header>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${STUDIOS.length}, 1fr)`, gap: 12, padding: "14px 16px" }}>
          {STUDIOS.map(s => {
            const count = stats.by_studio[s] ?? 0
            const abbr = studioAbbr(s)
            const color = studioColor(s)
            return (
              <div key={s} style={{ display: "flex", flexDirection: "column", gap: 6, borderLeft: `2px solid ${color}`, paddingLeft: 10 }}>
                <div style={{ fontSize: 10, letterSpacing: "0.18em", fontWeight: 700, color }}>{abbr}</div>
                <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "var(--font-display, inherit)", color: "var(--color-text)", lineHeight: 1 }}>
                  {count.toLocaleString()}
                  <sup style={{ fontSize: 9, letterSpacing: "0.15em", color: "var(--color-text-faint)", marginLeft: 4, fontWeight: 600 }}>SCN</sup>
                </div>
              </div>
            )
          })}
        </div>
      </section>
    </div>
  )
}
