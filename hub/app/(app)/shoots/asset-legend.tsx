import { PHASES, PHASE_GAP, CELL_GAP } from "./shoot-utils"

export function AssetLegend() {
  return (
    <div
      aria-hidden="true"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 10,
        background: "var(--color-bg)",
        borderBottom: "1px solid var(--color-border-subtle)",
        paddingBottom: 6,
        marginBottom: -2,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 12px 2px",
          color: "var(--color-text-faint)",
          fontSize: 9,
          fontWeight: 600,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}
      >
        <span style={{ width: 150 + 12, flexShrink: 0 }} />
        <span style={{ width: 64 + 8, flexShrink: 0 }} />
        {PHASES.map((phase, pi) => (
          <div
            key={phase.name}
            style={{
              display: "flex",
              gap: CELL_GAP,
              marginRight: pi < PHASES.length - 1 ? PHASE_GAP : 0,
              alignItems: "center",
            }}
          >
            <span
              style={{
                width: phase.assets.length * (16 + CELL_GAP) - CELL_GAP,
                color: "var(--color-text-muted)",
                textAlign: "center",
              }}
            >
              {phase.name}
            </span>
          </div>
        ))}
      </div>
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "0 12px", fontSize: 9, color: "var(--color-text-faint)",
      }}>
        {([
          ["var(--color-border)", "not yet"],
          ["var(--color-warn)",   "in flight"],
          ["var(--color-ok)",     "validated"],
          ["var(--color-err)",    "blocked"],
        ] as [string, string][]).map(([color, label]) => (
          <span key={label} style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <span style={{
              display: "inline-block", width: 8, height: 8, borderRadius: 2,
              background: color, flexShrink: 0,
            }} />
            {label}
          </span>
        ))}
        <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
          <span style={{
            display: "inline-block", width: 8, height: 8, borderRadius: 2,
            border: "1px dashed var(--color-border)", opacity: 0.4, flexShrink: 0,
          }} />
          n/a
        </span>
      </div>
    </div>
  )
}
