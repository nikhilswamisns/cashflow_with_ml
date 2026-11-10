import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { LoansEditor } from './LoansEditor'
import { ToastProvider } from '@/shared/toast'
import { newClient, stubApi } from '@/test/utils'
import type { Loans } from './types'

afterEach(() => vi.unstubAllGlobals())
const saved: Loans = {
  facilities: [
    {
      name: 'Amex line',
      type: 'credit_line',
      limit: 50000,
      drawn: 20000,
      rate_pct: 12,
      monthly_repayment: 1500,
      headroom: 30000,
      over_limit: false,
      monthly_interest: 200,
    },
  ],
  credit_lines: 1,
  limit: 50000,
  drawn: 20000,
  headroom: 30000,
  entered_repayments_per_month: 1500,
  entered_interest_per_month: 200,
  in_forecast: { repayments_per_month: 13333, interest_per_month: 1250 },
  note: '',
}
const wrap = (ui: React.ReactNode) => (
  <QueryClientProvider client={newClient()}>
    <ToastProvider>{ui}</ToastProvider>
  </QueryClientProvider>
)

describe('LoansEditor', () => {
  it('starts from the saved loans, works out headroom and interest as you type, and compares with the forecast', () => {
    render(wrap(<LoansEditor saved={saved} />))
    expect(screen.getByDisplayValue('Amex line')).toBeInTheDocument()
    expect(screen.getByText('$30,000')).toBeInTheDocument() // headroom
    fireEvent.change(screen.getByLabelText('Drawn'), { target: { value: '30000' } })
    expect(screen.getByText('$20,000')).toBeInTheDocument() // 50,000 - 30,000
    expect(screen.getByText(/Repayments \$13,333\/month · interest \$1,250\/month/)).toBeInTheDocument()
    expect(screen.getByText(/never adds a payment twice/)).toBeInTheDocument()
  })
  it('adds and removes a row, and saves the rows as numbers', async () => {
    const f = stubApi({ 'PUT /loans': saved })
    render(wrap(<LoansEditor saved={{ ...saved, facilities: [] }} />))
    expect(screen.getByText('No loans or credit lines entered yet.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Add a loan or credit line/ }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Term loan' } })
    fireEvent.change(screen.getByLabelText('Type'), { target: { value: 'term_loan' } })
    fireEvent.change(screen.getByLabelText('Outstanding'), { target: { value: '60000' } })
    fireEvent.change(screen.getByLabelText('Rate'), { target: { value: '6' } })
    expect(screen.getByText('$300')).toBeInTheDocument() // 60,000 x 6% / 12
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(f).toHaveBeenCalled())
    const body = JSON.parse((f.mock.calls.find((c) => String(c[1]?.method) === 'PUT')?.[1]?.body as string) ?? '{}')
    expect(body.facilities[0]).toMatchObject({
      name: 'Term loan',
      type: 'term_loan',
      drawn: 60000,
      rate_pct: 6,
      limit: 0,
    })
  })
})
