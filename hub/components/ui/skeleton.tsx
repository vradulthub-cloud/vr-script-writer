export function SkeletonBar({ width, height = 10 }: { width: number | string; height?: number }) {
  return (
    <span
      aria-hidden="true"
      style={{
        display: "inline-block",
        width,
        height,
        borderRadius: 3,
        background: "linear-gradient(90deg, var(--color-elevated) 0%, var(--color-border) 50%, var(--color-elevated) 100%)",
        backgroundSize: "200% 100%",
        animation: "skeletonShimmer 1400ms linear infinite",
        flexShrink: 0,
      }}
    />
  )
}

export function TableSkeleton({ rows = 4, cols = 3 }: { rows?: number; cols?: number }) {
  const colWidths = [80, 140, 60, 100, 80, 120]
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 1 }} aria-label="Loading…" aria-live="polite">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            padding: "8px 12px",
            borderBottom: "1px solid var(--color-border-subtle, var(--color-border))",
            opacity: 1 - i * (0.6 / rows),
          }}
        >
          {Array.from({ length: cols }).map((_, j) => (
            <SkeletonBar key={j} width={colWidths[j % colWidths.length]} />
          ))}
        </div>
      ))}
    </div>
  )
}
