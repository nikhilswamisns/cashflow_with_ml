"""Fix 24: Platinum statement at the close, charges after the close on the next statement, live card share over the
last three cycles, and a parent sales order that Zoho has already reduced."""
import json

from app.engine.v10_engine import RULES, V10Engine

P = "Business Platinum Card®"


def _rules():
    r = json.loads(RULES.read_text(encoding="utf-8"))
    r["manual_entries"] = []
    r["opening_cash"]["manual_adjustments"] = []
    return r


def _tx(day, amount, details="Fuel", kind="expense"):
    debit, credit = (amount, 0.0) if kind in ("payment", "refund") else (0.0, amount)
    return {"card": P, "date": day, "type": kind, "details": details, "debit": debit, "credit": credit}


def _snap(new_format=True):
    s = {"run_date": "2026-10-09", "source": "test", "pulled_at": "2026-10-02T00:00:00+00:00",
         "cash_accounts": [{"name": "BUSINESS FUNDAMENTALS CHK", "balance": 100000.0}],
         "card_accounts": [{"name": P, "balance": 10000.0}, {"name": "CORP Account - 7747", "balance": 500.0}],
         "card_cycle": {"start": "2026-08-27", "close": "2026-09-26"},
         "card_transactions": [_tx("2026-09-10", 8000.0), _tx("2026-09-12", 300.0, "Outbound Freight Costs"),
                               _tx("2026-09-28", 1500.0)],
         "invoices": [], "sales_orders": [], "purchase_orders": [], "bills": []}
    if new_format:
        s["card_cycle"].update({"history_start": "2026-06-27", "pulled_to": "2026-10-02"})
        s["card_transactions"] += [_tx("2026-07-05", 600.0, "Outbound Freight Costs"),
                                   _tx("2026-08-05", 900.0, "Outbound Freight Costs"),
                                   _tx("2026-08-06", 100.0, "Outbound Freight Costs", "refund")]
    return s


def test_first_statement_at_close_and_post_close_on_next():
    f = V10Engine(_snap(), rules=_rules()).run()
    c = f.card
    assert c["post_close"]["net"] == 1500.0
    assert c["cycles"][0]["total"] == 8500.0                      # 10,000 live - 1,500 posted after the 9/26 close
    assert round(c["cycles"][1]["opening"], 2) == 2000.0          # CORP 500 + the 1,500 posted after the close
    # nothing lost: everything owed on the cards at the pull is scheduled
    owed = sum(x["opening"] for x in c["cycles"])
    assert round(owed, 2) == 10500.0


def test_card_share_measured_live_over_three_cycles():
    f = V10Engine(_snap(), rules=_rules()).run()
    obs = [h["amount"] for h in f.card["share_obs"]]
    assert obs == [600.0, 800.0, 300.0]                           # refund nets off; payments excluded
    assert f.card["share_basis"] == "live"
    assert not any("earlier cycles not in this pull" in e for e in f.exceptions)


def test_older_snapshot_keeps_live_balance_and_stored_history():
    f = V10Engine(_snap(new_format=False), rules=_rules()).run()
    assert f.card["post_close"] is None
    assert f.card["cycles"][0]["total"] == 10000.0
    assert f.card["share_basis"] == "stored" and len(f.card["share_obs"]) == 3
    assert any("earlier cycles not in this pull" in e for e in f.exceptions)


def test_itemization_covers_the_unpaid_cycle_only():
    f = V10Engine(_snap(), rules=_rules()).run()
    assert round(sum(a for _, a in f.card["itemization"]), 2) == 8300.0


def test_parent_order_already_reduced_in_zoho_is_kept():
    s = _snap()
    s["sales_orders"] = [{"number": "SO-05927", "customer": "SERVPRO - Corporate", "status": "open", "date": "2026-09-25",
                          "shipment_date": None, "payment_terms_days": 45, "total": 61.75, "invoiced": 0.0,
                          "uninvoiced": 61.75}]
    f = V10Engine(s, rules=_rules()).run()
    row = next(r for r in f.revenue if r.ref == "SO-05927")
    assert row.amount == 61.75 and row.source == "SERVPRO Sales Order"
    # the original 333K parent still gets the fills deducted
    s["sales_orders"][0].update(total=333680.0, uninvoiced=333680.0)
    f = V10Engine(s, rules=_rules()).run()
    row = next(r for r in f.revenue if r.ref == "SO-05927")
    assert round(row.amount, 2) == round(333680.0 - 45113.65 - 79474.2, 2)


