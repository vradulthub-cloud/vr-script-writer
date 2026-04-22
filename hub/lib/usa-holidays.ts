/** USA federal holidays. Dates computed by rule — no external dep and no
 *  yearly data file to maintain. "Observed" shifts (holiday on Sat/Sun) are
 *  applied so the calendar shows the day most of the team is actually off.
 */

export type Holiday = {
  date: string // YYYY-MM-DD
  name: string
  short: string // 3-letter badge, e.g. "MLK"
}

/** Nth weekday of a month, 0-indexed day-of-week (Sun=0). */
function nthWeekday(year: number, month: number, weekday: number, n: number): Date {
  const first = new Date(year, month, 1)
  const offset = (weekday - first.getDay() + 7) % 7
  return new Date(year, month, 1 + offset + (n - 1) * 7)
}

/** Last weekday of a month. */
function lastWeekday(year: number, month: number, weekday: number): Date {
  const last = new Date(year, month + 1, 0)
  const offset = (last.getDay() - weekday + 7) % 7
  return new Date(year, month, last.getDate() - offset)
}

function fmt(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const dd = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${dd}`
}

/** If the fixed-date holiday lands on Sat/Sun, the observed holiday is the
 *  adjacent weekday (Sat → Fri, Sun → Mon). */
function observed(y: number, m: number, d: number): Date {
  const dt = new Date(y, m, d)
  const dow = dt.getDay()
  if (dow === 6) return new Date(y, m, d - 1)
  if (dow === 0) return new Date(y, m, d + 1)
  return dt
}

export function usaHolidaysForYear(year: number): Holiday[] {
  return [
    { date: fmt(observed(year, 0, 1)), name: "New Year's Day", short: "NYD" },
    { date: fmt(nthWeekday(year, 0, 1, 3)), name: "MLK Day", short: "MLK" },
    { date: fmt(nthWeekday(year, 1, 1, 3)), name: "Presidents' Day", short: "PRES" },
    { date: fmt(lastWeekday(year, 4, 1)), name: "Memorial Day", short: "MEM" },
    { date: fmt(observed(year, 5, 19)), name: "Juneteenth", short: "JUNE" },
    { date: fmt(observed(year, 6, 4)), name: "Independence Day", short: "IND" },
    { date: fmt(nthWeekday(year, 8, 1, 1)), name: "Labor Day", short: "LAB" },
    { date: fmt(nthWeekday(year, 9, 1, 2)), name: "Columbus Day", short: "COL" },
    { date: fmt(observed(year, 10, 11)), name: "Veterans Day", short: "VET" },
    { date: fmt(nthWeekday(year, 10, 4, 4)), name: "Thanksgiving", short: "THX" },
    { date: fmt(observed(year, 11, 25)), name: "Christmas Day", short: "XMAS" },
  ]
}

/** Returns a Map<YYYY-MM-DD, Holiday> covering `year - 1` → `year + 1` so a
 *  rendered month that spills into neighbour years still shows the right
 *  holiday chips in leading/trailing grid cells. */
export function holidayMap(year: number): Map<string, Holiday> {
  const all = [
    ...usaHolidaysForYear(year - 1),
    ...usaHolidaysForYear(year),
    ...usaHolidaysForYear(year + 1),
  ]
  return new Map(all.map(h => [h.date, h]))
}
