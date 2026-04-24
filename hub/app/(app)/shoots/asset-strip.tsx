"use client"

import { PHASES, PHASE_GAP, CELL_GAP, ASSET_SHORT, statusColor, statusIcon, cellApplies } from "./shoot-utils"
import { SHOOT_ASSET_LABELS, type BoardShootScene, type AssetStatus, type AssetType } from "@/lib/api"
import { studioColor } from "@/lib/studio-colors"

interface AssetStripProps {
  scene: BoardShootScene
  onCellClick: (assetType: AssetType) => void
  showLabels?: boolean
}

export function AssetStrip({ scene, onCellClick, showLabels = false }: AssetStripProps) {
  const assetsByType = new Map(scene.assets.map(a => [a.asset_type, a]))
  const accent = studioColor(scene.studio)

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div
        style={{
          fontSize: 9,
          fontWeight: 700,
          color: accent,
          letterSpacing: "0.05em",
          width: 64,
          flexShrink: 0,
          textTransform: "uppercase",
        }}
      >
        {scene.grail_tab || scene.studio.slice(0, 4).toUpperCase()} · {scene.scene_type}
      </div>
      <div style={{ display: "flex", alignItems: "center" }}>
        {PHASES.map((phase, pi) => (
          <div
            key={phase.name}
            style={{
              display: "flex",
              gap: CELL_GAP,
              marginRight: pi < PHASES.length - 1 ? PHASE_GAP : 0,
            }}
          >
            {phase.assets.map(at => {
              const a = assetsByType.get(at)
              const status: AssetStatus = a?.status ?? "not_present"
              const hasWarn = !!a && a.validity.some(v => v.status === "warn")
              const color = statusColor(status, hasWarn)
              const applies = cellApplies(at, scene.scene_type)
              const shortLabel = ASSET_SHORT[at]
              const wrapperStyle: React.CSSProperties = showLabels
                ? { display: "flex", flexDirection: "column", alignItems: "center", gap: 3, width: 28, flexShrink: 0 }
                : { display: "contents" }
              const cellNode = !applies ? (
                <span
                  aria-label={`${SHOOT_ASSET_LABELS[at]} (not applicable for ${scene.scene_type})`}
                  title={`${SHOOT_ASSET_LABELS[at]} — N/A for ${scene.scene_type}`}
                  style={{
                    width: 16,
                    height: 16,
                    borderRadius: 3,
                    border: "1px dashed var(--color-border)",
                    background: "transparent",
                    opacity: 0.3,
                    flexShrink: 0,
                  }}
                />
              ) : (
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(e) => { e.stopPropagation(); onCellClick(at) }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.stopPropagation()
                      onCellClick(at)
                    }
                  }}
                  title={`${phase.name} — ${SHOOT_ASSET_LABELS[at]}: ${status}${hasWarn ? " (warnings)" : ""}`}
                  style={{
                    width: 16,
                    height: 16,
                    borderRadius: 3,
                    border: `1px solid ${color}`,
                    background: status === "not_present" ? "transparent" : `color-mix(in srgb, ${color} 24%, transparent)`,
                    color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    flexShrink: 0,
                  }}
                >
                  {statusIcon(status, hasWarn)}
                </span>
              )
              if (!showLabels) return <span key={at} style={{ display: "contents" }}>{cellNode}</span>
              return (
                <div key={at} style={wrapperStyle}>
                  {cellNode}
                  <span
                    aria-hidden="true"
                    style={{
                      fontSize: 8,
                      lineHeight: 1,
                      letterSpacing: "0.06em",
                      fontWeight: 600,
                      color: applies ? "var(--color-text-muted)" : "var(--color-text-faint)",
                      textTransform: "uppercase",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {shortLabel}
                  </span>
                </div>
              )
            })}
          </div>
        ))}
      </div>
      {scene.scene_id ? (
        <span style={{ fontSize: 10, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)", marginLeft: "auto" }}>
          {scene.scene_id}
        </span>
      ) : (
        <span style={{ fontSize: 10, color: "var(--color-text-faint)", fontStyle: "italic", marginLeft: "auto" }}>
          pending Grail
        </span>
      )}
    </div>
  )
}
