import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MatrixTable } from './MatrixTable'
import type { MatrixData } from './types'

const data: MatrixData = {
  weeks: [
    {
      week_ending_friday: '2026-10-30',
      servpro_corporate: {
        amount: 67467,
        line_items: [
          { label: 'SERVPRO Sales Order', raw_ref: 'SO-05381', amount: 60375 },
          { label: 'SERVPRO Sales Order', raw_ref: 'SO-05998', amount: 7092 },
        ],
      },
      amazon: { amount: 0 },
    },
    { week_ending_friday: '2026-11-06', servpro_corporate: { amount: 0 }, amazon: { amount: 0 } },
  ],
  rows: [
    { kind: 'section', code: '', label: 'REVENUES', field: null, values: [] },
    { kind: 'line', code: '1100.1', label: 'SERVPRO', field: 'servpro_corporate', values: [67467, 0] },
    { kind: 'line', code: '1100.3', label: 'Amazon', field: 'amazon', values: [0, -559] },
  ],
}

describe('MatrixTable', () => {
  it('shows dashes for zero cells and red negative amounts', () => {
    render(<MatrixTable data={data} weeks={52} query="" />)
    const row = screen.getByText('Amazon').closest('tr')!
    expect(within(row).getByText('−$559')).toHaveClass('neg')
    expect(within(row).getByText('—')).toBeInTheDocument()
  })
  it('limits the weeks shown', () => {
    render(<MatrixTable data={data} weeks={1} query="" />)
    expect(screen.getAllByRole('columnheader')).toHaveLength(3) // code, account, one week
  })
  it('filters rows by label or code but keeps section headings', () => {
    render(<MatrixTable data={data} weeks={52} query="1100.3" />)
    expect(screen.queryByText('SERVPRO')).not.toBeInTheDocument()
    expect(screen.getByText('Amazon')).toBeInTheDocument()
    expect(screen.getByText('REVENUES')).toBeInTheDocument()
  })
  it('opens the line items behind a cell, and only for cells that have some', async () => {
    render(<MatrixTable data={data} weeks={52} query="" />)
    expect(screen.getAllByRole('button')).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: /SERVPRO, week ending 2026-10-30/ }))
    const dlg = await screen.findByRole('dialog')
    expect(within(dlg).getByText('SO-05381')).toBeInTheDocument()
    expect(within(dlg).getByText('$7,092')).toBeInTheDocument()
    expect(within(dlg).getByText(/Total:/)).toHaveTextContent('Total: $67,467')
  })
})
