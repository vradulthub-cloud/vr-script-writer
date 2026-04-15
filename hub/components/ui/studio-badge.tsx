import { studioColor, studioAbbr } from "@/lib/studio-colors"

export function StudioBadge({ studio }: { studio: string }) {
  const color = studioColor(studio)
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded"
      style={{
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.06em",
        background: `color-mix(in srgb, ${color} 18%, transparent)`,
        color,
        border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
        textTransform: "uppercase",
      }}
    >
      {studioAbbr(studio)}
    </span>
  )
}
