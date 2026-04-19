import type { ReactNode } from "react"
import { studioColor } from "@/lib/studio-colors"

/**
 * The hub's sole page-title primitive. Every top-level route renders one of
 * these. Carries the Cabinet Grotesk display face + a bottom rule; optional
 * studio accent tints the eyebrow and adds a 2px left rule that frames the
 * title block — "studio color owns its context" per the brand brief.
 *
 * Deliberately unopinionated about the actions slot: pass in filter tabs,
 * buttons, a search input, whatever the page needs on the right.
 */
export function PageHeader({
  title,
  eyebrow,
  subtitle,
  actions,
  studioAccent,
}: {
  title: ReactNode
  eyebrow?: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  studioAccent?: string
}) {
  const accent = studioAccent ? studioColor(studioAccent) : undefined

  return (
    <header
      className="page-header"
      style={{
        display: "grid",
        gridTemplateColumns: accent ? "2px minmax(0, 1fr) auto" : "minmax(0, 1fr) auto",
        alignItems: "end",
        gap: 16,
        columnGap: accent ? 14 : 16,
        marginBottom: 24,
        paddingBottom: 20,
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      {accent && (
        <span
          aria-hidden="true"
          style={{
            alignSelf: "stretch",
            background: accent,
            borderRadius: 1,
            width: 2,
          }}
        />
      )}

      <div style={{ minWidth: 0 }}>
        {eyebrow && (
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: accent ?? "var(--color-text-faint)",
              marginBottom: 10,
            }}
          >
            {eyebrow}
          </div>
        )}

        <h1 className="display-hero">{title}</h1>

        {subtitle && (
          <div
            style={{
              fontSize: 13,
              color: "var(--color-text-muted)",
              marginTop: 8,
              maxWidth: "65ch",
            }}
          >
            {subtitle}
          </div>
        )}
      </div>

      {actions && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexWrap: "wrap",
            justifyContent: "flex-end",
          }}
        >
          {actions}
        </div>
      )}
    </header>
  )
}
