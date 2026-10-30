"""Refresh & Compare: the comparison of a run with a later refresh pull (same week 1)."""
import copy
import io
import json

import openpyxl

from app.engine.compare import compare
from app.engine.v10_engine import RULES, V10Engine
from app.output.v10_exporter import export_forecast


def _rules():
    r = json.loads(RULES.read_text(encoding="utf-8"))
    r["manual_entries"] = []
    r["opening_cash"]["manual_adjustments"] = []
    return r


def _base():
    return {"run_date": "2026-10-02", "source": "test", "pulled_at": "2026-10-01T22:00:00+00:00",
            "cash_accounts": [{"name": "BUSINESS FUNDAMENTALS CHK", "balance": 100000.0}],
            "card_accounts": [{"name": "Business Platinum Card", "balance": 0.0}],
            "card_transactions": [],
            "invoices": [{"number": "INV-1", "customer": "Acme", "status": "sent", "date": "2026-09-20",
                          "due_date": "2026-10-20", "total": 1000.0, "balance": 1000.0, "salesorder_number": None},
                         {"number": "INV-2", "customer": "Beta", "status": "draft", "date": "2026-09-28",
                          "due_date": "2026-10-28", "total": 300.0, "balance": 300.0, "salesorder_number": None}],
            "sales_orders": [], "purchase_orders": [],
            "bills": [{"number": "B-1", "vendor": "Papertec Inc.", "status": "open", "date": "2026-09-14",
                       "due_date": "2026-10-14", "total": 5000.0, "balance": 5000.0, "reference": "",
                       "accounts": ["Inventory Asset"]}]}


def _refresh(base):
    r = copy.deepcopy(base)
    r["pulled_at"] = "2026-10-02T14:00:00+00:00"
    r["bills"] = []                                            # B-1 paid ...
    r["cash_accounts"][0]["balance"] -= 5000.0                 # ... from the bank
    r["invoices"][0]["balance"] = 600.0                        # INV-1 partly collected
    r["invoices"][0]["status"] = "partially_paid"
    r["cash_accounts"][0]["balance"] += 400.0
    r["invoices"][1]["status"] = "sent"                        # status only
    r["purchase_orders"] = [{"number": "PO-9", "vendor": "New Vendor", "status": "issued", "date": "2026-10-01",
                             "delivery_date": "2026-10-10", "total": 2000.0, "unbilled": 2000.0,
                             "payment_terms_days": 30, "accounts": ["Inventory Asset"], "received_status": ""}]
    return r


def _run(snap):
    return V10Engine(snap, rules=_rules()).run()


def test_bridge_explains_the_change_exactly():
    b = _base()
    r = _refresh(b)
    c = compare(b, r, _run(b), _run(r))
    assert c.notes == []
    assert round(c.bridge_total, 2) == round(c.horizon_change, 2) == -2000.0
    br = {label: amt for _, label, amt, _ in c.bridge}
    assert br["Settled activity - net"] == 0.0                # paid bill + partial collection = cash moved, no net effect
    assert br["New payments (new bills / purchase orders)"] == -2000.0
    ch = {x["ref"]: x["change"] for rows in c.blocks.values() for x in rows}
    assert ch["B-1"] == "No longer open" and ch["INV-1"] == "Partly paid" and ch["PO-9"] == "New"
    assert ch["INV-2"] == "Status draft → sent"
    assert next(x for x in c.blocks["Invoices"] if x["ref"] == "INV-2")["note"] == "No cash effect"


def test_no_changes_when_nothing_moved():
    b = _base()
    c = compare(b, copy.deepcopy(b), _run(b), _run(b))
    assert all(v == 0 for v in c.counts.values()) and c.bridge_total == 0


def test_export_adds_sheet_and_keeps_run_numbers():
    b = _base()
    r = _refresh(b)
    fb = _run(b)
    c = compare(b, r, fb, _run(r))
    plain = openpyxl.load_workbook(io.BytesIO(export_forecast(fb)))
    with_c = openpyxl.load_workbook(io.BytesIO(export_forecast(fb, comparison=c)))
    assert "Changes Since Run" not in plain.sheetnames
    assert with_c.sheetnames[-1] == "Changes Since Run"
    for name in plain.sheetnames:                           # main sheets identical: they show the run
        a, z = plain[name], with_c[name]
        assert all(a.cell(i, j).value == z.cell(i, j).value
                   for i in range(1, a.max_row + 1) for j in range(1, a.max_column + 1)), name
