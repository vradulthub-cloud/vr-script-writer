/** Custom calendar events. localStorage-backed for now — single-user only.
 *  TODO: hoist to backend so events are shared across the team.
 *  Why a versioned storage key: future schema changes won't read garbage from
 *  prior keys; we just bump the version and old entries are ignored.
 */

const STORAGE_KEY = "hub.calendar.events.v1"

export type CalendarEvent = {
  id: string
  date: string // YYYY-MM-DD
  title: string
  /** Free-form short tag, e.g. "MEETING", "TRAVEL", "DEADLINE". Uppercase. */
  kind?: string
  /** Slug from EVENT_COLORS (e.g. "lime", "amber"). Drives chip border + tag
   *  color so users can scan a busy month by category at a glance. */
  color?: string
  notes?: string
}

/** Curated tag palette. Eight options is enough for personal categorisation
 *  without making the picker a UX burden. Names lowercase / values either a
 *  CSS var (when the design system already owns the swatch) or a hex.
 *  We deliberately exclude the studio identity colours — those should remain
 *  unique to studio chips so the visual mapping stays clean. */
export const EVENT_COLORS = [
  { id: "lime",   label: "Lime",   value: "var(--color-lime)" },
  { id: "amber",  label: "Amber",  value: "#f59e0b" },
  { id: "red",    label: "Red",    value: "#ef4444" },
  { id: "rose",   label: "Rose",   value: "#fb7185" },
  { id: "violet", label: "Violet", value: "#a78bfa" },
  { id: "sky",    label: "Sky",    value: "#38bdf8" },
  { id: "teal",   label: "Teal",   value: "#2dd4bf" },
  { id: "slate",  label: "Slate",  value: "#94a3b8" },
] as const

export function eventColorValue(id: string | undefined): string {
  if (!id) return "var(--color-text-muted)"
  return EVENT_COLORS.find(c => c.id === id)?.value ?? "var(--color-text-muted)"
}

function read(): CalendarEvent[] {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function write(events: CalendarEvent[]): void {
  if (typeof window === "undefined") return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(events))
}

export function listEvents(): CalendarEvent[] {
  return read()
}

export function addEvent(input: Omit<CalendarEvent, "id">): CalendarEvent {
  const ev: CalendarEvent = { ...input, id: `evt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}` }
  const all = read()
  all.push(ev)
  write(all)
  return ev
}

export function removeEvent(id: string): void {
  write(read().filter(e => e.id !== id))
}
