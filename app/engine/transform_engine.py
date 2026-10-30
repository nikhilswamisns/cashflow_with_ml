from __future__ import annotations
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from app.config.loader import load_assumptions
from app.models.canonical import CanonicalRecord, DataConfidence, safe_parse_date
from app.models.matrix import LineItem
from app.transforms.bills_gap import build_bills_index, cogs_amount_and_date
from app.transforms.cogs_routing import cogs_category, po_due_date
from app.transforms.date_bucketing import bucket_ar_to_week_ending_friday, bucket_po_to_week_ending_friday, weekly_fridays
from app.transforms.revenue_routing import is_servpro_corporate, servpro_corporate_cash_in_date
CONFIG_DIR = Path(__file__).parent.parent / 'config'

class TransformException:

    def __init__(self, source: str, record_ref: str, reason: str):
        self.source = source
        self.record_ref = record_ref
        self.reason = reason

    def __str__(self) -> str:
        return f'[TransformException] {self.source} | {self.record_ref} | {self.reason}'

def _first_friday_of_month(year: int, month: int) -> date:
    d = date(year, month, 1)
    return d + timedelta(days=(4 - d.weekday()) % 7)

def _second_friday_of_month(year: int, month: int) -> date:
    return _first_friday_of_month(year, month) + timedelta(weeks=1)

def _third_friday_of_month(year: int, month: int) -> date:
    return _first_friday_of_month(year, month) + timedelta(weeks=2)

def _fourth_friday_of_month(year: int, month: int) -> date:
    return _first_friday_of_month(year, month) + timedelta(weeks=3)

def _last_friday_of_month(year: int, month: int) -> date:
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    d = date(year, month, last_day)
    return d - timedelta(days=(d.weekday() - 4) % 7)

def _cc_payment_friday(year: int, month: int) -> date:
    d = date(year, month, 15)
    return d + timedelta(days=(4 - d.weekday()) % 7)

def _tax_payment_friday(target: date) -> date:
    return target - timedelta(days=(target.weekday() - 4) % 7)

