from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from app.models.canonical import safe_parse_date
CONFIG_DIR = Path(__file__).parent

def _load(filename: str) -> dict:
    p = CONFIG_DIR / filename
    with open(p, encoding='utf-8') as f:
        return json.load(f)

@dataclass
class FreightDutyConfig:
    freight_vendors_exact: list[str]
    freight_reference_substrings: list[str]
    duty_vendors_exact: list[str]

@dataclass
class CCMapping:
    statement_category: str
    coa_code: str
    coa_label: str
    payment_method: str

@dataclass
class TaxEntry:
    date: date
    amount: Decimal

@dataclass
class AnnualExpenseEntry:
    month: int
    amount: Decimal
    coa_code: str
    label: str

@dataclass
class BiweeklySalaries:
    ops_ea_salary: Decimal
    admin_salaries: Decimal
    marketing_salaries: Decimal
    sales_salaries: Decimal
    graphics_photography: Decimal
    amazon_ads_admin: Decimal
    gusto_reimbursements: Decimal
    medicare: Decimal
    gusto_tax: Decimal
    amazon_advertising: Decimal

@dataclass
class AmazonWeeklyRates:
    fba_fees: Decimal
    seller_fees: Decimal
    amazon_monthly_fee: Decimal

@dataclass
class WeeklyRevenueRunRates:
    baseline_resellers: Decimal
    baseline_adjustments: Decimal
    baseline_discount: Decimal
    baseline_freight_billed: Decimal

@dataclass
class COALineItem:
    coa_code: str
    label: str
    row: int

@dataclass
class COASection:
    section_name: str
    row_range: tuple[int, int]
    line_items: list[COALineItem]

@dataclass
class COARoutingConfig:
    sections: dict[str, COASection]
    all_codes: set[str] = field(default_factory=set)

    def resolve(self, coa_code: str) -> COALineItem | None:
        for section in self.sections.values():
            for item in section.line_items:
                if item.coa_code == coa_code:
                    return item
        return None

@dataclass
class CustomerConfig:
    customer_name: str
    display_label: str
    coa_code: str
    treatment: str
    is_amazon: bool = False
    is_servpro_corporate: bool = False
    notes: str | None = None

@dataclass
class VendorConfig:
    vendor_name: str
    coa_code: str
    category_label: str
    classification_rule: str
    notes: str | None = None

@dataclass
class AssumptionsConfig:
    rolling_window_weeks: int
    ar_days_convention: int
    servpro_corporate_net_days: int
    po_default_payment_terms_days: int
    vendor_payment_terms_days: dict[str, int]
    cc_payment_day_of_month: int
    biweekly_pay_anchor_date: date
    biweekly_salaries: BiweeklySalaries
    monthly_first_friday_expenses: dict[str, float]
    monthly_second_friday_expenses: dict[str, float]
    monthly_third_friday_expenses: dict[str, float]
    monthly_fourth_friday_expenses: dict[str, float]
    monthly_last_friday_expenses: dict[str, float]
    annual_fourth_friday_expenses: list[AnnualExpenseEntry]
    cc_run_rates: dict[str, float]
    amazon_weekly_rates: AmazonWeeklyRates
    tax_payments_irs: list[TaxEntry]
    tax_payments_nj: list[TaxEntry]
    weekly_revenue_run_rates: WeeklyRevenueRunRates
    initial_week1_cc_actuals: dict[str, float]
    staleness_thresholds_days: dict[str, int]
_cache: dict[str, object] = {}

