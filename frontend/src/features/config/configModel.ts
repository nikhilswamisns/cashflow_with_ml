// Turns the assumptions JSON into editable form rows and back. Values stay text while typing, like the loans editor.
export type Doc = Record<string, unknown>
export type LeafKind = 'num' | 'int' | 'month' | 'date' | 'text'
export interface Leaf {
  s: string
  kind: LeafKind
}
export interface Col {
  key: string
  label: string
  kind: LeafKind
}
export interface MapRow {
  id: number
  key: string
  v: Leaf
  isNew: boolean
}
export type Row = Record<string, Leaf>
export type Entry =
  | { t: 'scalar'; leaf: Leaf }
  | { t: 'map'; rows: MapRow[] }
  | { t: 'list'; items: { id: number; leaf: Leaf }[] }
  | { t: 'rows'; cols: Col[]; rows: Row[] }
  | { t: 'groups'; groups: { key: string; cols: Col[]; rows: Row[] }[] }
  | { t: 'other'; raw: unknown }
export type Draft = Record<string, Entry>

export interface Meta {
  title: string
  hint?: string
  unit?: string // scalar suffix, or the header of a map's value column (default "$")
  kind?: LeafKind
  cols?: Col[]
  groupTitles?: Record<string, string>
  list?: boolean // a plain list of names, even when it is empty
  fixed?: boolean // the engine reads these names one by one, so rows can be edited but not added or removed
}

const money = (key: string, label: string): Col => ({ key, label, kind: 'num' })
export const META: Record<string, Meta> = {
  rolling_window_weeks: {
    title: 'Forecast window',
    unit: 'weeks',
    kind: 'int',
    hint: 'How many weeks ahead the forecast looks.',
  },
  ar_days_convention: { title: 'Receivables convention', unit: 'days', kind: 'int' },
  servpro_corporate_net_days: {
    title: 'SERVPRO Corporate pays after',
    unit: 'days',
    kind: 'int',
    hint: 'Days after shipment that SERVPRO Corporate pays.',
  },
  po_default_payment_terms_days: {
    title: 'Default purchase order terms',
    unit: 'days',
    kind: 'int',
    hint: 'Used when a purchase order and its vendor both have no terms.',
  },
  cc_payment_day_of_month: { title: 'Credit card paid on day', unit: 'of the month', kind: 'int' },
  biweekly_pay_anchor_date: {
    title: 'Payroll anchor date',
    hint: 'Any real payday. Every 2 weeks from this date counts as a payday.',
  },
  vendor_payment_terms_days: {
    title: 'Vendor payment terms',
    unit: 'Days',
    kind: 'int',
    hint: 'Used when a purchase order has no terms of its own.',
  },
  biweekly_salaries: { title: 'Payroll, every 2 weeks', fixed: true },
  monthly_first_friday_expenses: { title: 'Paid on the 1st Friday of each month' },
  monthly_second_friday_expenses: { title: 'Paid on the 2nd Friday of each month' },
  monthly_third_friday_expenses: { title: 'Paid on the 3rd Friday of each month' },
  monthly_fourth_friday_expenses: { title: 'Paid on the 4th Friday of each month' },
  monthly_last_friday_expenses: { title: 'Paid on the last Friday of each month' },
  annual_fourth_friday_expenses: {
    title: 'Yearly payments (4th Friday of the month)',
    cols: [
      { key: 'month', label: 'Month (1-12)', kind: 'month' },
      money('amount', 'Amount ($)'),
      { key: 'coa_code', label: 'Account code', kind: 'text' },
      { key: 'label', label: 'Label', kind: 'text' },
    ],
  },
  cc_run_rates: {
    title: 'Credit card run-rates, by account',
    hint: 'Names start with the account code, e.g. 2101_3pl_shipping.',
  },
  amazon_weekly_rates: { title: 'Amazon fees, weekly', fixed: true },
  tax_payments: {
    title: 'Tax payments',
    groupTitles: { irs: 'IRS', nj_state: 'NJ State' },
    cols: [{ key: 'date', label: 'Date', kind: 'date' }, money('amount', 'Amount ($)')],
  },
  weekly_revenue_run_rates: { title: 'Weekly revenue run-rates', fixed: true },
  initial_week1_cc_actuals: { title: 'Week-1 credit card actuals, by account code' },
  corporate_accounts: {
    title: 'SERVPRO Corporate customer names',
    list: true,
    hint: 'Customer names treated as SERVPRO Corporate. Add every spelling that appears in Zoho.',
  },
  freight_vendors_exact: {
    title: 'Freight vendors (exact name)',
    list: true,
    hint: 'A purchase order from one of these vendors is booked as freight.',
  },
  freight_reference_substrings: {
    title: 'Freight reference contains',
    list: true,
    hint: 'A purchase order whose reference contains one of these pieces of text is booked as freight.',
  },
  duty_vendors_exact: {
    title: 'Duty vendors (exact name)',
    list: true,
    hint: 'A purchase order from one of these vendors is booked as duty.',
  },
  mappings: {
    title: 'Credit card category map',
    hint: 'Which account each credit card statement category goes to, and when it is paid.',
    cols: [
      { key: 'statement_category', label: 'Statement category', kind: 'text' },
      { key: 'coa_code', label: 'Account code', kind: 'text' },
      { key: 'coa_label', label: 'Account label', kind: 'text' },
      { key: 'payment_method', label: 'Paid by', kind: 'text' },
    ],
  },
  staleness_thresholds_days: {
    title: 'Age limit per data file',
    unit: 'Days',
    kind: 'int',
    fixed: true,
    hint: 'How old each data file may be, in days, before it is flagged as out of date.',
  },
}

