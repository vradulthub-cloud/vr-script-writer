/** Custom calendar events. Backed by the FastAPI /calendar-events endpoint
 *  so the team shares one calendar. This module owns the UI-facing shape
 *  and the color palette; the network layer lives in lib/api.ts.
 */

import type { CalendarEventRow } from "./api"

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

/** Adapt a wire-shape event (snake_case, always-string fields) into the
 *  UI-facing CalendarEvent (camelCase id, optional strings). */
export function rowToEvent(r: CalendarEventRow): CalendarEvent {
  return {
    id: r.event_id,
    date: r.date,
    title: r.title,
    kind: r.kind || undefined,
    color: r.color || undefined,
    notes: r.notes || undefined,
  }
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

