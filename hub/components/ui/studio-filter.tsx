"use client"

import { STUDIO_ABBR, studioColor } from "@/lib/studio-colors"

const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"] as const

interface StudioFilterProps {
  /** Selected studio name (full key like "FuckPassVR") or null/empty for All. */
  value: string | null
  onChange: (next: string | null) => void
  /** Optional per-studio counts for the chip badges. Missing keys render as 0. */
  counts?: Partial<Record<string, number>>
  /** Hide chips for studios with zero items, except for the active one. */
  hideEmpty?: boolean
  /** Optional label rendered to the left of the chip row. */
  label?: string
}

/**
 * Compact horizontal chip row for filtering by studio.
 *
 * Studio identity colors are first-class in the design system — the chip
 * adopts the studio's color when active so a power user can spot at a
 * glance which studio they're scoped to. Non-active chips stay neutral
 * outline so the row reads as "filter affordances" rather than "studio
 * tags scattered across the screen".
 */
export function StudioFilter({
  value,
  onChange,
  counts,
  hideEmpty = false,
  label,
}: StudioFilterProps) {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      {label && (
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-faint)" }}>
          {label}
        </span>
      )}
      <div
        role="group"
        aria-label="Studio filter"
        style={{
          display: "inline-flex",
          gap: 1,
          padding: 3,
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 6,
        }}
      >
        <Chip
          label="All"
          color="var(--color-text-muted)"
          active={!value}
          onClick={() => onChange(null)}
        />
        {STUDIOS.map(s => {
          const count = counts?.[s] ?? 0
          if (hideEmpty && count === 0 && value !== s) return null
          return (
            <Chip
              key={s}
              label={STUDIO_ABBR[s] ?? s}
              color={studioColor(s)}
              active={value === s}
              count={counts ? count : undefined}
              onClick={() => onChange(value === s ? null : s)}
            />
          )
        })}
      </div>
    </div>
  )
}

function Chip({
  label,
  color,
  active,
  count,
  onClick,
}: {
  label: string
  color: string
  active: boolean
  count?: number
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 10px",
        fontSize: 11,
        fontWeight: active ? 700 : 500,
        letterSpacing: "0.06em",
        borderRadius: 4,
        background: active
          ? `color-mix(in srgb, ${color} 18%, transparent)`
          : "transparent",
        color: active ? color : "var(--color-text-muted)",
        border: active
          ? `1px solid color-mix(in srgb, ${color} 35%, transparent)`
          : "1px solid transparent",
        cursor: "pointer",
        fontFamily: "inherit",
        textTransform: "uppercase",
        transition: "background 120ms ease, color 120ms ease",
      }}
    >
      {label}
      {count !== undefined && count > 0 && (
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            padding: "0 4px",
            borderRadius: 8,
            background: active
              ? `color-mix(in srgb, ${color} 22%, transparent)`
              : "var(--color-elevated)",
            color: active ? color : "var(--color-text-faint)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {count}
        </span>
      )}
    </button>
  )
}
