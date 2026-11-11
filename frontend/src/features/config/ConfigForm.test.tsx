import { fireEvent, screen, waitFor } from '@testing-library/react'
import { ConfigForm } from './ConfigForm'
import { toDoc, toDraft, problems, type Doc } from './configModel'
import { renderApp, stubApi } from '@/test/utils'

afterEach(() => vi.unstubAllGlobals())

const saved: Doc = {
  rolling_window_weeks: 52,
  biweekly_pay_anchor_date: '2026-08-21',
  vendor_payment_terms_days: { '7 Seas Sourcing': 90, 'Easydek Beschermtechniek B.V.': 0 },
  biweekly_salaries: { ops_ea_salary: 1923.0, sales_salaries: 12708.3366666667 },
  annual_fourth_friday_expenses: [{ month: 4, amount: 3000, coa_code: '6103', label: 'Accounting Fees' }],
  tax_payments: {
    irs: [{ date: '2026-09-15', amount: 16500 }],
    nj_state: [{ date: '2026-09-15', amount: 2500 }],
  },
  initial_week1_cc_actuals: { '2104': 138.52, '5107': 7212.19, '4103': 110 },
}
const putBody = (f: ReturnType<typeof stubApi>) =>
  JSON.parse((f.mock.calls.find((c) => String(c[1]?.method) === 'PUT')?.[1]?.body as string) ?? '{}')

describe('assumptions model', () => {
  it('gives back exactly the same data when nothing is edited', () => {
    expect(toDoc(toDraft(saved))).toEqual(saved)
  })
  it('flags bad numbers, bad dates, a month out of range and duplicate names', () => {
    const d = toDraft(saved)
    expect(problems(d)).toEqual([])
    const bad = toDraft({ ...saved, rolling_window_weeks: 52.5, vendor_payment_terms_days: { a: 1 } })
    if (bad.vendor_payment_terms_days.t === 'map')
      bad.vendor_payment_terms_days.rows.push({ ...bad.vendor_payment_terms_days.rows[0], id: 99 })
    expect(problems(bad)).toEqual(['Forecast window: enter a valid value.', 'Vendor payment terms: "a" appears twice.'])
  })
})

describe('ConfigForm', () => {
  it('saves the untouched form as the same data it was given', async () => {
    const f = stubApi({ 'PUT /config/assumptions': { message: 'ok' } })
    renderApp(<ConfigForm table="assumptions" saved={saved} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save & Invalidate Cache' }))
    await waitFor(() => expect(f).toHaveBeenCalled())
    expect(putBody(f)).toEqual(saved)
  })
  it('edits an amount, keeps payroll names fixed, and adds and removes a vendor row', async () => {
    const f = stubApi({ 'PUT /config/assumptions': { message: 'ok' } })
    renderApp(<ConfigForm table="assumptions" saved={saved} />)
    expect(screen.queryByText('Unsaved changes')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Ops ea salary value'), { target: { value: '2000' } })
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
    expect(screen.queryByLabelText('Remove Ops ea salary')).not.toBeInTheDocument() // payroll rows are fixed
    fireEvent.click(screen.getByLabelText('Remove 7 Seas Sourcing'))
    fireEvent.click(screen.getAllByRole('button', { name: /Add a row/ })[0])
    fireEvent.change(screen.getByLabelText('Item name'), { target: { value: 'New Vendor' } })
    fireEvent.change(screen.getByLabelText('New Vendor value'), { target: { value: '45' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save & Invalidate Cache' }))
    await waitFor(() => expect(f).toHaveBeenCalled())
    const b = putBody(f)
    expect(b.biweekly_salaries.ops_ea_salary).toBe(2000)
    expect(b.vendor_payment_terms_days).toEqual({ 'Easydek Beschermtechniek B.V.': 0, 'New Vendor': 45 })
  })
  it('blocks saving while a value is not a number, and Revert restores the saved value', () => {
    const f = stubApi({})
    renderApp(<ConfigForm table="assumptions" saved={saved} />)
    fireEvent.change(screen.getByLabelText('Forecast window'), { target: { value: 'abc' } })
    expect(screen.getByText('Forecast window: enter a valid value.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save & Invalidate Cache' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Revert changes' }))
    expect(screen.getByLabelText('Forecast window')).toHaveValue('52')
    expect(f).not.toHaveBeenCalled()
  })
  it('switches to Raw JSON and back without changing the data', () => {
    renderApp(<ConfigForm table="assumptions" saved={saved} />)
    fireEvent.click(screen.getByRole('button', { name: 'Raw JSON' }))
    expect(JSON.parse((screen.getByLabelText('Configuration JSON') as HTMLTextAreaElement).value)).toEqual(saved)
    fireEvent.click(screen.getByRole('button', { name: 'Form' }))
    expect(screen.getByLabelText('Forecast window')).toHaveValue('52')
  })
})

describe('the other config tables', () => {
  const corp: Doc = { corporate_accounts: ['SERVPRO - Corporate', 'Servpro Corporate'] }
  const freight: Doc = {
    freight_vendors_exact: ['C.H. Robinson International, Inc.'],
    freight_reference_substrings: ['EFE'],
    duty_vendors_exact: ['US Customs and Border Protection'],
  }
  const ccmap: Doc = {
    mappings: [
      {
        statement_category: 'Subscriptions',
        coa_code: '7103',
        coa_label: 'Microsoft',
        payment_method: 'credit_card_15th',
      },
    ],
  }
  it('round-trips each one unchanged', () => {
    for (const d of [corp, freight, ccmap]) expect(toDoc(toDraft(d))).toEqual(d)
  })
  it('adds and removes names in a list, and blocks a blank entry', async () => {
    const f = stubApi({ 'PUT /config/corporate_accounts': { message: 'ok' } })
    renderApp(<ConfigForm table="corporate_accounts" saved={corp} />)
    fireEvent.click(screen.getByLabelText('Remove entry 2'))
    fireEvent.click(screen.getByRole('button', { name: /Add an entry/ }))
    expect(screen.getByRole('button', { name: 'Save & Invalidate Cache' })).toBeDisabled() // blank entry
    fireEvent.change(screen.getByLabelText('Entry 2'), { target: { value: ' Servpro Corp ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save & Invalidate Cache' }))
    await waitFor(() => expect(f).toHaveBeenCalled())
    expect(putBody(f)).toEqual({ corporate_accounts: ['SERVPRO - Corporate', 'Servpro Corp'] })
  })
  it('keeps all three freight lists, and edits a category mapping', async () => {
    const f = stubApi({ 'PUT /config/cc_category_coa_map': { message: 'ok' } })
    renderApp(<ConfigForm table="cc_category_coa_map" saved={ccmap} />)
    fireEvent.change(screen.getByLabelText('Account code, row 1'), { target: { value: '7199' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save & Invalidate Cache' }))
    await waitFor(() => expect(f).toHaveBeenCalled())
    expect(putBody(f).mappings[0]).toEqual({ ...(ccmap.mappings as object[])[0], coa_code: '7199' })
  })
  it('shows each freight list under its own heading', () => {
    renderApp(<ConfigForm table="freight_duty_vendors" saved={freight} />)
    expect(screen.getByText('Freight vendors (exact name)')).toBeInTheDocument()
    expect(screen.getByText('Freight reference contains')).toBeInTheDocument()
    expect(screen.getByText('Duty vendors (exact name)')).toBeInTheDocument()
  })
})
