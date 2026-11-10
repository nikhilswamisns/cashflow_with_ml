import { actualValues, slotDates } from './actual'

describe('slotDates', () => {
  it('starts with the day the run was made, then weekly Fridays from the first one, across a year end', () => {
    expect(slotDates('2026-10-28', '2026-10-30', 3)).toEqual(['2026-10-28', '2026-10-30', '2026-11-06', '2026-11-13'])
    expect(slotDates('2026-12-22', '2026-12-25', 2)).toEqual(['2026-12-22', '2026-12-25', '2027-01-01'])
  })
})

describe('actualValues', () => {
  const slots = slotDates('2026-10-28', '2026-10-30', 5) // Oct 28 start, Oct 30 .. Nov 27
  const points = [
    { date: '2026-10-28', balance: 72, kind: 'start' as const },
    { date: '2026-10-30', balance: 31, kind: 'week_end' as const },
    { date: '2026-11-06', balance: 54, kind: 'week_end' as const },
    { date: '2026-11-10', balance: 60, kind: 'today' as const },
  ]
  const a = { startDate: '2026-10-28', points }
  it('starts at the run start, fills past Fridays, leaves the future empty and puts today in the week in progress', () => {
    const { values, todayIdx } = actualValues(slots, a)
    expect(values).toEqual([72, 31, 54, 60, null, null]) // Nov 13 slot holds today's balance
    expect(todayIdx).toBe(3)
  })
  it('has no today marker when the points end on a Friday', () => {
    const { values, todayIdx } = actualValues(slots, { ...a, points: points.slice(0, 3) })
    expect(values).toEqual([72, 31, 54, null, null, null])
    expect(todayIdx).toBeNull()
  })
})