def load_assumptions() -> AssumptionsConfig:
    if 'assumptions' not in _cache:
        raw = _load('assumptions.json')
        bi_raw = raw.get('biweekly_salaries', {})
        amz_raw = raw.get('amazon_weekly_rates', {})
        tax_raw = raw.get('tax_payments', {})
        rev_raw = raw.get('weekly_revenue_run_rates', {})
        _cache['assumptions'] = AssumptionsConfig(rolling_window_weeks=raw.get('rolling_window_weeks', 52), ar_days_convention=raw.get('ar_days_convention', 21), servpro_corporate_net_days=raw.get('servpro_corporate_net_days', 45), po_default_payment_terms_days=raw.get('po_default_payment_terms_days', 30), vendor_payment_terms_days=raw.get('vendor_payment_terms_days', {}), cc_payment_day_of_month=raw.get('cc_payment_day_of_month', 15), biweekly_pay_anchor_date=safe_parse_date(raw.get('biweekly_pay_anchor_date', '2026-08-21')), biweekly_salaries=BiweeklySalaries(ops_ea_salary=Decimal(str(bi_raw.get('ops_ea_salary', '1923.00'))), admin_salaries=Decimal(str(bi_raw.get('admin_salaries', '1440.00'))), marketing_salaries=Decimal(str(bi_raw.get('marketing_salaries', '1000.00'))), sales_salaries=Decimal(str(bi_raw.get('sales_salaries', '12708.3366666667'))), graphics_photography=Decimal(str(bi_raw.get('graphics_photography', '320.00'))), amazon_ads_admin=Decimal(str(bi_raw.get('amazon_ads_admin', '550.00'))), gusto_reimbursements=Decimal(str(bi_raw.get('gusto_reimbursements', '811.3725'))), medicare=Decimal(str(bi_raw.get('medicare', '144.78125'))), gusto_tax=Decimal(str(bi_raw.get('gusto_tax', '574.8925'))), amazon_advertising=Decimal(str(bi_raw.get('amazon_advertising', '5577.64083333333')))), monthly_first_friday_expenses=raw.get('monthly_first_friday_expenses', {}), monthly_second_friday_expenses=raw.get('monthly_second_friday_expenses', {}), monthly_third_friday_expenses=raw.get('monthly_third_friday_expenses', {}), monthly_fourth_friday_expenses=raw.get('monthly_fourth_friday_expenses', {}), monthly_last_friday_expenses=raw.get('monthly_last_friday_expenses', {}), annual_fourth_friday_expenses=[AnnualExpenseEntry(month=e['month'], amount=Decimal(str(e['amount'])), coa_code=e['coa_code'], label=e['label']) for e in raw.get('annual_fourth_friday_expenses', [])], cc_run_rates=raw.get('cc_run_rates', {}), amazon_weekly_rates=AmazonWeeklyRates(fba_fees=Decimal(str(amz_raw.get('fba_fees', '2750.16076923'))), seller_fees=Decimal(str(amz_raw.get('seller_fees', '2010.83192308'))), amazon_monthly_fee=Decimal(str(amz_raw.get('amazon_monthly_fee', '10.00')))), tax_payments_irs=[TaxEntry(date=safe_parse_date(t['date']), amount=Decimal(str(t['amount']))) for t in tax_raw.get('irs', [])], tax_payments_nj=[TaxEntry(date=safe_parse_date(t['date']), amount=Decimal(str(t['amount']))) for t in tax_raw.get('nj_state', [])], weekly_revenue_run_rates=WeeklyRevenueRunRates(baseline_resellers=Decimal(str(rev_raw.get('baseline_resellers', '42185.8096153846'))), baseline_adjustments=Decimal(str(rev_raw.get('baseline_adjustments', '734.948846153846'))), baseline_discount=Decimal(str(rev_raw.get('baseline_discount', '-558.662692307692'))), baseline_freight_billed=Decimal(str(rev_raw.get('baseline_freight_billed', '361.131346153846')))), initial_week1_cc_actuals=raw.get('initial_week1_cc_actuals', {}), staleness_thresholds_days=raw.get('staleness_thresholds_days', {}))
    return _cache['assumptions']

def load_corporate_accounts() -> list[str]:
    if 'corporate_accounts' not in _cache:
        raw = _load('corporate_accounts.json')
        _cache['corporate_accounts'] = raw.get('corporate_accounts', [])
    return _cache['corporate_accounts']

def load_customers() -> list[CustomerConfig]:
    if 'customers' not in _cache:
        raw = _load('customers.json')
        _cache['customers'] = [CustomerConfig(customer_name=c['customer_name'], display_label=c['display_label'], coa_code=c['coa_code'], treatment=c['treatment'], is_amazon=c.get('is_amazon', False), is_servpro_corporate=c.get('is_servpro_corporate', False), notes=c.get('notes')) for c in raw['customers']]
    return _cache['customers']

def load_vendors() -> list[VendorConfig]:
    if 'vendors' not in _cache:
        raw = _load('vendors.json')
        _cache['vendors'] = [VendorConfig(vendor_name=v['vendor_name'], coa_code=v['coa_code'], category_label=v['category_label'], classification_rule=v['classification_rule'], notes=v.get('notes')) for v in raw['vendors']]
    return _cache['vendors']

def load_freight_duty() -> FreightDutyConfig:
    if 'freight_duty' not in _cache:
        raw = _load('freight_duty_vendors.json')
        _cache['freight_duty'] = FreightDutyConfig(freight_vendors_exact=raw['freight_vendors_exact'], freight_reference_substrings=raw['freight_reference_substrings'], duty_vendors_exact=raw['duty_vendors_exact'])
    return _cache['freight_duty']

def load_cc_mappings() -> list[CCMapping]:
    if 'cc_mappings' not in _cache:
        raw = _load('cc_category_coa_map.json')
        _cache['cc_mappings'] = [CCMapping(**m) for m in raw['mappings']]
    return _cache['cc_mappings']

def load_coa_routing() -> COARoutingConfig:
    if 'coa_routing' not in _cache:
        raw = _load('coa_routing.json')
        sections = {}
        all_codes: set[str] = set()
        for (section_name, section_raw) in raw['sections'].items():
            items = [COALineItem(coa_code=li['coa_code'], label=li['label'], row=li['row']) for li in section_raw.get('line_items', [])]
            for item in items:
                all_codes.add(item.coa_code)
            row_range_raw = section_raw['row_range']
            sections[section_name] = COASection(section_name=section_name, row_range=(row_range_raw[0], row_range_raw[1]), line_items=items)
        _cache['coa_routing'] = COARoutingConfig(sections=sections, all_codes=all_codes)
    return _cache['coa_routing']

def invalidate_cache() -> None:
    _cache.clear()