export function humanize(k: string): string {
  const s = k.replace(/_/g, ' ')
  return s.charAt(0).toUpperCase() + s.slice(1)
}
export const titleOf = (k: string) => META[k]?.title ?? humanize(k)

const isPlain = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const isScalar = (v: unknown) => typeof v === 'number' || typeof v === 'string'
const isNameList = (v: unknown): v is string[] =>
  Array.isArray(v) && v.length > 0 && v.every((x) => typeof x === 'string')
const isRowList = (v: unknown): v is Record<string, unknown>[] =>
  Array.isArray(v) && v.every((x) => isPlain(x) && Object.values(x).every(isScalar))

let nextId = 1
const leafOf = (v: unknown, kind: LeafKind): Leaf => ({ s: String(v), kind })
const inferKind = (key: string, v: unknown): LeafKind =>
  key === 'month' ? 'month' : /date/i.test(key) ? 'date' : typeof v === 'number' ? 'num' : 'text'

function colsFor(base: Col[] | undefined, items: Record<string, unknown>[]): Col[] {
  const cols = [...(base ?? [])]
  for (const it of items)
    for (const [k, v] of Object.entries(it)) {
      if (!cols.some((c) => c.key === k)) cols.push({ key: k, label: humanize(k), kind: inferKind(k, v) })
    }
  return cols
}
const rowOf = (cols: Col[], it: Record<string, unknown>): Row =>
  Object.fromEntries(cols.map((c) => [c.key, leafOf(it[c.key] ?? '', c.kind)]))
export const blankRow = (cols: Col[]): Row => Object.fromEntries(cols.map((c) => [c.key, { s: '', kind: c.kind }]))

