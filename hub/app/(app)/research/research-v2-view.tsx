"use client"

import { useMemo } from "react"
import type { Model } from "@/lib/api"
import { PageHeader } from "@/components/ui/page-header"

/** Prototype-style overview for Model Research: owns the hero title, then
 *  renders a stat cluster of roster health (rank breakdown + opportunity
 *  score). ModelSearch below keeps its search input but its duplicate
 *  title block is hidden via CSS. */
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
      <PageHeader
        title="Model Research"
        eyebrow="MODEL RESEARCH"
        subtitle={
          <span style={{ display: "flex", flexWrap: "wrap", gap: "0 16px" }}>
            <span><strong style={{ color: "var(--color-text)", fontWeight: 600 }}>{rollup.total.toLocaleString()}</strong> tracked</span>
            <span><strong style={{ color: "var(--color-ok)", fontWeight: 600 }}>{rollup.great}</strong> great</span>
            <span><strong style={{ color: "var(--color-lime)", fontWeight: 600 }}>{rollup.good}</strong> good</span>
            <span><strong style={{ color: "var(--color-warn)", fontWeight: 600 }}>{rollup.moderate}</strong> moderate</span>
            <span><strong style={{ color: "var(--color-text-muted)", fontWeight: 600 }}>{rollup.poor}</strong> poor</span>
            <span><strong style={{ color: "var(--color-text)", fontWeight: 600 }}>{rollup.available}</strong> available</span>
            <span>avg score <strong style={{ color: "var(--color-text)", fontWeight: 600 }}>{rollup.avgScore}</strong></span>
          </span>
        }
      />
    </div>
  )
}
