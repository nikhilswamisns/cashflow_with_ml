export type FacilityType = 'credit_line' | 'term_loan'

/** What is saved for one loan or credit line. */
export interface Facility {
  name: string
  type: FacilityType
  limit: number
  drawn: number
  rate_pct: number
  monthly_repayment: number
}

export interface FacilityRow extends Facility {
  headroom: number | null // credit lines only
  over_limit: boolean
  monthly_interest: number
}

export interface Loans {
  facilities: FacilityRow[]
  credit_lines: number
  limit: number
  drawn: number
  headroom: number
  entered_repayments_per_month: number
  entered_interest_per_month: number
  in_forecast: { repayments_per_month: number; interest_per_month: number }
  note: string
}
