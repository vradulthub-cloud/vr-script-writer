import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Backend writes timestamps in UTC. New rows are ISO-8601 with "Z";
// legacy rows are "YYYY-MM-DD HH:MM" with no timezone marker. V8 returns
// Invalid Date for `new Date("2026-04-25 12:34Z")` and parses the unmarked
// form as *local* time. This normalizes both to a UTC epoch.
export function parseUtcTimestamp(s: string | null | undefined): number {
  if (!s) return NaN
  if (/[zZ]|[+-]\d\d:?\d\d$/.test(s)) return new Date(s).getTime()
  const padded = s.length === 16 ? `${s}:00` : s  // add seconds if missing
  return new Date(`${padded.replace(" ", "T")}Z`).getTime()
}

export function relativeTime(timestamp: string | null | undefined): string {
  const t = parseUtcTimestamp(timestamp)
  if (!Number.isFinite(t)) return ""
  const diff = Date.now() - t
  const m = Math.floor(diff / 60_000)
  if (m < 2)  return "just now"
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}
