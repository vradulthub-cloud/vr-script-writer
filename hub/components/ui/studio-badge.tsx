import { studioColor, studioAbbr } from "@/lib/studio-colors"

export function StudioBadge({ studio }: { studio: string }) {
  const color = studioColor(studio)
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded-sm"
      style={{
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: "0.04em",
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
        color,
        border: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
        textTransform: "uppercase",
      }}
    >
      {studioAbbr(studio)}
    </span>
  )
}
