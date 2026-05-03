import type { ReactNode } from "react"

export interface StatTile {
  label: string
  value: string
  sub?: string
  /** Studio identity color when relevant; defaults to neutral text. */
  accent?: string
  /** Use the mono font for fixed-width values (versions, ids, percentages). */
  mono?: boolean
}

/**
 * Compact single-line status bar for the admin console. Previously rendered
 * as a 7-tile grid with 22px bold numerals — the chrome dominated the page
 * even though the real work lives inside the tabs. Demoted to a quiet strip
 * that reads at-a-glance without competing with the tab content for
 * attention.
 *
 * Entries flow inline with tabular-numerics, separated by a faint pipe. The
 * strip wraps on narrow viewports so it never truncates the status line.
 */
export function StatStrip({ stats }: { stats: StatTile[] }): ReactNode {
  return (
    <section
      aria-label="Admin status"
      style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "baseline",
        gap: "4px 14px",
        padding: "8px 14px",
        marginBottom: 20,
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        fontSize: 12,
        lineHeight: 1.6,
        fontVariantNumeric: "tabular-nums",
      }}
    >
      {stats.map((s, i) => (
        <span
          key={`${s.label}-${i}`}
          style={{ display: "inline-flex", alignItems: "baseline", gap: 6, minWidth: 0 }}
        >
          {i > 0 && (
            <span aria-hidden="true" style={{ color: "var(--color-border)", marginRight: 8 }}>
              |
            </span>
          )}
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "var(--color-text-faint)",
            }}
          >
            {s.label}
          </span>
          <span
            title={s.value}
            style={{
              color: s.accent ?? "var(--color-text)",
              fontFamily: s.mono ? "var(--font-mono)" : "inherit",
              fontWeight: 500,
            }}
          >
            {s.value}
          </span>
          {s.sub && (
            <span
              title={s.sub}
              style={{
                fontSize: 11,
                color: "var(--color-text-faint)",
              }}
            >
              ({s.sub})
            </span>
          )}
        </span>
      ))}
    </section>
  )
}
