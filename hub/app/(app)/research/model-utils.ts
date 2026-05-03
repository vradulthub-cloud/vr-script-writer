import { API_BASE_URL } from "@/lib/api"

// ─── Score / rank colour helpers ─────────────────────────────────────────────

export function scoreColor(s: number) {
  if (s >= 70) return "var(--color-ok)"
  if (s >= 50) return "var(--color-lime)"
  if (s >= 30) return "var(--color-warn)"
  return "var(--color-text-muted)"
}

export const RANK_COLOR: Record<string, string> = {
  great: "var(--color-ok)", good: "var(--color-lime)", moderate: "var(--color-warn)", poor: "var(--color-err)",
}

// ─── Photo URL helpers ────────────────────────────────────────────────────────

/** Server-side photo proxy — bypasses hotlink blocks, tries cache → VRPorn → Babepedia */
export function modelPhotoUrl(name: string) {
  return `${API_BASE_URL}/api/models/${encodeURIComponent(name.trim())}/photo`
}

export function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase()).join("")
}

// ─── Sanity-flag scraped physical stats ──────────────────────────────────────

export function isSuspiciousStat(label: string, value: string): boolean {
  if (label === "Height") {
    const ftIn = value.match(/(\d+)['′]\s*(\d+)/)
    const cm   = value.match(/(\d+)\s*cm/i)
    let totalIn = 0
    if (ftIn) totalIn = parseInt(ftIn[1]) * 12 + parseInt(ftIn[2])
    else if (cm) totalIn = Math.round(parseInt(cm[1]) / 2.54)
    return totalIn > 0 && (totalIn < 57 || totalIn > 73) // <4′9″ or >6′1″
  }
  if (label === "Weight") {
    const lbs = value.match(/(\d+)\s*(lb|lbs|pound)/i)
    const kg  = value.match(/(\d+)\s*kg/i)
    let w = 0
    if (lbs) w = parseInt(lbs[1])
    else if (kg) w = Math.round(parseInt(kg[1]) * 2.205)
    return w > 0 && (w < 88 || w > 180)
  }
  return false
}
