/**
 * Date helpers — local-timezone safe.
 *
 * The bug magnet we're avoiding: the backend sends shoot/release dates as
 * bare `YYYY-MM-DD` strings (no time, no zone). `new Date("2026-04-30")`
 * and `Date.parse("2026-04-30")` both interpret that as **UTC midnight**.
 * In any timezone west of UTC, that timestamp lands on the *previous*
 * calendar day in local time — so calendars and date displays drift back
 * one day for users in PT (UTC-7), and the same logic drifts forward for
 * users east of UTC if you go through `toISOString()`.
 *
 * Use these helpers anywhere you're working with bare-date strings.
 */

/**
 * Parse a bare `YYYY-MM-DD` (or any string starting with one) as **local
 * midnight** of that calendar day. Returns the timestamp in ms.
 *
 *   parseLocalDate("2026-04-30") → local midnight Apr 30 in user's TZ
 *
 * Returns null if the string doesn't start with a YYYY-MM-DD pattern.
 */
export function parseLocalDate(s: string | null | undefined): number | null {
  if (!s) return null
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!m) return null
  return new Date(+m[1], +m[2] - 1, +m[3]).getTime()
}

/** Same as parseLocalDate but returns a Date object (or null). */
export function parseLocalDateAsDate(s: string | null | undefined): Date | null {
  const t = parseLocalDate(s)
  return t === null ? null : new Date(t)
}

/**
 * Format a bare `YYYY-MM-DD` for display, parsing it as local midnight first.
 *
 *   formatLocalDate("2026-04-30", { weekday: "short", month: "short", day: "numeric" })
 *     → "Thu, Apr 30"  (in any timezone — does NOT drift to Wed Apr 29)
 *
 * Returns the input string unchanged (or "—" for empty input) if it can't be parsed.
 */
export function formatLocalDate(
  s: string | null | undefined,
  opts: Intl.DateTimeFormatOptions = { weekday: "short", month: "short", day: "numeric", year: "numeric" },
): string {
  const d = parseLocalDateAsDate(s)
  if (!d) return s || "—"
  return d.toLocaleDateString("en-US", opts)
}

/**
 * Today's date as a local `YYYY-MM-DD` key.
 *
 *   localTodayKey() → "2026-04-29"  (in user's local TZ; does NOT drift to
 *                                    "2026-04-30" after 5 PM PT due to UTC)
 *
 * Use for calendar "today" highlights, day-bucket comparisons, etc.
 */
export function localTodayKey(): string {
  return localDateKey(new Date())
}

/** Convert a Date to a local `YYYY-MM-DD` key. */
export function localDateKey(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}
