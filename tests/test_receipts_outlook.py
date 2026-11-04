"""Receipts outlook: the trend extension past the forecast CSV and the no-double-count rule."""
from datetime import date

import pytest

from app.ml.receipts_outlook import build_outlook, extend_forecast


def test_extend_forecast_keeps_growth_factor_and_band_multiples():
    fc = {(2027, 8): {"trend_forecast": 100.0, "low": 80.0, "high": 150.0},
          (2027, 9): {"trend_forecast": 110.0, "low": 88.0, "high": 165.0}}
    out, ext = extend_forecast(fc, (2027, 11))
    assert ext == {(2027, 10), (2027, 11)}
    assert out[(2027, 10)]["trend_forecast"] == pytest.approx(121.0)
    assert out[(2027, 10)]["low"] / out[(2027, 10)]["trend_forecast"] == pytest.approx(0.8)
    assert out[(2027, 11)]["high"] / out[(2027, 11)]["trend_forecast"] == pytest.approx(1.5)


def test_extend_forecast_noop_when_covered():
    fc = {(2027, 8): {"trend_forecast": 1.0, "low": 1.0, "high": 1.0}, (2027, 9): {"trend_forecast": 2.0, "low": 2.0, "high": 2.0}}
    out, ext = extend_forecast(fc, (2027, 9))
    assert out == fc and ext == set()


class _Row:
    def __init__(self, week, amount):
        self.week, self.amount = week, amount


class _F:
    """Minimal stand-in for an engine Forecast: 4 Fridays of Nov 2026, known receipts of 100 a week."""
    fridays = [date(2026, 11, 6), date(2026, 11, 13), date(2026, 11, 20), date(2026, 11, 27)]
    values = {15: [100.0, 100.0, 100.0, 100.0]}
    revenue = [_Row(date(2026, 11, 6), 60.0)]


def test_forecast_fills_only_the_gap(monkeypatch):
    monkeypatch.setattr("app.ml.receipts_outlook.load_monthly_forecast",
                        lambda: {(2026, 10): {"trend_forecast": 1.0, "low": 1.0, "high": 1.0},
                                 (2026, 11): {"trend_forecast": 1000.0, "low": 800.0, "high": 1500.0}})
    o = build_outlook(_F())
    # Nov 2026 has 4 Fridays and all 4 are in the window: share = 1; known = 400, so the forecast adds 600
    assert sum(o["forecast_added"]) == pytest.approx(600.0)
    assert [a + b for a, b in zip(o["documents"], o["run_rate"])] == [100.0] * 4
    assert sum(o["forecast_added_low"]) == pytest.approx(400.0)


def test_forecast_never_negative_when_known_beats_forecast(monkeypatch):
    monkeypatch.setattr("app.ml.receipts_outlook.load_monthly_forecast",
                        lambda: {(2026, 10): {"trend_forecast": 1.0, "low": 1.0, "high": 1.0},
                                 (2026, 11): {"trend_forecast": 300.0, "low": 200.0, "high": 400.0}})
    assert sum(build_outlook(_F())["forecast_added"]) == 0.0
