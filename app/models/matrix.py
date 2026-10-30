from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from app.models.canonical import DataConfidence

@dataclass(frozen=True)
class LineItem:
    amount: Decimal
    confidence: DataConfidence
    coa_code: str
    label: str
    raw_ref: str | None = None

@dataclass
class WeekCell:
    amount: Decimal = Decimal('0')
    confidence: DataConfidence = DataConfidence.PLACEHOLDER
    line_items: list[LineItem] = field(default_factory=list)

    def add(self, item: LineItem) -> None:
        self.line_items.append(item)
        self.amount += item.amount
        _rank = {DataConfidence.VERIFIED_LIVE: 0, DataConfidence.MANUAL_ENTRY: 1, DataConfidence.FIXED_ASSUMPTION: 2, DataConfidence.PERIODIC_ESTIMATE: 3, DataConfidence.ESTIMATE_BILLS_GAP: 4, DataConfidence.PLACEHOLDER: 5}
        if _rank.get(item.confidence, 5) > _rank.get(self.confidence, 5):
            self.confidence = item.confidence

@dataclass
class WeekSlice:
    week_ending_friday: date
    servpro_corporate: WeekCell = field(default_factory=WeekCell)
    other_resellers: WeekCell = field(default_factory=WeekCell)
    adjustments: WeekCell = field(default_factory=WeekCell)
    discount_given: WeekCell = field(default_factory=WeekCell)
    freight_billed: WeekCell = field(default_factory=WeekCell)
    ar_collection: WeekCell = field(default_factory=WeekCell)
    cogs_standard: WeekCell = field(default_factory=WeekCell)
    inbound_freight: WeekCell = field(default_factory=WeekCell)
    inbound_duty: WeekCell = field(default_factory=WeekCell)
    ops_3pl: WeekCell = field(default_factory=WeekCell)
    ops_amazon_fba: WeekCell = field(default_factory=WeekCell)
    ops_amazon_monthly: WeekCell = field(default_factory=WeekCell)
    ops_disposal: WeekCell = field(default_factory=WeekCell)
    ops_misc: WeekCell = field(default_factory=WeekCell)
    ops_ea_salaries: WeekCell = field(default_factory=WeekCell)
    ops_outbound_freight: WeekCell = field(default_factory=WeekCell)
    ops_seller_fees: WeekCell = field(default_factory=WeekCell)
    ops_storage: WeekCell = field(default_factory=WeekCell)
    mkt_web_redesign: WeekCell = field(default_factory=WeekCell)
    mkt_promo_items: WeekCell = field(default_factory=WeekCell)
    mkt_printing: WeekCell = field(default_factory=WeekCell)
    mkt_misc: WeekCell = field(default_factory=WeekCell)
    mkt_salaries: WeekCell = field(default_factory=WeekCell)
    mkt_graphics: WeekCell = field(default_factory=WeekCell)
    mkt_amazon_ads_admin: WeekCell = field(default_factory=WeekCell)
    mkt_seo: WeekCell = field(default_factory=WeekCell)
    mkt_facebook: WeekCell = field(default_factory=WeekCell)
    mkt_amazon_ads: WeekCell = field(default_factory=WeekCell)
    sell_vehicle: WeekCell = field(default_factory=WeekCell)
    sell_fuel: WeekCell = field(default_factory=WeekCell)
    sell_travel: WeekCell = field(default_factory=WeekCell)
    sell_tradeshow: WeekCell = field(default_factory=WeekCell)
    sell_salaries: WeekCell = field(default_factory=WeekCell)
    sell_reimbursements: WeekCell = field(default_factory=WeekCell)
    sell_medicare: WeekCell = field(default_factory=WeekCell)
    sell_gusto_tax: WeekCell = field(default_factory=WeekCell)
    sell_meals: WeekCell = field(default_factory=WeekCell)
    sell_commission: WeekCell = field(default_factory=WeekCell)
    fin_training: WeekCell = field(default_factory=WeekCell)
    fin_office_tools: WeekCell = field(default_factory=WeekCell)
    fin_rent: WeekCell = field(default_factory=WeekCell)
    fin_legal: WeekCell = field(default_factory=WeekCell)
    fin_interest: WeekCell = field(default_factory=WeekCell)
    fin_insurance: WeekCell = field(default_factory=WeekCell)
    fin_admin_salaries: WeekCell = field(default_factory=WeekCell)
    fin_accounting: WeekCell = field(default_factory=WeekCell)
    fin_bank_fees: WeekCell = field(default_factory=WeekCell)
    it_zoom: WeekCell = field(default_factory=WeekCell)
    it_zoho: WeekCell = field(default_factory=WeekCell)
    it_shopify: WeekCell = field(default_factory=WeekCell)
    it_microsoft: WeekCell = field(default_factory=WeekCell)
    it_godaddy: WeekCell = field(default_factory=WeekCell)
    it_phone: WeekCell = field(default_factory=WeekCell)
    it_development: WeekCell = field(default_factory=WeekCell)
    it_computer: WeekCell = field(default_factory=WeekCell)
    nonop_health_ins: WeekCell = field(default_factory=WeekCell)
    nonop_irs_tax: WeekCell = field(default_factory=WeekCell)
    nonop_nj_tax: WeekCell = field(default_factory=WeekCell)
    nonop_owner_draws: WeekCell = field(default_factory=WeekCell)
    borrowing: WeekCell = field(default_factory=WeekCell)
    loan_repayments: WeekCell = field(default_factory=WeekCell)
    potential_adjustments: WeekCell = field(default_factory=WeekCell)
    sales: Decimal = Decimal('0')
    total_revenue: Decimal = Decimal('0')
    total_cogs: Decimal = Decimal('0')
    total_operations: Decimal = Decimal('0')
    total_marketing: Decimal = Decimal('0')
    total_selling: Decimal = Decimal('0')
    total_finance_admin: Decimal = Decimal('0')
    total_it: Decimal = Decimal('0')
    total_non_operating: Decimal = Decimal('0')
    gross_profit: Decimal = Decimal('0')
    opening_cash: Decimal = Decimal('0')
    ending_cash: Decimal = Decimal('0')
    opening_cash_confidence: DataConfidence = DataConfidence.PLACEHOLDER

@dataclass
class WeeklyMatrix:
    weeks: list[WeekSlice] = field(default_factory=list)
    forecast_start_friday: date | None = None
    window_weeks: int = 52

@dataclass
class ValidationResult:
    passed: bool
    checks: list[ValidationCheck] = field(default_factory=list)

@dataclass
class ValidationCheck:
    name: str
    passed: bool
    message: str
    details: list[str] = field(default_factory=list)
