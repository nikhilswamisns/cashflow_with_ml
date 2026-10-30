from __future__ import annotations
from datetime import date
from dateutil.relativedelta import relativedelta
from app.config.loader import load_assumptions
from app.transforms.date_bucketing import bucket_po_to_week_ending_friday

def cc_expense_cash_out_week(statement_cycle_end_date: date, forecast_start_friday: date) -> date:
    cfg = load_assumptions()
    pay_day = cfg.cc_payment_day_of_month
    payment_due_date = date(statement_cycle_end_date.year, statement_cycle_end_date.month, pay_day) + relativedelta(months=1)
    return bucket_po_to_week_ending_friday(payment_due_date, forecast_start_friday)
