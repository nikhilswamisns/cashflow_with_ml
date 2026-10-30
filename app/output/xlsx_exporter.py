from __future__ import annotations
import io
from datetime import date
from decimal import Decimal
from pathlib import Path
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from app.models.matrix import WeeklyMatrix, WeekSlice
TEMPLATE_PATHS = [Path(__file__).parent.parent / 'templates' / 'Cash_Flow_Forecast_Template.xlsx', Path(__file__).parent.parent.parent / 'Cash_Flow_Forecast_2026-08-14.xlsx']
HEADER_FILL = PatternFill('solid', fgColor='1F4E79')
HEADER_FONT = Font(color='FFFFFF', bold=True, name='Calibri', size=10)
BOLD_FONT = Font(bold=True)
INPUT_ROWS = {'opening_cash': 4, 'servpro_corporate': 8, 'other_resellers': 9, 'adjustments': 10, 'discount_given': 11, 'freight_billed': 12, 'ar_collection': 13, 'cogs_standard': 17, 'inbound_freight': 18, 'inbound_duty': 19, 'ops_3pl': 23, 'ops_amazon_fba': 24, 'ops_amazon_monthly': 25, 'ops_disposal': 26, 'ops_misc': 27, 'ops_ea_salaries': 28, 'ops_outbound_freight': 29, 'ops_seller_fees': 30, 'ops_storage': 31, 'mkt_web_redesign': 37, 'mkt_promo_items': 38, 'mkt_printing': 39, 'mkt_misc': 40, 'mkt_salaries': 41, 'mkt_graphics': 42, 'mkt_amazon_ads_admin': 43, 'mkt_seo': 44, 'mkt_facebook': 45, 'mkt_amazon_ads': 46, 'sell_vehicle': 50, 'sell_fuel': 51, 'sell_travel': 52, 'sell_tradeshow': 53, 'sell_salaries': 54, 'sell_reimbursements': 55, 'sell_medicare': 56, 'sell_gusto_tax': 57, 'sell_meals': 58, 'sell_commission': 59, 'fin_training': 63, 'fin_office_tools': 64, 'fin_rent': 65, 'fin_legal': 66, 'fin_interest': 67, 'fin_insurance': 68, 'fin_admin_salaries': 69, 'fin_accounting': 70, 'fin_bank_fees': 71, 'it_zoom': 75, 'it_zoho': 76, 'it_shopify': 77, 'it_microsoft': 78, 'it_godaddy': 79, 'it_phone': 80, 'it_development': 81, 'it_computer': 82, 'nonop_health_ins': 86, 'nonop_irs_tax': 87, 'nonop_nj_tax': 88, 'nonop_owner_draws': 89, 'borrowing': 93, 'loan_repayments': 94, 'potential_adjustments': 95}
COMPUTED_ROWS = {'total_revenue': 14, 'total_cogs': 20, 'total_operations': 32, 'gross_profit': 34, 'total_marketing': 47, 'total_selling': 60, 'total_finance_admin': 72, 'total_it': 83, 'total_non_operating': 90, 'ending_cash': 97}
ROW_MAP = {**INPUT_ROWS, **COMPUTED_ROWS}

