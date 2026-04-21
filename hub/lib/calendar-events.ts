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
  notes?: string
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
