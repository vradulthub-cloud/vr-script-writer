"use client"

import { useMemo } from "react"
import type { Model } from "@/lib/api"

/** Prototype-style overview for Model Research: stat cluster of roster
 *  health (rank breakdown + opportunity score). Renders above ModelSearch
 *  which keeps its own PageHeader + Trending / Priority Outreach lists. */
export function ResearchV2View({ models }: { models: Model[] }) {
  const rollup = useMemo(() => {
    let great = 0, good = 0, moderate = 0, poor = 0, avail = 0
    let scoreSum = 0, scored = 0
    for (const m of models) {
      const rank = (m.rank || "").toLowerCase()
      if (rank.includes("great")) great += 1
      else if (rank.includes("good")) good += 1
      else if (rank.includes("moderate")) moderate += 1
      else if (rank.includes("poor")) poor += 1
      if (m.notes && m.notes.trim()) avail += 1
      if (typeof m.opportunity_score === "number" && m.opportunity_score > 0) {
        scoreSum += m.opportunity_score
        scored += 1
      }
    }
    return {
      total: models.length,
      great, good, moderate, poor,
      available: avail,
      avgScore: scored > 0 ? Math.round(scoreSum / scored) : 0,
    }
  }, [models])

  return (
    <div style={{ marginBottom: 20 }}>
      {/* KPI stat cluster */}
      <div className="ec-stats">
        <div className="s">
          <div className="k">ROSTER</div>
          <div className="v">{rollup.total.toLocaleString()}</div>
          <div className="d">tracked models</div>
        </div>
        <div className="s">
          <div className="k">GREAT</div>
          <div className="v" style={{ color: "var(--color-ok)" }}>{rollup.great.toLocaleString()}</div>
          <div className="d">top-rank models</div>
        </div>
        <div className="s">
          <div className="k">AVAILABLE</div>
          <div className="v">{rollup.available.toLocaleString()}</div>
          <div className="d">per agency notes</div>
        </div>
        <div className="s">
          <div className="k">AVG SCORE</div>
          <div className="v">{rollup.avgScore}</div>
          <div className="d">opportunity index</div>
        </div>
      </div>
    </div>
  )
}
