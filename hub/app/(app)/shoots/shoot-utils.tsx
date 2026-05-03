import { CheckCircle2, AlertTriangle, Circle, Clock } from "lucide-react"
import type { AssetStatus, AssetType, Shoot } from "@/lib/api"

export const POLL_MS = 60_000
export const AGING_WARN_HOURS = 48
export const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"] as const

export const PHASES: { name: string; assets: AssetType[] }[] = [
  { name: "Plan",  assets: ["script_done", "call_sheet_sent", "legal_run", "grail_run"] },
  { name: "Shoot", assets: ["bg_edit_uploaded", "solo_uploaded"] },
  { name: "Post",  assets: ["title_done", "encoded_uploaded", "photoset_uploaded", "storyboard_uploaded", "legal_docs_uploaded"] },
]
export const PHASE_GAP = 10
export const CELL_GAP  = 2

export const STATUS_LABEL: Record<AssetStatus, string> = {
  not_present: "not yet",
  available:   "in flight",
  validated:   "validated",
  stuck:       "stuck",
}

export const ASSET_SHORT: Record<AssetType, string> = {
  script_done:          "SCR",
  call_sheet_sent:      "CS",
  legal_run:            "LEG",
  grail_run:            "GR",
  bg_edit_uploaded:     "BG",
  solo_uploaded:        "SOLO",
  title_done:           "TTL",
  encoded_uploaded:     "ENC",
  photoset_uploaded:    "PHO",
  storyboard_uploaded:  "STB",
  legal_docs_uploaded:  "DOC",
}

export function statusColor(status: AssetStatus, hasValidityWarning: boolean): string {
  if (status === "stuck") return "var(--color-err)"
  if (status === "validated") return hasValidityWarning ? "var(--color-warn)" : "var(--color-ok)"
  if (status === "available") return "var(--color-warn)"
  return "var(--color-border)"
}

export function cellApplies(assetType: AssetType, sceneType: string): boolean {
  const t = (sceneType || "").toUpperCase()
  const isSolo = t === "SOLO" || t === "JOI"
  const isBG   = t === "BG"   || t === "BGCP"
  switch (assetType) {
    case "bg_edit_uploaded":     return isBG
    case "solo_uploaded":        return isSolo
    case "legal_run":            return isBG
    case "legal_docs_uploaded":  return isBG
    default: return true
  }
}

export function statusIcon(status: AssetStatus, hasValidityWarning: boolean) {
  if (status === "stuck")     return <AlertTriangle size={10} aria-hidden="true" />
  if (status === "validated") return hasValidityWarning ? <AlertTriangle size={10} aria-hidden="true" /> : <CheckCircle2 size={10} aria-hidden="true" />
  if (status === "available") return <Clock size={10} aria-hidden="true" />
  return <Circle size={10} aria-hidden="true" strokeWidth={1.5} />
}

export function shootCompleteness(shoot: Shoot): { validated: number; total: number } {
  let validated = 0
  let total = 0
  for (const s of shoot.scenes) {
    for (const a of s.assets) {
      total += 1
      if (a.status === "validated") validated += 1
    }
  }
  return { validated, total }
}

export function isAlert(shoot: Shoot): boolean {
  if (shoot.aging_hours < AGING_WARN_HOURS) return false
  const { validated, total } = shootCompleteness(shoot)
  return total > 0 && validated < total
}

export function formatShootDate(iso: string): string {
  if (!iso) return ""
  try {
    const d = new Date(iso + "T00:00:00")
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", weekday: "short" })
  } catch {
    return iso
  }
}

export function relativeFromHours(hours: number): string {
  if (hours === 0) return "upcoming / today"
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
