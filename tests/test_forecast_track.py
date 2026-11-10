"""Forecast tracking: the 'made before the week began' rule, the single file, and the actual-cash rebuild."""
from datetime import date

import pytest

from app.ml import actuals, track


def cmp(w1, rules, ml):
    """A /compare-like result for a run whose first Friday is w1."""
    wk = [w1, date.fromordinal(date.fromisoformat(w1).toordinal() + 7).isoformat(), "2099-01-01"]
    return {"weeks": wk, "ending_cash_rules": rules, "ending_cash_ml": ml, "bands": {"p10": [0, 0, 0], "p90": [9, 9, 9]}}


@pytest.fixture(autouse=True)
def tmp_file(tmp_path, monkeypatch):
    monkeypatch.setattr(track, "TRACK_FILE", tmp_path / "forecast_track.json")


def test_run_made_inside_the_week_is_not_a_prediction_of_it():
    # run created Wed 28 Oct, first Friday 30 Oct: Oct 30's week began Mon 26 Oct, so only Nov 6 is a prediction
    done = track.record("r1", "2026-10-28T11:06:00+00:00", cmp("2026-10-30", [-37538, -100010, 1], [10, 20, 30]))
    assert done == ["2026-11-06"]
    d = track.load()["weeks"]
    assert set(d) == {"2026-11-06"} and d["2026-11-06"]["rules"] == -100010 and d["2026-11-06"]["ml"] == 20


def test_only_the_first_horizon_weeks_are_kept():
    track.record("r1", "2026-10-19T00:00:00+00:00", cmp("2026-10-23", [1, 2, 3], [4, 5, 6]))  # Monday Oct 19: both weeks eligible
    assert len(track.load()["weeks"]) == track.HORIZON_WEEKS == 2


def test_a_later_run_before_the_week_starts_replaces_the_prediction():
    track.record("r1", "2026-10-28T11:00:00+00:00", cmp("2026-10-30", [0, -100, 0], [0, 50, 0]))
    track.record("r2", "2026-11-02T08:00:00+00:00", cmp("2026-11-06", [-80, 0, 0], [60, 0, 0]))  # Monday Nov 2: still eligible for Nov 6
    w = track.load()["weeks"]["2026-11-06"]
    assert (w["run_id"], w["rules"], w["ml"]) == ("r2", -80, 60)


def test_a_run_made_after_the_week_began_never_replaces_it():
    track.record("r1", "2026-10-28T11:00:00+00:00", cmp("2026-10-30", [0, -100, 0], [0, 50, 0]))
    track.record("r3", "2026-11-03T08:00:00+00:00", cmp("2026-11-06", [-5, 0, 0], [5, 0, 0]))  # Tuesday Nov 3: too late for Nov 6
    assert track.load()["weeks"]["2026-11-06"]["run_id"] == "r1"


def test_an_older_run_never_replaces_a_newer_eligible_one():
    track.record("new", "2026-11-02T08:00:00+00:00", cmp("2026-11-06", [-80, 0, 0], [60, 0, 0]))
    track.record("old", "2026-10-28T11:00:00+00:00", cmp("2026-10-30", [0, -100, 0], [0, 50, 0]))  # re-run of an old run
    assert track.load()["weeks"]["2026-11-06"]["run_id"] == "new"


def test_rebuild_undoes_entries_dated_after_each_day():
    rows = [{"transaction_date": "2026-11-09", "debit_amount": 5936.0, "credit_amount": ""},
            {"transaction_date": "2026-11-05", "debit_amount": "", "credit_amount": 1000.0},
            {"transaction_date": "2026-10-20", "debit_amount": 50.0, "credit_amount": ""}]
    out = actuals.rebuild(10000.0, rows, [date(2026, 11, 6), date(2026, 11, 4), date(2026, 10, 19)])
    assert out[date(2026, 11, 6)] == 4064.0        # 10000 - 5936 (the Nov 9 deposit is after)
    assert out[date(2026, 11, 4)] == 5064.0        # also undo the Nov 5 payment of 1000: 10000 - 5936 + 1000
    assert out[date(2026, 10, 19)] == 5014.0       # all three entries are after: 10000 - (5936 - 1000 + 50)


def test_weekly_actuals_adds_accounts_and_ends_at_today(monkeypatch):
    actuals._CACHE.clear()
    monkeypatch.setattr(actuals, "_accounts", lambda c: [{"account_id": "1", "name": "CHK", "balance": 1000.0},
                                                         {"account_id": "2", "name": "PayPal", "balance": 50.0}])
    ledger = {"1": [{"transaction_date": "2026-11-09", "debit_amount": 300.0, "credit_amount": ""}], "2": []}
    monkeypatch.setattr(actuals, "_ledger", lambda c, aid, since: ledger[aid])
    r = actuals.weekly_actuals([date(2026, 10, 30), date(2026, 11, 6), date(2026, 11, 13)], today=date(2026, 11, 10), client=object())
    assert [(p["date"], p["balance"], p["kind"]) for p in r["points"]] == [
        ("2026-10-30", 750.0, "week_end"), ("2026-11-06", 750.0, "week_end"), ("2026-11-10", 1050.0, "today")]  # Nov 13 is in the future: no point
