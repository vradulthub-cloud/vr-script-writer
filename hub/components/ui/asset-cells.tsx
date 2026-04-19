import type { CSSProperties } from "react"

export type AssetCellStatus = "ok" | "pending" | "missing" | "na"

export interface AssetCell {
  /** Short label — "Desc", "Vids", "Thumb", "Photos", "Story". 1–6 chars ideal. */
  label: string
  status: AssetCellStatus
  /** Optional tooltip content. */
  title?: string
}

/**
 * Inline row of coloured squares — each square is one asset's readiness.
 * Extends the PLAN/SHOOT/POST cell-grid vocabulary from Shoot Tracker into a
 * reusable primitive for cards, rows, and inline status strips.
 *
 * The label is always rendered as screen-reader-only + visible (uppercase
 * mono, tiny) so the grid communicates to both sight and assistive tech.
 * Pass `compact` for label-free dense rows.
 */
export function AssetCells({
  cells,
  size = "sm",
  compact = false,
  style,
}: {
  cells: AssetCell[]
  size?: "sm" | "md"
  compact?: boolean
  style?: CSSProperties
}) {
  const cellSize = size === "md" ? 14 : 10
  const gap = 2

  return (
    <div
      role="group"
      aria-label="Asset status"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: compact ? gap : 6,
        ...style,
      }}
    >
      {cells.map((c, i) => (
        <span
          key={`${c.label}-${i}`}
          title={c.title ?? `${c.label}: ${STATUS_DESC[c.status]}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 9,
            fontFamily: "var(--font-mono)",
            color: "var(--color-text-faint)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          <span
            aria-hidden="true"
            style={{
              width: cellSize,
              height: cellSize,
              borderRadius: 1.5,
              flexShrink: 0,
              ...STYLE_FOR[c.status],
            }}
          />
          {!compact && <span>{c.label}</span>}
        </span>
      ))}
    </div>
  )
}

const STATUS_DESC: Record<AssetCellStatus, string> = {
  ok: "ready",
  pending: "in progress",
  missing: "missing",
  na: "not applicable",
}

const STYLE_FOR: Record<AssetCellStatus, CSSProperties> = {
  ok: {
    background: "color-mix(in srgb, var(--color-ok) 65%, transparent)",
    border: "1px solid color-mix(in srgb, var(--color-ok) 55%, transparent)",
  },
  pending: {
    background: "color-mix(in srgb, var(--color-warn) 45%, transparent)",
    border: "1px solid color-mix(in srgb, var(--color-warn) 50%, transparent)",
  },
  missing: {
    background: "color-mix(in srgb, var(--color-err) 35%, transparent)",
    border: "1px solid color-mix(in srgb, var(--color-err) 55%, transparent)",
  },
  na: {
    background: "transparent",
    border: "1px solid var(--color-border)",
  },
}