class XLSXExporter:

    def __init__(self, matrix: WeeklyMatrix):
        self.matrix = matrix
        self.wb: Workbook | None = None
        for p in TEMPLATE_PATHS:
            if p.exists():
                try:
                    self.wb = openpyxl.load_workbook(p)
                    break
                except Exception:
                    pass
        if self.wb is None:
            self.wb = Workbook()
            self.wb.remove(self.wb.active)

    def export(self) -> bytes:
        if 'Cash Flow Model' in self.wb.sheetnames:
            self._update_templated_workbook()
        else:
            self._build_from_scratch()
        buf = io.BytesIO()
        self.wb.save(buf)
        buf.seek(0)
        return buf.read()

    def _cell_amount(self, ws: WeekSlice, field: str) -> float:
        val = getattr(ws, field, None)
        if val is None:
            return 0.0
        if hasattr(val, 'amount'):
            return float(val.amount)
        if isinstance(val, Decimal):
            return float(val)
        return float(val)

    def _update_templated_workbook(self) -> None:
        from openpyxl.utils import get_column_letter
        ws_sheet = self.wb['Cash Flow Model']
        weeks = self.matrix.weeks
        if not weeks:
            return
        for r in list(ws_sheet.merged_cells.ranges):
            if r.min_row in [2, 3] or r.min_row >= 4:
                ws_sheet.unmerge_cells(str(r))
        for c in range(3, 60):
            for r in range(4, 98):
                cell = ws_sheet.cell(r, c)
                if type(cell).__name__ != 'MergedCell':
                    cell.value = None
        prev_month = None
        for (idx, week) in enumerate(weeks):
            col = idx + 3
            col_let = get_column_letter(col)
            prev_col_let = get_column_letter(col - 1) if col > 3 else None
            ws_sheet.cell(2, col).value = f"{week.week_ending_friday.month}/{week.week_ending_friday.day}/{week.week_ending_friday:%y}"
            curr_month = week.week_ending_friday.strftime('%b %Y')
            if curr_month != prev_month:
                ws_sheet.cell(3, col).value = curr_month
                prev_month = curr_month
            else:
                ws_sheet.cell(3, col).value = None
            for (field, row_num) in INPUT_ROWS.items():
                if field == 'opening_cash':
                    if idx == 0:
                        ws_sheet.cell(row_num, col).value = float(week.opening_cash)
                    else:
                        ws_sheet.cell(row_num, col).value = f"={prev_col_let}97"
                    continue
                val = self._cell_amount(week, field)
                ws_sheet.cell(row_num, col).value = val if val != 0.0 else 0
            ws_sheet.cell(14, col).value = f"={col_let}8+{col_let}9+{col_let}10+{col_let}11+{col_let}12+{col_let}13"
            ws_sheet.cell(20, col).value = f"=({col_let}17+{col_let}18+{col_let}19)"
            ws_sheet.cell(32, col).value = f"={col_let}23+{col_let}24+{col_let}25+{col_let}26+{col_let}27+{col_let}28+{col_let}29+{col_let}30+{col_let}31"
            ws_sheet.cell(34, col).value = f"={col_let}14-{col_let}20-{col_let}32"
            ws_sheet.cell(47, col).value = f"={col_let}37+{col_let}38+{col_let}39+{col_let}40+{col_let}41+{col_let}42+{col_let}43+{col_let}44+{col_let}45+{col_let}46"
            ws_sheet.cell(60, col).value = f"={col_let}50+{col_let}51+{col_let}52+{col_let}53+{col_let}54+{col_let}55+{col_let}56+{col_let}57+{col_let}58+{col_let}59"
            ws_sheet.cell(72, col).value = f"={col_let}63+{col_let}64+{col_let}65+{col_let}66+{col_let}67+{col_let}68+{col_let}69+{col_let}70+{col_let}71"
            ws_sheet.cell(83, col).value = f"={col_let}75+{col_let}76+{col_let}77+{col_let}78+{col_let}79+{col_let}80+{col_let}81+{col_let}82"
            ws_sheet.cell(90, col).value = f"={col_let}86+{col_let}87+{col_let}88+{col_let}89"
            ws_sheet.cell(97, col).value = f"={col_let}4+{col_let}14-{col_let}20-{col_let}32-{col_let}47-{col_let}60-{col_let}72-{col_let}83-{col_let}90+{col_let}93-{col_let}94+{col_let}95"
        if 'General Info' in self.wb.sheetnames:
            ws_gi = self.wb['General Info']
            ws_gi.cell(4, 2, '2.0 (Forecasting Engine Rebuild)')
            ws_gi.cell(5, 2, str(self.matrix.forecast_start_friday or date.today()))
            ws_gi.cell(6, 2, f"52 Weeks ({weeks[0].week_ending_friday.strftime('%b %d, %Y')} – {weeks[-1].week_ending_friday.strftime('%b %d, %Y')})")

    def _build_from_scratch(self) -> None:
        tab_names = ['Cash Flow Model', 'General Info', 'Assumptions & Rules', 'NewAddtnl Assumptions', 'Reports Needed', 'Revenue Detail', 'COGS Detail', 'Expense Assumptions', 'Credit Card Payments']
        for tab in tab_names:
            self.wb.create_sheet(tab)
        ws_sheet = self.wb['Cash Flow Model']
        weeks = self.matrix.weeks
        ws_sheet.cell(1, 1, 'AI CASH FLOW MODEL  |  Weekly Forecast').font = HEADER_FONT
        ws_sheet.cell(1, 1).fill = HEADER_FILL
        ws_sheet.cell(2, 1, 'Code').font = BOLD_FONT
        ws_sheet.cell(2, 2, 'Account').font = BOLD_FONT
        for (col_idx, week) in enumerate(weeks, start=3):
            cell = ws_sheet.cell(2, col_idx, f"{week.week_ending_friday.month}/{week.week_ending_friday.day}/{week.week_ending_friday:%y}")
            cell.font = BOLD_FONT
            cell.alignment = Alignment(horizontal='center')
        labels = {4: 'Opening Cash Position', 8: 'SERVPRO Corporate', 9: 'Other Resellers', 10: 'Adjustments', 11: 'Discount Given', 12: 'Freight Billed', 13: 'A/R Collection', 14: 'Total Revenue', 17: 'Cost of Goods Sold', 18: 'Inbound Freight', 19: "Inbound Duty & Gov't Fees", 20: 'Total COGS', 32: 'Total Operations', 34: 'GROSS PROFIT', 47: 'Total Marketing', 60: 'Total Selling', 72: 'Total Finance & Admin', 83: 'Total IT', 90: 'Total Non-Operating', 93: 'Borrowing', 94: 'Loan Repayments', 95: 'Potential Adjustments', 97: 'ENDING CASH POSITION'}
        for (row_num, label) in labels.items():
            ws_sheet.cell(row_num, 2, label).font = BOLD_FONT
        prev_month = None
        for (idx, week) in enumerate(weeks):
            col = idx + 3
            curr_month = week.week_ending_friday.strftime('%b %Y')
            if curr_month != prev_month:
                ws_sheet.cell(3, col, curr_month)
                prev_month = curr_month
            for (field, row_num) in ROW_MAP.items():
                if field == 'opening_cash':
                    if idx == 0:
                        ws_sheet.cell(row_num, col, float(week.opening_cash))
                    continue
                val = self._cell_amount(week, field)
                if val != 0.0:
                    ws_sheet.cell(row_num, col, val)
