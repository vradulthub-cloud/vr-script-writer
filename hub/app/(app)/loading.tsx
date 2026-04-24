import { SkeletonBar } from "@/components/ui/skeleton"

// Route-segment loading state rendered inside the AppShell while any
// (app) page.tsx is resolving its data. Prevents blank-page flash on nav.
export default function AppLoading() {
  return (
    <div style={{ maxWidth: 1400 }} aria-busy="true" aria-live="polite">
      {/* Page header */}
      <div style={{ marginBottom: 28, paddingBottom: 16, borderBottom: "1px solid var(--color-border-subtle)" }}>
        <SkeletonBar width={80} height={10} />
        <div style={{ marginTop: 8 }}>
          <SkeletonBar width={260} height={22} />
        </div>
      </div>

      {/* Briefing card */}
      <div
        style={{
          padding: "14px 16px",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 6,
          marginBottom: 20,
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <SkeletonBar width={200} height={14} />
        <SkeletonBar width={320} height={10} />
      </div>

      {/* Stats strip */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 8,
          marginBottom: 20,
        }}
      >
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            style={{
              padding: "12px 14px",
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              display: "flex",
              flexDirection: "column",
              gap: 8,
              opacity: 1 - i * 0.12,
            }}
          >
            <SkeletonBar width={40} height={9} />
            <SkeletonBar width={70} height={22} />
          </div>
        ))}
      </div>

      {/* Body grid */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 320px", gap: 24 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {[90, 75, 85, 65, 80].map((w, i) => (
            <div
              key={i}
              style={{
                padding: "10px 12px",
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 5,
                display: "flex",
                gap: 10,
                alignItems: "center",
                opacity: 1 - i * 0.1,
              }}
            >
              <SkeletonBar width={56} height={40} />
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
                <SkeletonBar width={`${w}%`} height={11} />
                <SkeletonBar width="50%" height={9} />
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              style={{
                padding: "10px 12px",
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 5,
                display: "flex",
                gap: 8,
                alignItems: "flex-start",
                opacity: 1 - i * 0.12,
              }}
            >
              <SkeletonBar width={13} height={13} />
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 5 }}>
                <SkeletonBar width="80%" height={10} />
                <SkeletonBar width="60%" height={9} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
