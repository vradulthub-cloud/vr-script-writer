"use client"

import { useState } from "react"
import { initials } from "./model-utils"

// ─── Photo component ──────────────────────────────────────────────────────────

/**
 * Photo defaults to decorative (alt=""). Pass `decorative={false}` on
 * semantic headshots (ProfileView hero image) so screen readers announce
 * who is shown — a name is non-decorative context there.
 */
export function Photo({
  src,
  fallbackSrc,
  name,
  width,
  height,
  radius = 4,
  objectPos = "50% 15%",
  decorative = true,
}: {
  src: string
  fallbackSrc?: string
  name: string
  width: number | string
  height: number
  radius?: number
  objectPos?: string
  decorative?: boolean
}) {
  const [srcIdx, setSrcIdx] = useState(0)
  const ini = initials(name)
  // De-duplicate src + fallbackSrc so a broken URL doesn't waste a slot.
  const srcs = Array.from(new Set([src, fallbackSrc].filter(Boolean))) as string[]
  const activeSrc = srcs[srcIdx]

  if (!activeSrc) {
    return (
      <div
        role={decorative ? undefined : "img"}
        aria-label={decorative ? undefined : name}
        style={{
          width, height, borderRadius: radius,
          background: "var(--color-elevated)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: typeof width === "number" ? Math.round(Number(width) * 0.28) : 28,
          fontWeight: 700, color: "var(--color-text-faint)",
          flexShrink: 0,
        }}
      >
        {ini}
      </div>
    )
  }

  return (
    <img
      src={activeSrc}
      alt={decorative ? "" : name}
      aria-hidden={decorative ? "true" : undefined}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setSrcIdx(i => i + 1)}
      style={{
        width, height, borderRadius: radius, flexShrink: 0,
        objectFit: "cover", objectPosition: objectPos, display: "block",
      }}
    />
  )
}
