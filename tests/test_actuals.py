"""Actual cash rebuilt from the Zoho ledger."""
from datetime import date

from app.ml import actuals


def test_rebuild_undoes_entries_dated_after_each_day():
    rows = [{"transaction_date": "2026-11-09", "debit_amount": 5936.0, "credit_amount": ""},
            {"transaction_date": "2026-11-05", "debit_amount": "", "credit_amount": 1000.0},
            {"transaction_date": "2026-10-20", "debit_amount": 50.0, "credit_amount": ""}]
    out = actuals.rebuild(10000.0, rows, [date(2026, 11, 6), date(2026, 11, 4), date(2026, 10, 19)])
    assert out[date(2026, 11, 6)] == 4064.0        # 10000 - 5936 (the Nov 9 deposit is after)
    assert out[date(2026, 11, 4)] == 5064.0        # also undo the Nov 5 payment of 1000: 10000 - 5936 + 1000
    assert out[date(2026, 10, 19)] == 5014.0       # all three entries are after: 10000 - (5936 - 1000 + 50)


def test_weekly_actuals_has_start_fridays_and_today_and_shares_one_ledger_fetch(monkeypatch):
    actuals.clear_cache()
    monkeypatch.setattr(actuals, "_accounts", lambda c: [{"account_id": "1", "name": "CHK", "balance": 1000.0},
                                                         {"account_id": "2", "name": "PayPal", "balance": 50.0}])
    ledger = {"1": [{"transaction_date": "2026-11-09", "debit_amount": 300.0, "credit_amount": ""}], "2": []}
    calls = []
    monkeypatch.setattr(actuals, "_ledger", lambda c, aid, since: calls.append(aid) or ledger[aid])
    args = dict(today=date(2026, 11, 10), client=object(), start=date(2026, 10, 28))
    fridays = [date(2026, 10, 30), date(2026, 11, 6), date(2026, 11, 13)]
    r = actuals.weekly_actuals(fridays, **args)
    assert [(p["date"], p["balance"], p["kind"]) for p in r["points"]] == [
        ("2026-10-28", 750.0, "start"), ("2026-10-30", 750.0, "week_end"), ("2026-11-06", 750.0, "week_end"),
        ("2026-11-10", 1050.0, "today")]  # Nov 13 is in the future: no point
    actuals.weekly_actuals(fridays[:2], **args)        # another run, same day: no new Zoho ledger calls
    assert calls == ["1", "2"]
