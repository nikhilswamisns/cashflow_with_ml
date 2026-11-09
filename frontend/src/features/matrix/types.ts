export interface LineItem {
  label?: string
  raw_ref?: string | null
  amount: number
  confidence?: string | null
}

export interface MatrixCell {
  amount: number
  line_items?: LineItem[]
}

export type RowKind = 'section' | 'group' | 'line' | 'total' | 'opening' | 'gross' | 'ending'

export interface MatrixRow {
  kind: RowKind
  code: string
  label: string
  field: string | null
  values: number[]
}

export interface MatrixWeek {
  week_ending_friday: string
  [field: string]: unknown
}

export interface MatrixData {
  weeks: MatrixWeek[]
  rows: MatrixRow[]
}
