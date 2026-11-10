"""This week's actions: ranking and the 14-day window, judged on the day the data was pulled."""
from datetime import date

from app.actions import build_actions

AS_OF = date(2026, 11, 9)


def inv(number, due, balance, status="sent"):
    return {"number": number, "customer": "C " + number, "due_date": due, "balance": balance, "total": balance, "status": status}


def bill(number, due, balance, status="open"):
    return {"number": number, "vendor": "V " + number, "due_date": due, "balance": balance, "total": balance, "status": status}


def test_overdue_invoices_rank_by_amount_times_days_overdue():
    snap = {"invoices": [
        inv("small-old", "2026-09-09", 1000),    # 61 days x 1000 = 61,000
        inv("big-new", "2026-11-04", 20000),     # 5 days x 20000 = 100,000  -> first
        inv("not-due", "2026-11-09", 5000),      # due today: not overdue
        inv("future", "2026-12-01", 9999),
        inv("draft", "2026-10-01", 500, status="draft"),
        inv("paid-off", "2026-10-01", 0),
    ]}
    r = build_actions(snap, AS_OF)["invoices"]
    assert [x["number"] for x in r["items"]] == ["big-new", "small-old"]
    assert r["items"][0]["days_overdue"] == 5 and r["items"][0]["score"] == 100000
    assert r["count"] == 2 and r["total"] == 21000


def test_bills_window_overdue_first_then_soonest_due():
    snap = {"bills": [
        bill("later", "2026-11-20", 700),           # 11 days away
        bill("soon-big", "2026-11-11", 3000),       # 2 days away
        bill("soon-small", "2026-11-11", 100),
        bill("overdue-small", "2026-11-01", 500),   # 8 days x 500 = 4,000
        bill("overdue-big", "2026-11-08", 9000),    # 1 day x 9000 = 9,000 -> first overdue
        bill("beyond", "2026-11-24", 8000),         # 15 days: outside the 14-day window
        bill("edge", "2026-11-23", 50),             # exactly 14 days: inside
    ]}
    r = build_actions(snap, AS_OF)["bills"]
    assert [x["number"] for x in r["items"]] == ["overdue-big", "overdue-small", "soon-big", "soon-small", "later", "edge"]
    assert r["overdue_count"] == 2 and r["overdue_total"] == 9500
    assert r["count"] == 6


def test_limit_keeps_the_count_and_total_of_everything():
    snap = {"invoices": [inv(str(i), "2026-10-01", 10) for i in range(25)]}
    r = build_actions(snap, AS_OF, limit=10)["invoices"]
    assert len(r["items"]) == 10 and r["count"] == 25 and r["total"] == 250
