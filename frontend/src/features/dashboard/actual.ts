import type { Actuals } from '@/features/dashboard/types'
import { dlabel } from '@/shared/format'

/** ISO dates ("2026-11-06") for the dashboard's "MM-DD" week labels. Same year rule as fullDates: start in the as-of year
 * and roll over at December to January. (fullDates returns display text, not dates; the chart needs real dates.) */
export const weekIsoDates = (labels: string[], asOf: string): string[] => {
  let y = +asOf.slice(0, 4) || new Date().getFullYear()
  let prev = 0
  return labels.map((s) => {
    const m = +s.split('-')[0]
    if (m < prev) y += 1
    prev = m
    return `${y}-${s}`
  })
}

/** The axis text for a slot date, e.g. "2026-11-06" -> "Nov 6". */
export const slotLabel = (iso: string) => dlabel(iso.slice(5))

/** The newest actual point: today's balance (or the latest Friday when today is a Friday). */
export const latestPoint = (a: Actuals) => a.points.reduce<Actuals['points'][number] | null>((m, p) => (!m || p.date > m.date ? p : m), null)

/** Chart slots in date order: the forecast weeks plus one slot for today, where every line starts. Weeks before
 * today are over; they stay on the axis so the earlier forecast can be compared with what happened. */
export function buildSlots(weeks: string[], today: string | null): { dates: string[]; todayIdx: number | null } {
  const dates = today ? [...new Set([...weeks, today])].sort() : weeks
  return { dates, todayIdx: today ? dates.indexOf(today) : null }
}

/** One forecast series on the slots: the engine's value for a week, today's actual at the today slot (the shared start),
 * and nothing for a date that is no forecast week. */
export function onSlots(
  arr: number[],
  dates: string[],
  weeks: string[],
  todayIdx: number | null,
  todayBalance: number | null,
): (number | null)[] {
  return dates.map((d, i) => (i === todayIdx && todayBalance != null ? todayBalance : (arr[weeks.indexOf(d)] ?? null)))
}

/** Actual balance per slot: each past Friday that is on the axis, and today. */
export function actualValues(slots: string[], a: Actuals): (number | null)[] {
  const byDate = new Map(a.points.map((p) => [p.date, p.balance]))
  return slots.map((w) => byDate.get(w) ?? null)
}
