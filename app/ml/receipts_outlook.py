"""Weekly receipts in layers: booked documents, flat run-rate, and what the monthly revenue forecast adds.

Read-only. Same method as ml_work/06_receipts_rules_vs_forecast.py: for each calendar month,
gap = max(0, forecast x share of the month inside the window - receipts the rules already show), spread evenly
over that month's weeks. Forecast revenue is treated as cash in the same month (no payment lag). Months past Sep 2027 extend the same trend.
"""
from __future__ import annotations

import calendar
import csv
from collections import defaultdict

from app.ml import ROOT

FORECAST_CSV = ROOT / "ml_work" / "outputs" / "05_forecast_new_range.csv"


def load_monthly_forecast() -> dict[tuple[int, int], dict[str, float]]:
    with open(FORECAST_CSV, newline="", encoding="utf-8") as fh:
        return {(int(r[""][:4]), int(r[""][5:7])): {k: float(r[k]) for k in ("trend_forecast", "low", "high")}
                for r in csv.DictReader(fh)}


def extend_forecast(fc: dict, until: tuple[int, int]) -> tuple[dict, set]:
    """Extend the monthly forecast past the CSV's last month. The model is a log-linear trend: each month is the
    previous one times a constant growth factor, and low/high are fixed multiples of the trend, so the same factor
    carries all three columns forward. Returns (extended forecast, months that were extended)."""
    fc = dict(fc)
    keys = sorted(fc)
    extended: set = set()
    if len(keys) < 2:
        return fc, extended
    prev, last = fc[keys[-2]], fc[keys[-1]]
    growth = {k: last[k] / prev[k] for k in last}
    y, m = keys[-1]
    cur = dict(last)
    while (y, m) < until:
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        cur = {k: cur[k] * growth[k] for k in cur}
        fc[(y, m)] = dict(cur)
        extended.add((y, m))
    return fc, extended


def build_outlook(f) -> dict:
    """f: an engine Forecast (rules only)."""
    from app.engine.v10_engine import ROW_TOTAL_REVENUE
    fridays = f.fridays
    total = f.values[ROW_TOTAL_REVENUE]
    docs = [0.0] * len(fridays)
    for r in f.revenue:
        if r.week in fridays:
            docs[fridays.index(r.week)] += r.amount
    runrate = [max(t - d, 0.0) for t, d in zip(total, docs)]
    last_fri = fridays[-1]
    fc, ext_months = extend_forecast(load_monthly_forecast(), (last_fri.year, last_fri.month))
    by_month = defaultdict(list)
    for i, d in enumerate(fridays):
        by_month[(d.year, d.month)].append(i)
    added, low, high = ([0.0] * len(fridays) for _ in range(3))
    covered = [False] * len(fridays)
    extended = [(d.year, d.month) in ext_months for d in fridays]
    for (y, m), idx in by_month.items():
        if (y, m) not in fc:
            continue
        fridays_in_month = sum(1 for day in range(1, calendar.monthrange(y, m)[1] + 1) if calendar.weekday(y, m, day) == 4)
        share = len(idx) / fridays_in_month
        booked = sum(total[i] for i in idx)
        for key, arr in (("trend_forecast", added), ("low", low), ("high", high)):
            gap = max(0.0, fc[(y, m)][key] * share - booked)
            for i in idx:
                arr[i] = gap / len(idx)
        for i in idx:
            covered[i] = True
    r2 = lambda a: [round(v, 2) for v in a]
    return {"weeks": [d.isoformat() for d in fridays], "documents": r2(docs), "run_rate": r2(runrate),
            "forecast_added": r2(added), "forecast_added_low": r2(low), "forecast_added_high": r2(high),
            "forecast_covered": covered, "forecast_extended": extended,
            "note": "Forecast revenue is treated as cash in the same month (no payment lag). Months past Sep 2027 extend the same trend. Receipts only: costs are not included."}
