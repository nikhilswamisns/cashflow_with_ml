import { fetchMatrix } from './api'
import { stubApi } from '@/test/utils'

afterEach(() => vi.unstubAllGlobals())

describe('fetchMatrix', () => {
  it('passes a run that has a layout straight through', async () => {
    const layout = [{ kind: 'line', code: '1100.1', label: 'SERVPRO', field: 'servpro_corporate', values: [1, 2] }]
    stubApi({ 'GET /runs/r1/matrix': { weeks: [{ week_ending_friday: '2026-10-30' }], layout } })
    const m = await fetchMatrix('r1')
    expect(m.rows).toEqual(layout)
  })
  it('builds the fixed row list for older runs without a layout, reading plain numbers and {amount} cells', async () => {
    stubApi({
      'GET /runs/old/matrix': {
        weeks: [
          {
            week_ending_friday: '2026-10-30',
            opening_cash: 100,
            amazon: { amount: 5, line_items: [] },
            ending_cash: 90,
          },
          { week_ending_friday: '2026-11-06', opening_cash: 90, amazon: { amount: 7 }, ending_cash: 80 },
        ],
      },
    })
    const m = await fetchMatrix('old')
    const by = (label: string) => m.rows.find((r) => r.label === label)!
    expect(by('Amazon').values).toEqual([5, 7])
    expect(by('Opening Cash Position').values).toEqual([100, 90])
    expect(by('Ending Cash Position').kind).toBe('ending')
    expect(by('REVENUES').kind).toBe('section')
    expect(by('Adjustments').values).toEqual([0, 0]) // missing field reads as zero
  })
})