class TransformEngine:

    def __init__(self, records: list[CanonicalRecord], forecast_start_friday: date, window_weeks: int | None=None):
        self.records = records
        self.forecast_start_friday = forecast_start_friday
        self.cfg = load_assumptions()
        self.window_weeks = window_weeks or self.cfg.rolling_window_weeks
        self.fridays = weekly_fridays(forecast_start_friday, self.window_weeks)
        self.exceptions: list[TransformException] = []
        self._by_source: dict[str, list[CanonicalRecord]] = defaultdict(list)
        for r in records:
            self._by_source[r.source].append(r)

    def run(self) -> dict[date, list[LineItem]]:
        result: dict[date, list[LineItem]] = {f: [] for f in self.fridays}
        self._transform_ar_invoices(result)
        self._transform_sales_orders(result)
        self._transform_revenue_run_rates(result)
        self._transform_purchase_orders(result)
        self._transform_bills_direct(result)
        self._transform_biweekly_payroll(result)
        self._transform_cc_expenses(result)
        self._transform_amazon_weekly(result)
        self._transform_monthly_and_annual_expenses(result)
        self._transform_tax_payments(result)
        self._transform_week1_cc_actuals(result)
        return result

    def _transform_ar_invoices(self, result: dict[date, list[LineItem]]) -> None:
        invoices = self._by_source.get('ar_unpaid_invoices', [])
        ACTIONABLE_STATUSES = {'open', 'sent', 'overdue', 'partiallypaid', 'partially_paid'}
        for inv in invoices:
            payload = inv.payload
            customer = payload.get('customer_name', '')
            status = (payload.get('status', '') or '').lower().replace(' ', '')
            due_raw = payload.get('due_date')
            balance = Decimal(str(payload.get('balance', 0)))
            if status not in ACTIONABLE_STATUSES:
                continue
            if balance <= 0:
                continue
            if not due_raw:
                self.exceptions.append(TransformException('ar_unpaid_invoices', inv.raw_ref or 'unknown', 'Missing due_date — cannot bucket.'))
                continue
            due_date = safe_parse_date(due_raw)
            if is_servpro_corporate(customer):
                coa_code = '1100.1'
                label = 'SERVPRO Corporate'
            else:
                coa_code = 'AR'
                label = 'A/R Collection'
            cash_in_week = bucket_ar_to_week_ending_friday(due_date, self.forecast_start_friday)
            if cash_in_week not in result:
                result[cash_in_week] = []
            result[cash_in_week].append(LineItem(amount=balance, confidence=inv.confidence, coa_code=coa_code, label=label, raw_ref=inv.raw_ref))

    def _transform_sales_orders(self, result: dict[date, list[LineItem]]) -> None:
        sos = self._by_source.get('confirmed_sales_orders', [])
        invoices = self._by_source.get('ar_unpaid_invoices', [])
        ACTIONABLE_SO_STATUSES = {'confirmed', 'open', 'partially_invoiced', 'partiallyinvoiced'}
        invoice_due_by_number: dict[str, date] = {}
        for inv in invoices:
            inv_num = inv.payload.get('invoice_number', '')
            due_raw = inv.payload.get('due_date')
            if inv_num and due_raw:
                invoice_due_by_number[inv_num] = safe_parse_date(due_raw)
        for so in sos:
            payload = so.payload
            customer = payload.get('customer_name', '')
            status = (payload.get('status') or payload.get('order_status') or '').lower().replace(' ', '_')
            if status not in ACTIONABLE_SO_STATUSES:
                continue
            if not is_servpro_corporate(customer):
                continue
            total = Decimal(str(payload.get('total', 0) or 0))
            if total <= 0:
                continue
            linked_inv_num = payload.get('linked_invoice_number')
            if linked_inv_num and linked_inv_num in invoice_due_by_number:
                cash_in_date = invoice_due_by_number[linked_inv_num]
                note = 'SERVPRO Corporate — invoice due_date supersedes SO estimate'
            else:
                ship_raw = payload.get('expected_shipment_date')
                if not ship_raw:
                    self.exceptions.append(TransformException('confirmed_sales_orders', so.raw_ref or 'unknown', 'SERVPRO Corporate SO has no expected_shipment_date and no linked invoice.'))
                    continue
                ship_date = safe_parse_date(ship_raw)
                cash_in_date = servpro_corporate_cash_in_date(ship_date)
                note = 'SERVPRO Corporate — Net-45 from expected_shipment_date'
            cash_in_week = bucket_ar_to_week_ending_friday(cash_in_date, self.forecast_start_friday)
            if cash_in_week not in result:
                result[cash_in_week] = []
            result[cash_in_week].append(LineItem(amount=total, confidence=so.confidence, coa_code='1100.1', label='SERVPRO Corporate Net-45', raw_ref=f'{so.raw_ref} | {note}'))

    def _transform_revenue_run_rates(self, result: dict[date, list[LineItem]]) -> None:
        rates = self.cfg.weekly_revenue_run_rates
        for friday in self.fridays:
            result[friday].extend([LineItem(amount=rates.baseline_resellers, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='1100.2', label='Other Resellers', raw_ref='Sales by Item 6-mo avg (Feb–Jul 2026) ÷ 26 wks'), LineItem(amount=rates.baseline_adjustments, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='1101', label='Adjustments', raw_ref='P&L 7-mo annualized ÷ 52 wks'), LineItem(amount=rates.baseline_discount, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='1102', label='Discount Given', raw_ref='P&L 7-mo annualized ÷ 52 wks'), LineItem(amount=rates.baseline_freight_billed, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='1103', label='Freight Billed', raw_ref='P&L 7-mo annualized ÷ 52 wks')])

    def _transform_purchase_orders(self, result: dict[date, list[LineItem]]) -> None:
        pos = self._by_source.get('purchase_orders', [])
        bills = self._by_source.get('partially_paid_bills', [])
        bills_index = build_bills_index(bills)
        for po in pos:
            payload = po.payload
            po_num = payload.get('purchaseorder_number', '')
            po_status = (payload.get('order_status') or payload.get('status') or '').lower()
            total = Decimal(str(payload.get('total') or 0))
            if po_status in ('cancelled', 'void'):
                continue
            category = cogs_category(payload)
            coa_code = category.split('_')[0]
            label = {'3100_cogs_standard': 'Cost of Goods Sold', '3101_inbound_freight': 'Inbound Freight', '3102_inbound_duty': "Inbound Duty & Gov't Fees"}.get(category, 'Cost of Goods Sold')
            if po_num in bills_index:
                bill = bills_index[po_num]
                amt = bill.balance_due
                due_date = bill.due_date
                confidence = DataConfidence.VERIFIED_LIVE
                raw_ref = f'{po.raw_ref} (reconciled against bill {bill.status})'
            elif po_status in ('open', 'issued', 'draft'):
                amt = total
                try:
                    due_date = po_due_date(payload)
                except ValueError:
                    self.exceptions.append(TransformException('purchase_orders', po.raw_ref or 'unknown', 'Cannot compute due_date — neither delivery_date nor date is set.'))
                    continue
                confidence = DataConfidence.VERIFIED_LIVE
                raw_ref = po.raw_ref
            else:
                continue
            if amt <= 0:
                continue
            cash_out_week = bucket_po_to_week_ending_friday(due_date, self.forecast_start_friday)
            if cash_out_week not in result:
                result[cash_out_week] = []
            result[cash_out_week].append(LineItem(amount=amt, confidence=confidence, coa_code=coa_code, label=label, raw_ref=raw_ref))

    def _transform_bills_direct(self, result: dict[date, list[LineItem]]) -> None:
        bills = self._by_source.get('partially_paid_bills', [])
        pos = self._by_source.get('purchase_orders', [])
        open_po_numbers: set[str] = set()
        for po in pos:
            status = (po.payload.get('order_status') or po.payload.get('status') or '').lower()
            if status in ('open', 'issued', 'draft'):
                open_po_numbers.add(po.payload.get('purchaseorder_number', ''))
        for bill in bills:
            payload = bill.payload
            bill_num = payload.get('bill_number', '')
            linked_po = payload.get('linked_po') or ''
            if linked_po and linked_po in open_po_numbers:
                continue
            vendor = (payload.get('vendor') or '').strip()
            balance = Decimal(str(payload.get('balance_due', 0) or 0))
            due_raw = payload.get('due_date')
            if balance <= 0 or not due_raw:
                continue
            from app.models.canonical import safe_parse_date
            due_date = safe_parse_date(due_raw)
            coa_override = payload.get('_coa_override')
            if coa_override:
                coa_code = coa_override.split('_')[0]
                label = {'3100_cogs_standard': 'Cost of Goods Sold', '3101_inbound_freight': 'Inbound Freight', '3102_inbound_duty': "Inbound Duty & Gov't Fees"}.get(coa_override, 'Cost of Goods Sold')
            else:
                vendor_lower = vendor.lower()
                if 'irs' in vendor_lower or 'internal revenue' in vendor_lower:
                    coa_code, label = '9902', 'IRS Taxes'
                elif 'nj' in vendor_lower or 'new jersey' in vendor_lower:
                    coa_code, label = '9903', 'NJ State Tax'
                else:
                    category = cogs_category({'vendor_name': vendor, 'reference_number': linked_po})
                    coa_code = category.split('_')[0]
                    label = {'3100_cogs_standard': 'Cost of Goods Sold', '3101_inbound_freight': 'Inbound Freight', '3102_inbound_duty': "Inbound Duty & Gov't Fees"}.get(category, 'Cost of Goods Sold')
            cash_out_week = bucket_po_to_week_ending_friday(due_date, self.forecast_start_friday)
            if cash_out_week not in result:
                result[cash_out_week] = []
            result[cash_out_week].append(LineItem(amount=balance, confidence=DataConfidence.VERIFIED_LIVE, coa_code=coa_code, label=label, raw_ref=f'Bill {bill_num} ({vendor})'))

    def _transform_biweekly_payroll(self, result: dict[date, list[LineItem]]) -> None:
        cfg = self.cfg
        anchor = cfg.biweekly_pay_anchor_date
        bi_sal = cfg.biweekly_salaries
        for friday in self.fridays:
            days_diff = (friday - anchor).days
            if days_diff % 14 != 0 or days_diff < 0:
                continue
            result[friday].extend([LineItem(amount=bi_sal.ops_ea_salary, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='2106', label='Operations/EA Salaries', raw_ref='Fixed $1,923 biweekly — NewAddtnl Assumptions'), LineItem(amount=bi_sal.admin_salaries, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='6101', label='Admin Salaries & Benefits', raw_ref='Fixed $1,440 biweekly — Expense Assumptions'), LineItem(amount=bi_sal.marketing_salaries, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='5125', label='Marketing Salaries', raw_ref='Fixed $1,000 biweekly — Expense Assumptions'), LineItem(amount=bi_sal.sales_salaries, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='4102', label='Sales Salaries', raw_ref='Fixed $12,708.34 biweekly ($10,208.34 base + $2,500 addl)'), LineItem(amount=bi_sal.graphics_photography, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='5104', label='Graphics/Video/Photography', raw_ref='Fixed $320 biweekly — Expense Assumptions'), LineItem(amount=bi_sal.amazon_ads_admin, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='5101', label='Amazon Ads Admin', raw_ref='Fixed $550 biweekly — Expense Assumptions'), LineItem(amount=bi_sal.gusto_reimbursements, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='4118', label='Reimbursements (Gusto)', raw_ref='avg/mo ÷2 ×1.5 — Expense Assumptions'), LineItem(amount=bi_sal.medicare, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='4116', label='Medicare', raw_ref='avg/mo ÷2 ×1.5 — Expense Assumptions'), LineItem(amount=bi_sal.gusto_tax, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='4115', label='Tax (Gusto)', raw_ref='avg/mo ÷2 ×1.5 — Expense Assumptions'), LineItem(amount=bi_sal.amazon_advertising, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='5107', label='Amazon Advertising', raw_ref='avg/mo ÷2 biweekly — Expense Assumptions')])

    def _transform_cc_expenses(self, result: dict[date, list[LineItem]]) -> None:
        cfg = self.cfg
        cc_map = cfg.cc_run_rates
        cc_items = [('2101', '3PL Shipping Services', '2101_3pl_shipping'), ('2104', 'Disposal', '2104_disposal'), ('2105', 'Misc Operations Expenses', '2105_misc_operations'), ('2109', 'Storage', '2109_storage'), ('5108', 'Facebook Advertising', '5108_facebook_advertising'), ('5119', 'SEO Ad Spend', '5119_seo_ad_spend'), ('5121', 'Promotional Items', '5121_promotional_items'), ('5122', 'Printing/Mailings/Lists', '5122_printing_mailings'), ('5123', 'Miscellaneous Marketing', '5123_misc_marketing'), ('4105', 'Fuel', '4105_fuel'), ('4109', 'Travel Expense', '4109_travel_expense'), ('4112', 'Meals & Entertainment', '4112_meals_entertainment'), ('5109', 'Tradeshow Marketing', '5109_tradeshow_marketing'), ('6102', "Legal Services/Gov't Filings", '6102_legal_services'), ('6106', 'Bank/CC/PayPal Fees', '6106_bank_cc_fees'), ('6107', 'Business Insurance', '6107_business_insurance'), ('6114', 'Training', '6114_training'), ('7102', 'Zoho', '7102_zoho'), ('7103', 'Microsoft', '7103_microsoft'), ('7104', 'Shopify', '7104_shopify'), ('7106', 'Go Daddy', '7106_go_daddy'), ('7110', 'Zoom', '7110_zoom'), ('7113', 'Phone', '7113_phone'), ('7114', 'Computer/Internet', '7114_computer_internet'), ('9901', 'Health Insurance', '9901_health_insurance')]
        all_months = {(f.year, f.month) for f in self.fridays}
        cc_fridays = {_cc_payment_friday(y, m) for (y, m) in all_months}
        for friday in self.fridays:
            if friday not in cc_fridays:
                continue
            for (coa_code, label, key) in cc_items:
                amount_raw = cc_map.get(key, 0)
                amount = Decimal(str(amount_raw))
                if amount == 0:
                    continue
                result[friday].append(LineItem(amount=amount, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code=coa_code, label=label, raw_ref='CC run-rate (Expense Assumptions)'))

    def _transform_amazon_weekly(self, result: dict[date, list[LineItem]]) -> None:
        rates = self.cfg.amazon_weekly_rates
        for friday in self.fridays:
            result[friday].extend([LineItem(amount=rates.fba_fees, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='2102', label='Amazon FBA Fees', raw_ref='avg/wk 6-mo ÷ 26 wks'), LineItem(amount=rates.amazon_monthly_fee, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='2103', label='Amazon Monthly Fee', raw_ref='Fixed $40/mo ÷ 4 wks = $10/wk')])
            if friday != self.forecast_start_friday:
                result[friday].append(LineItem(amount=rates.seller_fees, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='2108', label='Seller Fees', raw_ref='avg/wk 6-mo ÷ 26 wks'))

    def _transform_monthly_and_annual_expenses(self, result: dict[date, list[LineItem]]) -> None:
        cfg = self.cfg
        all_months = {(f.year, f.month) for f in self.fridays}
        first_fridays = {_first_friday_of_month(y, m) for (y, m) in all_months}
        for friday in self.fridays:
            if friday in first_fridays:
                veh = Decimal(str(cfg.monthly_first_friday_expenses.get('vehicle_expense', 3029.32)))
                obf = Decimal(str(cfg.monthly_first_friday_expenses.get('outbound_freight', 10448.195)))
                rent = Decimal(str(cfg.monthly_first_friday_expenses.get('office_rent', 5000.0)))
                od = Decimal(str(cfg.monthly_first_friday_expenses.get('owner_disbursements', 343.709166667)))
                result[friday].extend([LineItem(amount=veh, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='4103', label='Vehicle Expense', raw_ref='Fixed $3,029.32 1st Friday — Expense Assumptions'), LineItem(amount=obf, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='2107', label='Outbound Freight Costs', raw_ref='12-mo avg 1st Friday — Expense Assumptions'), LineItem(amount=od, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='9904', label='Owner Disbursements', raw_ref='12-mo avg 1st Friday — Expense Assumptions')])
                if friday >= date(2026, 9, 1):
                    result[friday].append(LineItem(amount=rent, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='6108', label='Office Rent/Cleaning/Utilities', raw_ref='Fixed $5,000/mo from Sep 2026'))
        for (y, m) in all_months:
            if m in (6, 12):
                fri = _first_friday_of_month(y, m)
                if fri in result:
                    result[fri].append(LineItem(amount=Decimal('6250.00'), confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='6109', label='Interest', raw_ref='Fixed $6,250 semi-annual interest (Jun/Dec 1st Fri)'))
        second_fridays = {_second_friday_of_month(y, m) for (y, m) in all_months}
        comm_amt = Decimal(str(cfg.monthly_second_friday_expenses.get('commission', 2929.0475)))
        for friday in self.fridays:
            if friday in second_fridays:
                result[friday].append(LineItem(amount=comm_amt, confidence=DataConfidence.PERIODIC_ESTIMATE, coa_code='4101', label='Commission', raw_ref='6-mo avg 2nd Friday — Expense Assumptions'))
        third_fridays = {_third_friday_of_month(y, m) for (y, m) in all_months}
        int_3rd = Decimal(str(cfg.monthly_third_friday_expenses.get('interest', 250.0)))
        for friday in self.fridays:
            if friday in third_fridays:
                result[friday].append(LineItem(amount=int_3rd, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='6109', label='Interest', raw_ref='Fixed $250 3rd Friday — Assumptions & Rules'))
        fourth_fridays = {_fourth_friday_of_month(y, m) for (y, m) in all_months}
        int_4th = Decimal(str(cfg.monthly_fourth_friday_expenses.get('interest', 1000.0)))
        for friday in self.fridays:
            if friday in fourth_fridays:
                result[friday].append(LineItem(amount=int_4th, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='6109', label='Interest', raw_ref='Fixed $1,000 4th Friday — Assumptions & Rules'))
        for entry in cfg.annual_fourth_friday_expenses:
            for (y, m) in all_months:
                if m == entry.month:
                    fri = _fourth_friday_of_month(y, m)
                    if fri in result:
                        result[fri].append(LineItem(amount=entry.amount, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code=entry.coa_code, label=entry.label, raw_ref=f'Annual {entry.label} in month {entry.month}'))
        last_fridays = {_last_friday_of_month(y, m) for (y, m) in all_months}
        loan_amt = Decimal(str(cfg.monthly_last_friday_expenses.get('loan_repayments', 13333.0)))
        for friday in self.fridays:
            if friday in last_fridays:
                result[friday].append(LineItem(amount=loan_amt, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='LOAN_REPAY', label='Loan Repayments', raw_ref='Fixed $13,333 last Friday — Assumptions & Rules'))

    def _transform_tax_payments(self, result: dict[date, list[LineItem]]) -> None:
        cfg = self.cfg
        for t in cfg.tax_payments_irs:
            fri = _tax_payment_friday(t.date)
            if fri in result:
                result[fri].append(LineItem(amount=t.amount, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='9902', label='IRS Taxes', raw_ref=f'IRS Tax due {t.date}'))
        for t in cfg.tax_payments_nj:
            fri = _tax_payment_friday(t.date)
            if fri in result:
                result[fri].append(LineItem(amount=t.amount, confidence=DataConfidence.FIXED_ASSUMPTION, coa_code='9903', label='NJ State Tax', raw_ref=f'NJ State Tax due {t.date}'))

    def _transform_week1_cc_actuals(self, result: dict[date, list[LineItem]]) -> None:
        cc_records = self._by_source.get('credit_card_statement', [])
        if cc_records:
            for r in cc_records:
                payload = r.payload
                coa = payload.get('coa_code') or '2105'
                amt = Decimal(str(payload.get('amount', 0)))
                lbl = payload.get('category') or 'Credit Card Charge'
                if amt != 0 and self.forecast_start_friday in result:
                    result[self.forecast_start_friday].append(LineItem(amount=amt, confidence=DataConfidence.VERIFIED_LIVE, coa_code=coa, label=lbl, raw_ref=r.raw_ref or 'Uploaded CC Statement'))
        else:
            week1 = self.forecast_start_friday
            if week1 in result:
                for (coa, amt) in self.cfg.initial_week1_cc_actuals.items():
                    result[week1].append(LineItem(amount=Decimal(str(amt)), confidence=DataConfidence.MANUAL_ENTRY, coa_code=coa, label='CC Statement Actual', raw_ref='8/15/26 Statement Actuals — Cash Flow Forecast 2026-08-14.xlsx'))
