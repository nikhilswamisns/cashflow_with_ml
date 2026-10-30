"""Fix 26: 52-week window; Duckbill repayment on row 95 (1st Friday, General Info B32, through Dec 2027)."""
import json
from datetime import date

from app.engine.v10_engine import RULES, V10Engine


def _rules(**over):
    r = json.loads(RULES.read_text(encoding="utf-8"))
    r["manual_entries"] = []
    r["opening_cash"]["manual_adjustments"] = []
    r.update(over)
    return r


def _snap(bills=()):
    return {"run_date": "2026-10-09", "source": "test", "pulled_at": "2026-10-02T00:00:00+00:00",
            "cash_accounts": [{"name": "BUSINESS FUNDAMENTALS CHK", "balance": 100000.0}],
            "card_accounts": [{"name": "Business Platinum Card", "balance": 0.0}],
            "card_transactions": [], "invoices": [], "sales_orders": [], "purchase_orders": [], "bills": list(bills)}


DUCK = {"number": "Duckbill Repayment(30 Sep 2026)", "vendor": "Skagit Valley Innovations, LLC (Duckbill)",
        "status": "open", "date": "2026-09-30", "due_date": "2026-10-15", "total": 3750.0, "balance": 3750.0,
        "reference": None, "accounts": ["Intellectual Property Rights-Payable"]}


def test_window_is_52_weeks():
    f = V10Engine(_snap(), rules=_rules()).run()
    assert len(f.fridays) == 52 and f.fridays[-1] == date(2027, 10, 1)


def test_open_bill_then_first_fridays_no_double_count():
    f = V10Engine(_snap([DUCK]), rules=_rules()).run()
    weeks = [(x["week"], x["source"].startswith("Zoho")) for x in f.duckbill]
    assert weeks[0] == (date(2026, 10, 9), True)                 # Oct payment: 1st Friday 10/02 is before week 1 -> week 1
    assert weeks[1] == (date(2026, 11, 6), False)                # then the schedule from November
    assert all(x["week"].day <= 7 for x in f.duckbill if x["source"].startswith("Schedule"))   # 1st Fridays
    assert sum(1 for x in f.duckbill if (x["week"].year, x["week"].month) == (2026, 10)) == 1
    i = f.fridays.index(date(2026, 11, 6))
    assert f.values[95][i] == 3750.0 and f.cfm[95][i][1] == "='General Info'!$B$32"
    # the bill is not in COGS; it is listed with the row-95 reason
    assert not any(r.ref == DUCK["number"] for r in f.cogs)
    assert any(r.ref == DUCK["number"] and "row 95" in r.basis for r in f.excluded_bills)


def test_no_bill_means_schedule_only_and_end_month():
    f = V10Engine(_snap(), rules=_rules()).run()
    assert f.duckbill[0]["week"] == date(2026, 11, 6)            # October's 1st Friday (10/02) is before week 1
    r = _rules()
    r["duckbill"]["end_month"] = "2027-03"
    f = V10Engine(_snap(), rules=r).run()
    assert f.duckbill[-1]["week"] == date(2027, 3, 5) and len(f.duckbill) == 5


def test_bill_amount_different_from_monthly_is_used_and_flagged():
    f = V10Engine(_snap([dict(DUCK, balance=3500.0)]), rules=_rules()).run()
    assert f.values[95][0] == 3500.0 and f.cfm[95][0][1] == "=3500.0"
    assert any("Duckbill bill" in e for e in f.exceptions)
