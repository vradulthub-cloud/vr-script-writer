// ─── localStorage helpers + parse util ───────────────────────────────────────

const PENDING_KEY = "hub:approvals:pending"

export interface PersistedDecision {
  approvalIds: string[]
  decision: "Approved" | "Rejected"
  notes?: string
  queuedAt: number
}

export function readPersistedDecisions(): PersistedDecision[] {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(PENDING_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function writePersistedDecisions(entries: PersistedDecision[]): void {
  if (typeof window === "undefined") return
  try {
    if (entries.length === 0) window.localStorage.removeItem(PENDING_KEY)
    else window.localStorage.setItem(PENDING_KEY, JSON.stringify(entries))
  } catch {
    // Quota / private mode — nothing we can do; in-memory ref still carries it.
  }
}

export function appendPersistedDecision(entry: PersistedDecision): void {
  writePersistedDecisions([...readPersistedDecisions(), entry])
}

export function clearPersistedDecisionsFor(ids: string[]): void {
  const set = new Set(ids)
  writePersistedDecisions(readPersistedDecisions().filter((e) => !e.approvalIds.some((id) => set.has(id))))
}

// ─── parseContentJson ─────────────────────────────────────────────────────────

export type ParsedContent =
  | { kind: "sections"; sections: { label: string; value: string }[] }
  | { kind: "raw"; text: string }
  | { kind: "empty" }

export function parseContentJson(raw: string | null | undefined): ParsedContent {
  if (!raw?.trim()) return { kind: "empty" }
  try {
    const parsed = JSON.parse(raw)
    if (typeof parsed === "string") {
      return parsed.trim() ? { kind: "raw", text: parsed } : { kind: "empty" }
    }
    if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
      const sections = Object.entries(parsed)
        .filter(([, v]) => typeof v === "string" && (v as string).trim())
        .map(([k, v]) => ({
          label: k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
          value: v as string,
        }))
      return sections.length ? { kind: "sections", sections } : { kind: "empty" }
    }
  } catch {
    // not JSON — treat as raw text
  }
  return raw.trim() ? { kind: "raw", text: raw } : { kind: "empty" }
}
