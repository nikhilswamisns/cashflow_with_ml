import { actualValues, weekDates } from './actual'

describe('weekDates', () => {
  it('starts history weeks before the first week and walks in 7-day steps across a year end', () => {
    expect(weekDates('2026-10-30', 2, 3)).toEqual([
      '2026-10-16',
      '2026-10-23',
      '2026-10-30',
      '2026-11-06',
      '2026-11-13',
    ])
    expect(weekDates('2026-12-25', 0, 2)).toEqual(['2026-12-25', '2027-01-01'])
  })
})

describe('actualValues', () => {
  const weeks = weekDates('2026-10-30', 2, 4) // Oct 16 .. Nov 13
  const a = {
    firstWeek: '2026-10-30',
    historyWeeks: 2,
    points: [
      { date: '2026-10-23', balance: 70, kind: 'week_end' as const },
      { date: '2026-10-30', balance: 31, kind: 'week_end' as const },
      { date: '2026-11-06', balance: 54, kind: 'week_end' as const },
      { date: '2026-11-10', balance: 60, kind: 'today' as const },
    ],
  }
  it('fills past Fridays, leaves the future empty and puts today in the week still in progress', () => {
    const { values, todayIdx } = actualValues(weeks, a)
    expect(values).toEqual([null, 70, 31, 54, 60, null]) // Oct 16 unknown, Nov 13 slot holds today, Nov 20 empty
    expect(todayIdx).toBe(4)
  })
  it('has no today marker when the points end on a Friday', () => {
    const { values, todayIdx } = actualValues(weeks, { ...a, points: a.points.slice(0, 3) })
    expect(values).toEqual([null, 70, 31, 54, null, null])
    expect(todayIdx).toBeNull()
  })
})
