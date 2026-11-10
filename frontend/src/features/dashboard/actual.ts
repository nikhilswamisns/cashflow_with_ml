import type { Actuals } from '@/features/dashboard/types'

const addDays = (iso: string, n: number) => {
  const d = new Date(iso + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

/** ISO week-ending Fridays: `history` weeks before the first week, then `count` weeks from it. */
export const weekDates = (firstWeek: string, history: number, count: number): string[] =>
  Array.from({ length: history + count }, (_, i) => addDays(firstWeek, (i - history) * 7))

/** Actual balance per week slot. Today's balance sits in the week still in progress (the next Friday) and is flagged. */
export function actualValues(weeks: string[], a: Actuals): { values: (number | null)[]; todayIdx: number | null } {
  const byDate = new Map(a.points.filter((p) => p.kind === 'week_end').map((p) => [p.date, p.balance]))
  const values = weeks.map((w) => byDate.get(w) ?? null)
  const today = a.points.find((p) => p.kind === 'today')
  let todayIdx: number | null = null
  if (today) {
    const i = weeks.findIndex((w) => w > today.date)
    if (i >= 0) {
      values[i] = today.balance
      todayIdx = i
    }
  }
  return { values, todayIdx }
}
