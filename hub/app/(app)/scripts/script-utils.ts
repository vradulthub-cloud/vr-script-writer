const SECTION_KEYS = ["THEME", "PLOT", "SHOOT LOCATION", "SET DESIGN", "PROPS", "WARDROBE - FEMALE", "WARDROBE - MALE"]

/**
 * Normalize the Scripts sheet's column D ("Scene") into the API's BG/BGCP.
 * Writers spell creampie scenes as "BGCP", "B/G CP", "Creampie", "CP", etc.
 * Anything that mentions creampie/CP becomes BGCP; everything else (including
 * blanks) defaults to BG. NaughtyJOI / VRAllure don't use this — their
 * generators have studio-specific scene types handled at the call site.
 */
export function normalizeSceneType(raw: string | undefined | null): "BG" | "BGCP" {
  const s = (raw ?? "").toUpperCase().replace(/[^A-Z]/g, "")
  if (!s) return "BG"
  return s.includes("CREAMPIE") || s.includes("CP") ? "BGCP" : "BG"
}

export function parseSections(text: string): Record<string, string> {
  const clean = text.replace(/\*\*([^*\n]+)\*\*/g, "$1")
  const result: Record<string, string> = {}
  const lookahead = SECTION_KEYS.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ":").join("|")
  for (const key of SECTION_KEYS) {
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    const re = new RegExp(`${escaped}:([\\s\\S]*?)(?=${lookahead}|$)`, "i")
    const m = clean.match(re)
    if (m) result[key] = m[1].trim()
  }
  return result
}