def test_paid_block_says_none_when_prior_exists_but_nothing_paid():
    import io
    import openpyxl
    from app.output.v10_exporter import export_forecast
    s = _snap()
    s["bills"] = [{"number": "B-1", "vendor": "Papertec Inc.", "status": "open", "date": "2026-09-14",
                   "due_date": "2026-10-14", "total": 5.0, "balance": 5.0, "reference": "", "accounts": ["Inventory Asset"]}]
    prior = dict(s, run_date="2026-10-02", pulled_at="2026-09-25T10:00:00+00:00")
    texts = []
    for p in (None, prior):
        f = V10Engine(s, rules=_rules(), prior_snapshot=p).run()
        ws = openpyxl.load_workbook(io.BytesIO(export_forecast(f)))["COGS Detail"]
        texts.append([c.value for row in ws.iter_rows() for c in row
                      if isinstance(c.value, str) and (c.value.startswith("No prior") or c.value.startswith("None —"))])
    assert texts[0] == ["No prior forecast on file — nothing to compare."]
    assert texts[1] and "week 1 = 10/2/26" in texts[1][0] and "paid since" in texts[1][0]


def test_statement_paid_early_is_not_rejected_and_only_remainder_is_due():
    # 6 Oct 2026 case: statement 63,812.88 at the 9/26 close, 62,875.70 paid 10/04, 16,333.76 charged since the close
    s = _snap()
    s["card_cycle"]["pulled_to"] = "2026-10-06"
    s["card_accounts"][0]["balance"] = 17270.94
    s["card_transactions"] = [_tx("2026-09-10", 63812.88), _tx("2026-07-05", 600.0, "Outbound Freight Costs"),
                              _tx("2026-08-05", 900.0, "Outbound Freight Costs"),
                              _tx("2026-09-29", 16333.76), _tx("2026-10-04", 62875.70, "AMEX Credit Card", "payment")]
    f = V10Engine(s, rules=_rules()).run()
    c = f.card
    assert not any("looks wrong" in e for e in f.exceptions)
    assert c["share_basis"] == "live"
    assert c["cycles"][0]["total"] == 937.18                       # still due on the 10/20 statement
    assert c["platinum_close_balance"] == 63812.88 and c["paid_since_close"] == 62875.70
    assert round(c["cycles"][1]["opening"], 2) == round(500.0 + 16333.76, 2)   # CORP + charges since the close


def test_paid_more_than_statement_reduces_next_statement():
    s = _snap()
    s["card_cycle"]["pulled_to"] = "2026-10-06"
    s["card_accounts"][0]["balance"] = 500.0          # 8,000 statement, 9,000 paid, 1,500 charged since
    s["card_transactions"] = [_tx("2026-09-10", 8000.0), _tx("2026-09-29", 1500.0),
                              _tx("2026-10-04", 9000.0, "AMEX Credit Card", "payment")]
    f = V10Engine(s, rules=_rules()).run()
    c = f.card
    assert c["cycles"][0]["total"] == 0.0
    assert round(c["cycles"][1]["opening"], 2) == round(500.0 + 1500.0 - 1000.0, 2)
    assert any("beyond the statement" in e for e in f.exceptions)


def test_open_amex_statement_bill_is_paid_on_row_94_not_treated_as_paid():
    # Fix 28 (6 Oct 2026): Zoho moved the statement into A/P as bill "AMEX Credit Card(04 Oct 2026)" 62,875.70 due 10/19,
    # posted to the Platinum account. The bill shows as a "payment" on the card but no cash has left yet.
    s = _snap()
    s["card_cycle"]["pulled_to"] = "2026-10-06"
    s["card_accounts"][0]["balance"] = 17270.94
    s["card_transactions"] = [_tx("2026-09-10", 63812.88), _tx("2026-07-05", 600.0, "Outbound Freight Costs"),
                              _tx("2026-08-05", 900.0, "Outbound Freight Costs"),
                              _tx("2026-09-29", 16333.76), _tx("2026-10-04", 62875.70, "AMEX Credit Card", "payment")]
    s["bills"] = [{"number": "AMEX Credit Card(04 Oct 2026)", "vendor": "AMEX Credit Card", "status": "open",
                   "date": "2026-10-04", "due_date": "2026-10-19", "total": 62875.70, "balance": 62875.70,
                   "reference": None, "accounts": [P]}]
    f = V10Engine(s, rules=_rules()).run()
    c = f.card
    assert c["cycles"][0]["total"] == 62875.70 and str(c["cycles"][0]["lands"]) == "2026-10-16"
    assert c["carry_to_next"] == 937.18 and c["post_close_net"] == 17270.94
    assert round(c["cycles"][1]["opening"], 2) == round(500.0 + 17270.94, 2)
    assert not any(r.ref.startswith("AMEX") for r in f.cogs)
    assert any(r.ref.startswith("AMEX") and "row 94" in r.basis for r in f.excluded_bills)
    assert not any("AMEX" in r[0] for r in f.restatements)
    # nothing owed is lost: bill + everything left on the cards is scheduled
    assert round(sum(x["opening"] for x in c["cycles"]), 2) == round(62875.70 + 17270.94 + 500.0, 2)
