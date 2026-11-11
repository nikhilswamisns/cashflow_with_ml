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
    assert sorted(calls) == ["1", "2"]


def test_stale_data_is_served_at_once_and_refreshed_in_the_background(monkeypatch):
    actuals.clear_cache()
    today = date(2026, 11, 10)
    actuals._STATE.update(at=1.0, since=date(2026, 10, 1), accounts=["x"], ledgers={})   # old, but covers what is asked
    sync, bg = [], []
    monkeypatch.setattr(actuals, "_refresh", lambda c, since: sync.append(since))
    monkeypatch.setattr(actuals, "_background_refresh", lambda since: bg.append(since))
    state = actuals._data(object(), date(2026, 10, 20), today)
    assert state["accounts"] == ["x"] and not sync and len(bg) == 1     # nobody waits for Zoho


def test_a_run_older_than_the_cached_ledger_triggers_a_real_read(monkeypatch):
    actuals.clear_cache()
    today = date(2026, 11, 10)
    actuals._STATE.update(at=1e12, since=date(2026, 10, 10), accounts=[], ledgers={})  # fresh, but starts Oct 10
    sync = []
    monkeypatch.setattr(actuals, "_refresh", lambda c, since: sync.append(since))
    actuals._data(object(), date(2026, 9, 1), today)
    assert sync == [date(2026, 9, 1)]


def test_actuals_endpoint_asks_for_the_last_14_days_whatever_the_run_date(monkeypatch):
    """A run made today (or long ago) still gets two weeks of history: the window follows today, not the run."""
    import datetime as dt
    from app.ml import api as ml_api
    seen = {}
    monkeypatch.setattr(ml_api, "_actuals_or_503", lambda fridays, today=None, start=None: seen.update(f=fridays, t=today, s=start) or {"points": []})
    monkeypatch.setattr("app.db.get_run", lambda rid: {"run_id": rid})
    class D(dt.date):
        @classmethod
        def today(cls): return cls(2026, 11, 11)
    monkeypatch.setattr(dt, "date", D)
    r = ml_api.run_actuals("x")
    assert r["start_date"] == "2026-10-28" and seen["s"] == D(2026, 10, 28)
    assert [f.isoformat() for f in seen["f"]][:2] == ["2026-10-30", "2026-11-06"]
