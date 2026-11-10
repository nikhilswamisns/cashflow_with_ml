export type ConfigTable = 'assumptions' | 'corporate_accounts' | 'freight_duty_vendors' | 'cc_category_coa_map'
/** The loans table has its own form and endpoint; the others are raw JSON files. */
export type TableKey = ConfigTable | 'loans'
