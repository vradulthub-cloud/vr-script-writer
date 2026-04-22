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
 * Full-width strip of operational stats. Replaces the old vertical "System"
 * card which got crammed into a narrow right-column. The strip is visible
 * across all admin tabs because freshness/health is the kind of thing you
 * always want at a glance — burying it inside a Health tab would mean
 * admins forget to look.
 *
 * Layout uses CSS grid auto-fit so tiles wrap on narrower screens; on
 * desktop they line up in a single dense row.
 */
export function StatStrip({ stats }: { stats: StatTile[] }): ReactNode {
  return (
    <section
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
        gap: 1,                    // hairline divider between tiles
        background: "var(--color-border)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        overflow: "hidden",
        marginBottom: 24,
      }}
    >
      {stats.map((s, i) => (
        <div
          key={`${s.label}-${i}`}
          style={{
            background: "var(--color-surface)",
            padding: "14px 16px",
            display: "flex",
            flexDirection: "column",
            gap: 4,
            minWidth: 0,
          }}
        >
          <div
            style={{
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              color: "var(--color-text-muted)",
            }}
          >
            {s.label}
          </div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 800,
              letterSpacing: "-0.02em",
              color: s.accent ?? "var(--color-text)",
              fontFamily: s.mono ? "var(--font-mono)" : "inherit",
              lineHeight: 1.1,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
            title={s.value}
          >
            {s.value}
          </div>
          {s.sub && (
            <div
              style={{
                fontSize: 10,
                color: "var(--color-text-faint)",
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={s.sub}
            >
              {s.sub}
            </div>
          )}
        </div>
      ))}
    </section>
  )
}
