import { dlabel, kfmt, sum, tickMoney, usd } from './format'

describe('format', () => {
  it('formats dollars with a real minus sign and no cents', () => {
    expect(usd(74096.81)).toBe('$74,097')
    expect(usd(-201427.9)).toBe('−$201,428')
    expect(usd(0)).toBe('$0')
  })
  it('rounds half up like JavaScript Math.round (the parity script relies on this)', () => {
    expect(usd(0.5)).toBe('$1')
    expect(usd(2.5)).toBe('$3')
  })
  it('abbreviates large amounts', () => {
    expect(kfmt(9_024_536)).toBe('$9.02M')
    expect(kfmt(-201_428)).toBe('−$201.4K')
    expect(kfmt(950)).toBe('$950')
    expect(tickMoney(600_000)).toBe('$600K')
    expect(tickMoney(1_500_000)).toBe('$1.5M')
  })
  it('turns MM-DD week labels into short dates', () => {
    expect(dlabel('12-25')).toBe('Dec 25')
    expect(dlabel('01-08')).toBe('Jan 8')
  })
  it('sums', () => {
    expect(sum([1, 2, 3.5])).toBe(6.5)
    expect(sum([])).toBe(0)
  })
})
