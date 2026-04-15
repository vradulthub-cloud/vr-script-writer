"use client"

import { STUDIO_COLOR } from "@/lib/studio-colors"

const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

interface StudioSelectorProps {
  value: string
  onChange: (studio: string) => void
  /** Include an "All" option at the start */
  showAll?: boolean
  /** Visual size variant */
  size?: "sm" | "md"
}

export function StudioSelector({ value, onChange, showAll, size = "sm" }: StudioSelectorProps) {
  const options = showAll ? ["All", ...STUDIOS] : STUDIOS

  return (
    <div className="flex gap-1.5 flex-wrap">
      {options.map((s) => {
        const active = value === s
        const color = s === "All" ? "var(--color-text-muted)" : STUDIO_COLOR[s]
        const pad = size === "md" ? "px-3 py-1.5" : "px-2.5 py-1"
        const fs = size === "md" ? 12 : 11

        return (
          <button
            key={s}
            type="button"
            onClick={() => onChange(s)}
            className={`${pad} rounded transition-colors`}
            style={{
              fontSize: fs,
              fontWeight: active ? 600 : 500,
              background: active
                ? `color-mix(in srgb, ${color} 15%, transparent)`
                : "transparent",
              color: active ? color : "var(--color-text-muted)",
              border: `1px solid ${active
                ? `color-mix(in srgb, ${color} 30%, transparent)`
                : "var(--color-border)"}`,
            }}
          >
            {s}
          </button>
        )
      })}
    </div>
  )
}

export { STUDIOS }
