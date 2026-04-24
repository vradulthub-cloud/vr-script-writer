import type { Ticket } from "@/lib/api"

const SCENE_PREFIX_TO_STUDIO: Record<string, string> = {
  FPVR: "FuckPassVR",
  VRH:  "VRHush",
  VRA:  "VRAllure",
  NJOI: "NaughtyJOI",
  NNJOI: "NaughtyJOI",  // Grail-tab variant — see CLAUDE.md studio mapping table.
}
const SCENE_ID_RE = /\b(NNJOI|NJOI|FPVR|VRH|VRA)[-_]?\d{2,5}\b/gi

/**
 * Extract every studio referenced by a ticket via its linked_items field.
 * Returns the set of full studio keys ("FuckPassVR", "VRHush", ...).
 * Empty set when no scene IDs are linked — those tickets pass any studio
 * filter only when "All" is selected.
 */
export function studiosFromTicket(t: Ticket): Set<string> {
  const out = new Set<string>()
  const haystack = `${t.linked_items ?? ""} ${t.title ?? ""}`
  let m: RegExpExecArray | null
  SCENE_ID_RE.lastIndex = 0
  while ((m = SCENE_ID_RE.exec(haystack)) !== null) {
    const prefix = m[1].toUpperCase()
    const studio = SCENE_PREFIX_TO_STUDIO[prefix]
    if (studio) out.add(studio)
  }
  return out
}

const DATE_FMT = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" })

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10)
  return DATE_FMT.format(d)
}
