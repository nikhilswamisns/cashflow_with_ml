"""Working capital: aging buckets, DSO / DPO, concentration, and the live 90-day reads (with a fake Zoho client)."""
from datetime import date

from app.working_capital import aging, build_working_capital, concentration, days_ratio
from app.zoho_flows import _cogs_from_report, _sales

AS_OF = date(2026, 11, 9)


def inv(customer, due, balance, status="sent"):
    return {"customer": customer, "due_date": due, "balance": balance, "total": balance, "status": status}


def test_aging_buckets_by_days_past_due():
    rows = [inv("a", "2026-11-20", 100),   # not due
            inv("a", "2026-11-09", 10),    # due today: not late
            inv("b", "2026-10-20", 200),   # 20 days late: 0-30
            inv("b", "2026-10-10", 300),   # 30 days late: 0-30 (edge)
            inv("c", "2026-10-09", 400),   # 31: 31-60
            inv("c", "2026-08-10", 500),   # 91: 90+
            inv("d", "2026-09-10", 600),   # 60: 31-60 (edge)
            inv("d", "2026-08-11", 700),   # 90: 61-90 (edge)
            inv("e", "2026-01-01", 5, status="draft"),
            inv("e", "2026-01-01", 0)]
    r = aging(rows, AS_OF, "customer")
    got = {b["label"]: (b["amount"], b["count"]) for b in r["buckets"]}
    assert got == {"Not due": (110, 2), "0-30": (500, 2), "31-60": (1000, 2), "61-90": (700, 1), "90+": (500, 1)}
    assert r["total"] == 2810 and r["count"] == 8


def test_missing_due_date_is_counted_and_reported():
    r = aging([inv("a", None, 50), inv("a", "garbage", 25)], AS_OF, "customer")
    assert r["missing_due_date"] == 2 and r["buckets"][0]["amount"] == 75


def test_dso_dpo_and_unknown_flows():
    assert days_ratio(30000, 90000) == 30.0
    assert days_ratio(30000, None) is None and days_ratio(30000, 0) is None
    snap = {"invoices": [inv("a", "2026-11-20", 45000)], "bills": [inv("v", "2026-11-20", 9000)]}
    r = build_working_capital(snap, AS_OF, {"sales": 90000, "cogs": 18000})
    assert r["dso"] == 45.0 and r["dpo"] == 45.0 and r["flows_available"]
    r = build_working_capital(snap, AS_OF, None)
    assert r["dso"] is None and r["dpo"] is None and not r["flows_available"] and r["concentration"]["sales"] is None


def test_concentration_focus_and_top5():
    rows = [inv("SERVPRO - Corporate", "2026-12-01", 600), inv("SERVPRO of X", "2026-12-01", 100)] + \
           [inv(f"c{i}", "2026-12-01", 50) for i in range(6)]
    c = concentration(rows, {"SERVPRO - Corporate": 50, "other": 50})["ar"]
    assert c["total"] == 1000 and c["focus_share"] == 0.7
    assert len(c["top"]) == 5 and c["top_share"] == 0.85   # 600 + 100 + 3 x 50 = 850 of 1000
    assert concentration(rows, {"SERVPRO - Corporate": 50, "other": 50})["sales"]["focus_share"] == 0.5


def test_zoho_reads_skip_draft_and_void_and_find_cogs():
    total, by = _sales([{"status": "paid", "total": 100, "customer_name": "A"},
                        {"status": "Void", "total": 999, "customer_name": "A"},
                        {"status": "draft", "total": 999, "customer_name": "B"},
                        {"status": "sent", "total": 50, "customer_name": "B"}])
    assert total == 150 and by == {"A": 100, "B": 50}
    # Zoho nests the sections: Gross Profit > account_transactions > [Operating Income, Cost of Goods Sold > COST OF GOODS SOLD]
    report = {"profit_and_loss": [{"name": "Gross Profit", "total": 9, "account_transactions": [
        {"name": "Operating Income", "total": 500},
        {"name": "Cost of Goods Sold", "total": 321.5, "account_transactions": [{"name": "COST OF GOODS SOLD", "total": 300}]}]}]}
    assert _cogs_from_report(report) == 321.5
    assert _cogs_from_report({"profit_and_loss": []}) is None
