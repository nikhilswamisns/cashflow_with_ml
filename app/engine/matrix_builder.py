from __future__ import annotations
from datetime import date
from decimal import Decimal
from app.models.canonical import DataConfidence
from app.models.matrix import LineItem, WeekCell, WeekSlice, WeeklyMatrix
_COA_TO_FIELD: dict[str, str] = {'1100.1': 'servpro_corporate', '1100.2': 'other_resellers', '1101': 'adjustments', '1102': 'discount_given', '1103': 'freight_billed', 'AR': 'ar_collection', '3100': 'cogs_standard', '3101': 'inbound_freight', '3102': 'inbound_duty', '2101': 'ops_3pl', '2102': 'ops_amazon_fba', '2103': 'ops_amazon_monthly', '2104': 'ops_disposal', '2105': 'ops_misc', '2106': 'ops_ea_salaries', '2107': 'ops_outbound_freight', '2108': 'ops_seller_fees', '2109': 'ops_storage', '5124': 'mkt_web_redesign', '5121': 'mkt_promo_items', '5122': 'mkt_printing', '5123': 'mkt_misc', '5125': 'mkt_salaries', '5104': 'mkt_graphics', '5101': 'mkt_amazon_ads_admin', '5119': 'mkt_seo', '5108': 'mkt_facebook', '5107': 'mkt_amazon_ads', '4103': 'sell_vehicle', '4105': 'sell_fuel', '4109': 'sell_travel', '5109': 'sell_tradeshow', '4102': 'sell_salaries', '4118': 'sell_reimbursements', '4116': 'sell_medicare', '4115': 'sell_gusto_tax', '4112': 'sell_meals', '4101': 'sell_commission', '6114': 'fin_training', '6111': 'fin_office_tools', '6108': 'fin_rent', '6102': 'fin_legal', '6109': 'fin_interest', '6107': 'fin_insurance', '6101': 'fin_admin_salaries', '6103': 'fin_accounting', '6106': 'fin_bank_fees', '7110': 'it_zoom', '7102': 'it_zoho', '7104': 'it_shopify', '7103': 'it_microsoft', '7106': 'it_godaddy', '7113': 'it_phone', '7111': 'it_development', '7114': 'it_computer', '9901': 'nonop_health_ins', '9902': 'nonop_irs_tax', '9903': 'nonop_nj_tax', '9904': 'nonop_owner_draws', 'BORROW': 'borrowing', 'LOAN_REPAY': 'loan_repayments', 'POTENTIAL': 'potential_adjustments'}

def build_matrix(week_line_items: dict[date, list[LineItem]], opening_cash_amount: Decimal, forecast_start_friday: date, window_weeks: int=52) -> WeeklyMatrix:
    from app.transforms.date_bucketing import weekly_fridays
    fridays = weekly_fridays(forecast_start_friday, window_weeks)
    week_slices: list[WeekSlice] = []
    for friday in fridays:
        ws = WeekSlice(week_ending_friday=friday)
        items = week_line_items.get(friday, [])
        for item in items:
            field_name = _COA_TO_FIELD.get(item.coa_code)
            if field_name is None:
                continue
            cell: WeekCell = getattr(ws, field_name)
            cell.add(item)
        ws.sales = ws.servpro_corporate.amount + ws.other_resellers.amount
        ws.total_revenue = ws.servpro_corporate.amount + ws.other_resellers.amount + ws.adjustments.amount + ws.discount_given.amount + ws.freight_billed.amount + ws.ar_collection.amount
        ws.total_cogs = ws.cogs_standard.amount + ws.inbound_freight.amount + ws.inbound_duty.amount
        ws.total_operations = ws.ops_3pl.amount + ws.ops_amazon_fba.amount + ws.ops_amazon_monthly.amount + ws.ops_disposal.amount + ws.ops_misc.amount + ws.ops_ea_salaries.amount + ws.ops_outbound_freight.amount + ws.ops_seller_fees.amount + ws.ops_storage.amount
        ws.gross_profit = ws.total_revenue - ws.total_cogs - ws.total_operations
        ws.total_marketing = ws.mkt_web_redesign.amount + ws.mkt_promo_items.amount + ws.mkt_printing.amount + ws.mkt_misc.amount + ws.mkt_salaries.amount + ws.mkt_graphics.amount + ws.mkt_amazon_ads_admin.amount + ws.mkt_seo.amount + ws.mkt_facebook.amount + ws.mkt_amazon_ads.amount
        ws.total_selling = ws.sell_vehicle.amount + ws.sell_fuel.amount + ws.sell_travel.amount + ws.sell_tradeshow.amount + ws.sell_salaries.amount + ws.sell_reimbursements.amount + ws.sell_medicare.amount + ws.sell_gusto_tax.amount + ws.sell_meals.amount + ws.sell_commission.amount
        ws.total_finance_admin = ws.fin_training.amount + ws.fin_office_tools.amount + ws.fin_rent.amount + ws.fin_legal.amount + ws.fin_interest.amount + ws.fin_insurance.amount + ws.fin_admin_salaries.amount + ws.fin_accounting.amount + ws.fin_bank_fees.amount
        ws.total_it = ws.it_zoom.amount + ws.it_zoho.amount + ws.it_shopify.amount + ws.it_microsoft.amount + ws.it_godaddy.amount + ws.it_phone.amount + ws.it_development.amount + ws.it_computer.amount
        ws.total_non_operating = ws.nonop_health_ins.amount + ws.nonop_irs_tax.amount + ws.nonop_nj_tax.amount + ws.nonop_owner_draws.amount
        week_slices.append(ws)
    for (i, ws) in enumerate(week_slices):
        if i == 0:
            ws.opening_cash = opening_cash_amount
            ws.opening_cash_confidence = DataConfidence.MANUAL_ENTRY
        else:
            ws.opening_cash = week_slices[i - 1].ending_cash
            ws.opening_cash_confidence = DataConfidence.FIXED_ASSUMPTION
        ws.ending_cash = ws.opening_cash + ws.total_revenue - ws.total_cogs - ws.total_operations - ws.total_marketing - ws.total_selling - ws.total_finance_admin - ws.total_it - ws.total_non_operating + ws.borrowing.amount - ws.loan_repayments.amount + ws.potential_adjustments.amount
    return WeeklyMatrix(weeks=week_slices, forecast_start_friday=forecast_start_friday, window_weeks=window_weeks)
