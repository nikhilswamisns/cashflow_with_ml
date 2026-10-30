"""Manual entries (forecast_rules.json "manual_entries") and the empty opening-cash adjustment."""
import copy
import json
from datetime import date

from app.engine.v10_engine import RULES, V10Engine


def _snap(run_date="2026-10-02"):
    return {"run_date": run_date, "source": "test", "pulled_at": "2026-10-01T00:00:00+00:00",
            "invoices": [], "sales_orders": [], "purchase_orders": [], "bills": [], "card_transactions": [],
            "cash_accounts": [{"name": "BUSINESS FUNDAMENTALS CHK", "balance": 100000.0},
                              {"name": "Stripe Clearing", "balance": 1000.0}],
            "card_accounts": [{"name": "Business Platinum Card", "balance": 0.0},
                              {"name": "CORP Account - 7747", "balance": 0.0}]}


def _rules(entries, adjustments=()):
    r = json.loads(RULES.read_text(encoding="utf-8"))
    r["manual_entries"] = list(entries)
    r["opening_cash"]["manual_adjustments"] = list(adjustments)
    return r


ENTRY = {"label": "Loan repayment - one-off", "cfm_row": 95, "week_ending": "2026-10-02", "amount": 73000.0,
         "source": "test", "entered_by": "test", "entered_on": "2026-10-01"}


def test_opening_cash_without_adjustment():
    f = V10Engine(_snap(), rules=_rules([])).run()
    assert f.manual_adjustments == []
    assert f.opening_cash == 101000.0


def test_entry_applied_by_formula_and_reduces_cash():
    base = V10Engine(_snap(), rules=_rules([])).run()
    f = V10Engine(_snap(), rules=_rules([ENTRY])).run()
    m = f.manual_entries[0]
    assert m["applied"] and m["gi_row"] == 50 and m["week"] == date(2026, 10, 2)
    assert f.values[95][0] - base.values[95][0] == 73000.0       # on top of the scheduled row-95 amounts
    assert f.cfm[95][0][1] == "='General Info'!$B$32+'General Info'!$B$50"   # Duckbill (1st Friday) + the entry
    assert round(base.values[98][0] - f.values[98][0], 2) == 73000.0
    assert round(base.values[98][-1] - f.values[98][-1], 2) == 73000.0


def test_entry_added_to_existing_schedule_cell():
    e = dict(ENTRY, week_ending="2026-10-30", amount=500.0)   # last Friday: row 95 already carries $13,333
    f = V10Engine(_snap(), rules=_rules([e])).run()
    v, formula = f.cfm[95][4]
    assert round(v, 2) == round(f.assumptions.gi[31] + 500.0, 2)
    assert formula == "='General Info'!$B$31+'General Info'!$B$50"


def test_entry_before_week_1_expires():
    f = V10Engine(_snap("2026-10-09"), rules=_rules([ENTRY])).run()
    assert not f.manual_entries[0]["applied"] and f.manual_entries[0]["status"].startswith("EXPIRED")
    assert all(v == 0 for v in f.values[95][:3])


def test_entry_on_card_or_detail_row_is_refused():
    rules = _rules([dict(ENTRY, cfm_row=24), dict(ENTRY, cfm_row=10), dict(ENTRY, cfm_row=94)])
    f = V10Engine(_snap(), rules=rules).run()
    assert [m["applied"] for m in f.manual_entries] == [False, False, False]
    assert len([e for e in f.exceptions if "cannot take a manual entry" in e]) == 3


def test_amazon_customers_get_their_own_row():
    snap = _snap()
    snap["invoices"] = [
        {"number": "INV-1", "customer": "Gutster Amazon USA", "status": "sent", "date": "2026-09-20", "due_date": "2026-10-20",
         "total": 100.0, "balance": 100.0, "salesorder_number": None},
        {"number": "INV-2", "customer": "Duckbill Amazon USA", "status": "partially_paid", "date": "2026-09-20",
         "due_date": "2026-10-20", "total": 50.0, "balance": 40.0, "salesorder_number": None},
        {"number": "INV-3", "customer": "Acme Hardware", "status": "sent", "date": "2026-09-20", "due_date": "2026-10-20",
         "total": 70.0, "balance": 70.0, "salesorder_number": None},
        {"number": "INV-4", "customer": "SERVPRO - Corporate", "status": "sent", "date": "2026-09-20",
         "due_date": "2026-10-20", "total": 30.0, "balance": 30.0, "salesorder_number": None}]
    f = V10Engine(snap, rules=_rules([])).run()
    src = {r.ref: r.source for r in f.revenue}
    assert src == {"INV-1": "Amazon Invoice", "INV-2": "Amazon Invoice", "INV-3": "A/R Collection", "INV-4": "SERVPRO Invoice"}
    i = f.fridays.index(date(2026, 10, 23))
    assert f.values[10][i] == 140.0 and f.values[14][i] == 70.0 and f.values[8][i] == 30.0
    assert f.values[15][i] >= 240.0          # Total Revenue includes all three revenue rows


def test_amazon_sales_orders_and_export_routing():
    import io
    import openpyxl
    from app.output.v10_exporter import export_forecast
    snap = _snap()
    snap["invoices"] = [
        {"number": "INV-A", "customer": "Staple Popper Amazon Canada", "status": "sent", "date": "2026-09-20",
         "due_date": "2026-10-20", "total": 10.0, "balance": 10.0, "salesorder_number": None},
        {"number": "INV-R", "customer": "Heath Lumber Co., Inc.", "status": "sent", "date": "2026-09-20",
         "due_date": "2026-10-20", "total": 20.0, "balance": 20.0, "salesorder_number": None}]
    snap["sales_orders"] = [
        {"number": "SO-A", "customer": "Gutster Amazon USA", "status": "open", "date": "2026-09-30",
         "shipment_date": "2026-10-01", "payment_terms_days": 30, "total": 500.0, "invoiced": 0.0, "uninvoiced": 500.0},
        {"number": "SO-R", "customer": "Excel Supplies - Houston", "status": "confirmed", "date": "2026-09-29",
         "shipment_date": "2026-09-30", "payment_terms_days": 30, "total": 300.0, "invoiced": 0.0, "uninvoiced": 300.0}]
    f = V10Engine(snap, rules=_rules([])).run()
    src = {r.ref: (r.source, r.week) for r in f.revenue}
    assert src["SO-A"] == ("Amazon Sales Order", date(2026, 11, 6))   # ship 10/01 + 30 = 10/31 -> Friday on/after
    assert src["SO-R"][0] == "A/R Sales Order" and src["INV-R"][0] == "A/R Collection" and src["INV-A"][0] == "Amazon Invoice"
    # no Amazon customer may reach the A/R row, and the two rows add up to all non-SERVPRO revenue lines
    amazon = sum(r.amount for r in f.revenue if "amazon" in r.party.lower())
    assert amazon == 510.0
    assert round(sum(f.values[10]), 2) == 510.0
    assert round(sum(f.values[14]), 2) == 320.0
    wb = openpyxl.load_workbook(io.BytesIO(export_forecast(f)))
    cfm = wb["Cash Flow Model"]
    assert cfm["B10"].value.strip() == "Amazon" and cfm["B14"].value.strip() == "A/R Collection"
    assert '"Amazon*"' in cfm["C10"].value and '"A/R*"' in cfm["C14"].value
    rd = wb["Revenue Detail"]
    for row in rd.iter_rows(min_row=15):
        cust, label = row[2].value, row[0].value
        if isinstance(cust, str) and "amazon" in cust.lower() and row[5].value is not None:
            assert str(label).startswith("Amazon"), (cust, label)
