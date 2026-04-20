"use client"

import { useMemo } from "react"
import type { Model } from "@/lib/api"
import { PageHeader } from "@/components/ui/page-header"

/** Prototype-style overview for Model Research. Shows a roster summary
 *  (rank/rate/last-booked KPIs) above the existing ModelSearch surface.
 *  Only rendered when Eclatech V2 flag is on. */
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
    <div>
      <PageHeader
        title="Model Research"
        eyebrow={`ROSTER · ${rollup.total.toLocaleString()} MODELS · AVG SCORE ${rollup.avgScore}`}
        subtitle={`${rollup.great} great · ${rollup.good} good · ${rollup.moderate} moderate · ${rollup.poor} poor · ${rollup.available} listed as available`}
      />

      {/* KPI stat cluster */}
      <div className="ec-stat-cluster" style={{ marginBottom: 14 }}>
        <div className="ec-stat">
          <div className="l">ROSTER</div>
          <div className="v">{rollup.total.toLocaleString()}</div>
          <div className="s">tracked models</div>
        </div>
        <div className="ec-stat">
          <div className="l">GREAT</div>
          <div className="v" data-ok>{rollup.great.toLocaleString()}</div>
          <div className="s">top-rank models</div>
        </div>
        <div className="ec-stat">
          <div className="l">AVAILABLE</div>
          <div className="v">{rollup.available.toLocaleString()}</div>
          <div className="s">per agency notes</div>
        </div>
        <div className="ec-stat">
          <div className="l">AVG SCORE</div>
          <div className="v">{rollup.avgScore}</div>
          <div className="s">opportunity index</div>
        </div>
      </div>
    </div>
  )
}
