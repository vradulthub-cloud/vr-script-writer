import type { ReactNode, CSSProperties } from "react"

type PanelTone = "default" | "muted" | "urgent"
type PanelVariant = "label" | "content"

/**
 * Shared panel primitive. Replaces the ~dozen inline-styled
 * `{ background, border, borderRadius }` blocks scattered across pages so
 * surface tone is controlled in one place.
 *
 * `tone="urgent"` uses a full (not side-stripe) red-tinted border — impeccable
 * banned border-left accents. The count badge in the header is the urgency
 * signal; the border is secondary.
 */
export function Panel({
  title,
  count,
  action,
  tone = "default",
  variant = "label",
  padded = false,
  style,
  className,
  children,
}: {
  title?: ReactNode
  count?: ReactNode
  action?: ReactNode
  tone?: PanelTone
  /**
   * Controls the title treatment:
   *   "label"   — default uppercase-tracked 13px chrome for grouped sections.
   *   "content" — 20px semibold sentence-case for panels that carry content
   *               weight (named regions, feature blocks). Uses --text-title.
   */
  variant?: PanelVariant
  /** Apply inner body padding. Leave off when children render their own rows (tables, lists). */
  padded?: boolean
  style?: CSSProperties
  className?: string
  children: ReactNode
}) {
  const border =
    tone === "urgent"
      ? "1px solid color-mix(in srgb, var(--color-err) 32%, transparent)"
      : "1px solid var(--color-border)"
  const bg =
    tone === "muted"
      ? "color-mix(in srgb, var(--color-surface) 60%, transparent)"
      : "var(--color-surface)"

  return (
    <section
      className={className}
      style={{
        background: bg,
        border,
        borderRadius: 6,
        overflow: "hidden",
        ...style,
      }}
    >
      {(title || action) && (
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            padding: "9px 14px",
            borderBottom: "1px solid var(--color-border)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
            {title && (
              // Semantic h2: Panel is always a first-class page region; it
              // sits under the page's single h1 in PageHeader. Two styles:
              // "label" (default) is the dense uppercase-tracked chrome used
              // for grouped sections; "content" is the 20px semibold title
              // used for content-bearing panels so the mid-step of the type
              // scale gets real hierarchy instead of compressing into 13px
              // label chrome.
              <h2
                style={
                  variant === "content"
                    ? {
                        margin: 0,
                        fontSize: "var(--text-title)",
                        fontWeight: 600,
                        letterSpacing: "-0.01em",
                        color: "var(--color-text)",
                        fontFamily: "var(--font-display)",
                        lineHeight: 1.2,
                      }
                    : {
                        margin: 0,
                        fontSize: "0.8125rem",
                        fontWeight: 600,
                        letterSpacing: "0.06em",
                        textTransform: "uppercase",
                        color: "var(--color-text-muted)",
                        fontFamily: "var(--font-display)",
                        lineHeight: 1.15,
                      }
                }
              >
                {title}
              </h2>
            )}
            {count !== undefined && count !== null && (
              <span
                aria-label={typeof count === "number" ? `${count} items` : undefined}
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: tone === "urgent" ? "var(--color-err)" : "var(--color-text-muted)",
                  border:
                    tone === "urgent"
                      ? "1px solid color-mix(in srgb, var(--color-err) 32%, transparent)"
                      : "1px solid var(--color-border)",
                  background:
                    tone === "urgent"
                      ? "color-mix(in srgb, var(--color-err) 10%, transparent)"
                      : "transparent",
                  borderRadius: 10,
                  padding: "0 7px",
                  lineHeight: 1.5,
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {count}
              </span>
            )}
          </div>
          {action && <div style={{ display: "flex", alignItems: "center", gap: 8 }}>{action}</div>}
        </header>
      )}

      <div style={padded ? { padding: 14 } : undefined}>{children}</div>
    </section>
  )
}
