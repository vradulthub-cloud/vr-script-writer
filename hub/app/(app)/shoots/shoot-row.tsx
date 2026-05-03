"use client"

import { isAlert, shootCompleteness, formatShootDate, relativeFromHours } from "./shoot-utils"
import { AssetStrip } from "./asset-strip"
import { studioColor } from "@/lib/studio-colors"
import type { Shoot, AssetType } from "@/lib/api"

// ── v1 row ────────────────────────────────────────────────────────────

interface ShootRowProps {
  shoot: Shoot
  selected: boolean
  onSelect: () => void
  onCellClick: (sceneIdx: number, assetType: AssetType) => void
}

export function ShootRow({ shoot, selected, onSelect, onCellClick }: ShootRowProps) {
  const primaryStudio = shoot.scenes[0]?.studio ?? "FuckPassVR"
  const accent = studioColor(primaryStudio)
  const alert = isAlert(shoot)
  const { validated, total } = shootCompleteness(shoot)

  return (
    <button
      type="button"
      onClick={onSelect}
      className="text-left rounded transition-colors w-full"
      style={{
        display: "grid",
        gridTemplateColumns: "3px 150px minmax(0, 1fr)",
        gap: 12,
        padding: "10px 12px",
        background: selected ? "var(--color-elevated)" : "var(--color-surface)",
        border: `1px solid ${selected ? accent : "var(--color-border)"}`,
        cursor: "pointer",
      }}
    >
      <span style={{ background: alert ? "var(--color-err)" : accent, borderRadius: 2 }} aria-hidden="true" />
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: alert ? "var(--color-err)" : "var(--color-text)",
            letterSpacing: "0.02em",
          }}
        >
          {formatShootDate(shoot.shoot_date)}
        </div>
        <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
          {shoot.female_talent}{shoot.male_talent ? ` / ${shoot.male_talent}` : ""}
        </div>
        <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 2 }}>
          {relativeFromHours(shoot.aging_hours)} · {validated}/{total}
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
        {shoot.scenes.map((scene, idx) => (
          <AssetStrip
            key={scene.position}
            scene={scene}
            onCellClick={(at) => onCellClick(idx, at)}
          />
        ))}
      </div>
    </button>
  )
}

// ── v2 row ────────────────────────────────────────────────────────────

interface ShootRowV2Props {
  shoot: Shoot
  expanded: boolean
  onToggle: () => void
  onOpenDetails: () => void
  onCellClick: (sceneIdx: number, assetType: AssetType) => void
}

export function ShootRowV2({ shoot, expanded, onToggle, onOpenDetails, onCellClick }: ShootRowV2Props) {
  const primaryStudio = shoot.scenes[0]?.studio ?? "FuckPassVR"
  const accent = studioColor(primaryStudio)
  const alert = isAlert(shoot)
  const { validated, total } = shootCompleteness(shoot)
  const progress = total > 0 ? Math.round((validated / total) * 100) : 0
  const abbr = (shoot.scenes[0]?.grail_tab || primaryStudio.slice(0, 4)).toUpperCase()
  const statusKey = progress === 100 ? "ok" : alert ? "err" : progress > 0 ? "progress" : "warn"
  const statusLabel = progress === 100 ? "WRAPPED" : alert ? "OVERDUE" : progress > 0 ? "ACTIVE" : "PREP"

  return (
    <div
      style={{
        border: `1px solid ${expanded ? "var(--color-border)" : alert ? "var(--color-err)" : "var(--color-border-subtle)"}`,
        background: expanded
          ? "var(--color-elevated)"
          : alert
            ? "color-mix(in srgb, var(--color-err) 6%, var(--color-surface))"
            : "var(--color-surface)",
        transition: "background 120ms ease",
      }}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        style={{
          width: "100%",
          display: "grid",
          gridTemplateColumns: "72px 140px minmax(0, 1fr) 160px 110px 80px 20px",
          columnGap: 14,
          alignItems: "center",
          padding: "12px 14px",
          background: "transparent",
          border: "none",
          textAlign: "left",
          cursor: "pointer",
          color: "inherit",
        }}
      >
        <span className={`ec-studio-chip ${abbr.toLowerCase()}`} style={{
          fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", color: accent,
        }}>
          {abbr}
        </span>

        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text)", fontVariantNumeric: "tabular-nums" }}>
          {formatShootDate(shoot.shoot_date)}
        </div>

        <div style={{ minWidth: 0 }}>
          <div style={{
            fontSize: 13, color: "var(--color-text)", overflow: "hidden",
            textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {shoot.female_talent || "—"}
            {shoot.male_talent && <span style={{ color: "var(--color-text-muted)" }}> / {shoot.male_talent}</span>}
          </div>
          <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 2 }}>
            {shoot.scenes.length} scene{shoot.scenes.length === 1 ? "" : "s"} · {relativeFromHours(shoot.aging_hours)}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            fontSize: 12, fontVariantNumeric: "tabular-nums",
            color: "var(--color-text)", minWidth: 48, textAlign: "right",
          }}>
            {validated}/{total}
          </span>
          <div style={{
            flex: 1, height: 4, borderRadius: 2,
            background: "var(--color-border-subtle)", overflow: "hidden",
          }}>
            <div style={{
              width: "100%",
              height: "100%",
              background: alert ? "var(--color-err)" : accent,
              transform: `scaleX(${progress / 100})`,
              transformOrigin: "left center",
              transition: "transform 180ms var(--ease-out-quart)",
            }} />
          </div>
          <span style={{
            fontSize: 11, fontVariantNumeric: "tabular-nums",
            color: "var(--color-text-muted)", minWidth: 34, textAlign: "right",
          }}>
            {progress}%
          </span>
        </div>

        <span className="ec-pill" data-s={statusKey} style={{ justifySelf: "start" }}>
          <span className="d" />
          {statusLabel}
        </span>

        {alert ? (
          <span className="ec-age" data-hot style={{ justifySelf: "start" }}>
            {Math.floor(shoot.aging_hours / 24)}d
          </span>
        ) : (
          <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
            {shoot.aging_hours > 0 ? `${Math.floor(shoot.aging_hours / 24)}d` : "fresh"}
          </span>
        )}

        <span aria-hidden="true" style={{
          fontSize: 10, color: "var(--color-text-muted)",
          transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
          transition: "transform 120ms ease",
          justifySelf: "center",
        }}>
          ▶
        </span>
      </button>

      {expanded && (
        <div style={{
          padding: "10px 14px 14px 14px",
          borderTop: "1px solid var(--color-border-subtle)",
          display: "flex", flexDirection: "column", gap: 8,
        }}>
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            fontSize: 9, letterSpacing: "0.14em", color: "var(--color-text-faint)",
            textTransform: "uppercase",
          }}>
            <span>Asset phases · click a cell to revalidate</span>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onOpenDetails() }}
              style={{
                background: "transparent", border: "none", cursor: "pointer",
                fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase",
                color: "var(--color-lime)", padding: 0,
              }}
            >
              Open details →
            </button>
          </div>
          {shoot.scenes.map((scene, idx) => (
            <AssetStrip
              key={scene.position}
              scene={scene}
              onCellClick={(at) => onCellClick(idx, at)}
              showLabels
            />
          ))}
        </div>
      )}
    </div>
  )
}
