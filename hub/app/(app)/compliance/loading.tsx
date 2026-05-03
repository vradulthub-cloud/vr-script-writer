/**
 * Route-segment loading skeleton. Next.js renders this instantly while
 * page.tsx awaits its compliance.shoots() fetch — replaces the blank
 * screen the user was seeing during the 1–10s cold load.
 */
export default function Loading() {
  return (
    <div
      aria-busy="true"
      style={{
        padding: "24px 28px",
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}
    >
      <SkelBar w={180} h={22} />
      <SkelBar w={"40%"} h={12} />
      <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            style={{
              padding: "14px 16px",
              borderRadius: 6,
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              display: "flex",
              alignItems: "center",
              gap: 14,
            }}
          >
            <SkelBar w={56} h={16} />
            <SkelBar w={"30%"} h={12} />
            <span style={{ flex: 1 }} />
            <SkelBar w={80} h={20} />
            <SkelBar w={80} h={20} />
          </div>
        ))}
      </div>
    </div>
  )
}

function SkelBar({ w, h }: { w: number | string; h: number }) {
  return (
    <span
      aria-hidden="true"
      style={{
        display: "inline-block",
        width: w,
        height: h,
        borderRadius: 3,
        background:
          "linear-gradient(90deg, var(--color-elevated) 0%, var(--color-border) 50%, var(--color-elevated) 100%)",
        backgroundSize: "200% 100%",
        animation: "skeletonShimmer 1400ms linear infinite",
      }}
    />
  )
}