export function toDraft(doc: Doc): Draft {
  const out: Draft = {}
  for (const [k, v] of Object.entries(doc)) {
    const meta = META[k]
    if (typeof v === 'number') out[k] = { t: 'scalar', leaf: leafOf(v, meta?.kind ?? 'num') }
    else if (typeof v === 'string') out[k] = { t: 'scalar', leaf: leafOf(v, /date/i.test(k) ? 'date' : 'text') }
    else if (meta?.list ? Array.isArray(v) && v.every((x) => typeof x === 'string') : isNameList(v))
      out[k] = { t: 'list', items: (v as string[]).map((s) => ({ id: nextId++, leaf: leafOf(s, 'text') })) }
    else if (isRowList(v)) {
      const cols = colsFor(meta?.cols, v)
      out[k] = { t: 'rows', cols, rows: v.map((it) => rowOf(cols, it)) }
    } else if (isPlain(v) && Object.values(v).every((x) => typeof x === 'number')) {
      const kind = meta?.kind ?? 'num'
      out[k] = {
        t: 'map',
        rows: Object.entries(v).map(([key, x]) => ({ id: nextId++, key, v: leafOf(x, kind), isNew: false })),
      }
    } else if (isPlain(v) && Object.values(v).length > 0 && Object.values(v).every(isRowList)) {
      out[k] = {
        t: 'groups',
        groups: Object.entries(v).map(([key, items]) => {
          const cols = colsFor(meta?.cols, items as Record<string, unknown>[])
          return { key, cols, rows: (items as Record<string, unknown>[]).map((it) => rowOf(cols, it)) }
        }),
      }
    } else out[k] = { t: 'other', raw: v }
  }
  return out
}

const numeric = (k: LeafKind) => k === 'num' || k === 'int' || k === 'month'
const leafValue = (l: Leaf) => (numeric(l.kind) ? Number(l.s.trim()) : l.s)
const rowValue = (cols: Col[], r: Row) => Object.fromEntries(cols.map((c) => [c.key, leafValue(r[c.key])]))

export function toDoc(d: Draft): Doc {
  const out: Doc = {}
  for (const [k, e] of Object.entries(d)) {
    if (e.t === 'scalar') out[k] = leafValue(e.leaf)
    else if (e.t === 'list') out[k] = e.items.map((i) => i.leaf.s.trim())
    else if (e.t === 'map') out[k] = Object.fromEntries(e.rows.map((r) => [r.key.trim(), leafValue(r.v)]))
    else if (e.t === 'rows') out[k] = e.rows.map((r) => rowValue(e.cols, r))
    else if (e.t === 'groups')
      out[k] = Object.fromEntries(e.groups.map((g) => [g.key, g.rows.map((r) => rowValue(g.cols, r))]))
    else out[k] = e.raw
  }
  return out
}

export function leafBad(l: Leaf): boolean {
  const s = l.s.trim()
  if (l.kind === 'text') return false
  if (l.kind === 'date') return !/^\d{4}-\d{2}-\d{2}$/.test(s) || Number.isNaN(Date.parse(s))
  const n = Number(s)
  if (s === '' || !Number.isFinite(n)) return true
  if (l.kind === 'int') return !Number.isInteger(n) || n < 0
  if (l.kind === 'month') return !Number.isInteger(n) || n < 1 || n > 12
  return false
}

/** Plain-words problems that block saving, one line per section. */
export function problems(d: Draft): string[] {
  const out: string[] = []
  for (const [k, e] of Object.entries(d)) {
    const t = titleOf(k)
    const rowsBad = (rows: Row[]) => rows.some((r) => Object.values(r).some(leafBad))
    if (e.t === 'scalar' && leafBad(e.leaf)) out.push(`${t}: enter a valid value.`)
    else if (e.t === 'map') {
      if (e.rows.some((r) => leafBad(r.v))) out.push(`${t}: every value must be a valid number.`)
      const names = e.rows.map((r) => r.key.trim())
      if (names.some((n) => n === '')) out.push(`${t}: every row needs a name.`)
      const dup = names.find((n, i) => n !== '' && names.indexOf(n) !== i)
      if (dup) out.push(`${t}: "${dup}" appears twice.`)
    } else if (e.t === 'list') {
      if (e.items.some((i) => i.leaf.s.trim() === '')) out.push(`${t}: remove or fill in the blank entries.`)
    } else if (e.t === 'rows' && rowsBad(e.rows)) out.push(`${t}: fix the highlighted values.`)
    else if (e.t === 'groups' && e.groups.some((g) => rowsBad(g.rows))) out.push(`${t}: fix the highlighted values.`)
  }
  return out
}
