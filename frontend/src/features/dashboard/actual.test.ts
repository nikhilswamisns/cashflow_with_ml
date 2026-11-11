import { actualValues, buildSlots, latestPoint, onSlots, slotLabel, weekIsoDates } from './actual'

const weeks = ['2026-11-06', '2026-11-13', '2026-11-20'] // week 1 already over on 11 Nov
const points = [
  { date: '2026-10-28', balance: 72, kind: 'start' as const },
  { date: '2026-10-30', balance: 31, kind: 'week_end' as const },
  { date: '2026-11-06', balance: 54, kind: 'week_end' as const },
  { date: '2026-11-11', balance: 60, kind: 'today' as const },
]
const a = { startDate: '2026-10-28', points }

describe('buildSlots', () => {
  it('puts today between the Fridays, in date order, with no earlier date than week 1', () => {
    expect(buildSlots(weeks, '2026-11-11')).toEqual({
      dates: ['2026-11-06', '2026-11-11', '2026-11-13', '2026-11-20'],
      todayIdx: 1,
    })
  })
  it('does not repeat a date when today is a forecast Friday', () => {
    expect(buildSlots(weeks, '2026-11-13')).toEqual({ dates: weeks, todayIdx: 1 })
  })
  it('is just the weeks while the actuals have not loaded', () => {
    expect(buildSlots(weeks, null)).toEqual({ dates: weeks, todayIdx: null })
  })
})

describe('latestPoint', () => {
  it("is today's balance", () => expect(latestPoint(a)?.balance).toBe(60))
  it('is the latest Friday when today is a Friday', () => {
    expect(latestPoint({ ...a, points: points.slice(0, 3) })?.date).toBe('2026-11-06')
  })
})

describe('onSlots', () => {
  const { dates, todayIdx } = buildSlots(weeks, '2026-11-11')
  it("keeps the engine's value per week and starts at today's actual balance", () => {
    expect(onSlots([10, 20, 30], dates, weeks, todayIdx, 60)).toEqual([10, 60, 20, 30])
  })
  it('leaves the today slot empty when there is no actual balance', () => {
    expect(onSlots([10, 20, 30], dates, weeks, todayIdx, null)).toEqual([10, null, 20, 30])
  })
})

describe('actualValues', () => {
  const { dates } = buildSlots(weeks, '2026-11-11')
  it('has a dot on each ended Friday that is on the axis, and on today', () => {
    expect(actualValues(dates, a)).toEqual([54, 60, null, null])
  })
})

describe('the chart axis end to end (labels from the dashboard -> slots -> axis text)', () => {
  const labels = ['11-06', '11-13', '11-20', '11-27', '12-04', '12-11', '12-18', '12-25', '01-01', '01-08']
  it('turns MM-DD week labels into ISO dates and rolls the year over in January', () => {
    const iso = weekIsoDates(labels, '2026-11-06')
    expect(iso.slice(0, 2)).toEqual(['2026-11-06', '2026-11-13'])
    expect(iso.slice(-2)).toEqual(['2027-01-01', '2027-01-08'])
  })
  it('never produces "undefined" or an out-of-order axis, with or without actuals', () => {
    const iso = weekIsoDates(labels, '2026-11-06')
    for (const today of ['2026-11-11', null]) {
      const { dates } = buildSlots(iso, today)
      const text = dates.map(slotLabel)
      expect(text.join(' ')).not.toMatch(/undefined|NaN/)
      expect([...dates].sort()).toEqual(dates)
    }
    expect(buildSlots(iso, '2026-11-11').dates.map(slotLabel).slice(0, 3)).toEqual(['Nov 6', 'Nov 11', 'Nov 13'])
  })
})
