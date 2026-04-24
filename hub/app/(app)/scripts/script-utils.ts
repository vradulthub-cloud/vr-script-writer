const SECTION_KEYS = ["THEME", "PLOT", "SHOOT LOCATION", "SET DESIGN", "PROPS", "WARDROBE - FEMALE", "WARDROBE - MALE"]

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
