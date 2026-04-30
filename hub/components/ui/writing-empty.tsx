"use client"

/**
 * Empty-state card for the Writing Room output panels (Scripts and
 * Descriptions). v3 redesign — centered icon disc on a faint lime tint,
 * a serif italic primary line, and a small helper. Replaces the older
 * dashed-border generic empty box.
 *
 * Use inside the output column of either page when there's nothing
 * generated yet and nothing streaming.
 */
export function WritingEmptyState({
  icon,
  primary,
  helper,
  height = 320,
}: {
  icon: string
  primary: string
  helper?: string
  height?: number | string
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 12,
        height,
        textAlign: "center",
        padding: "24px",
        borderRadius: 8,
        border: "1px solid var(--color-paper-rule)",
        background: "var(--color-paper)",
      }}
    >
      <div
        style={{
          width: 72,
          height: 72,
          borderRadius: 18,
          background: "color-mix(in srgb, var(--color-lime) 8%, transparent)",
          border: "1px solid color-mix(in srgb, var(--color-lime) 18%, transparent)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 26,
          color: "color-mix(in srgb, var(--color-lime) 60%, transparent)",
        }}
      >
        {icon}
      </div>
      <div
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: 18,
          fontWeight: 500,
          fontStyle: "italic",
          color: "var(--color-paper-text)",
          maxWidth: 380,
          lineHeight: 1.5,
        }}
      >
        {primary}
      </div>
      {helper && (
        <div style={{ fontSize: 12, color: "var(--color-paper-sub)" }}>{helper}</div>
      )}
    </div>
  )
}
