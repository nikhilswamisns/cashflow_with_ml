"""Walk-forward backtest: would ML have beaten the fixed rules?

For each cut-off Friday T: train ONLY on documents finished by T, take the documents that were open at T, forecast
them with (a) the current engine rule and (b) the ML P50, and compare both with what really happened.

Metrics (per kind, averaged over cut-offs):
  mae_days      mean absolute error of the predicted cash date
  within_1wk    share of documents placed in the correct forecast week (+/-0 weeks) / within 1 week
  wape_12w      weekly-total error over the next 12 weeks:  sum|predicted - actual| / sum(actual)
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from app.ml.history import build_tables
from app.ml.timing_model import TimingModel

SO_DAYS = {"servpro": 45, "amazon": 30, "other": 21}      # forecast_rules.json  sales_orders / amazon


def fri_after(ts: pd.Timestamp) -> pd.Timestamp:
    return ts + pd.Timedelta(days=(4 - ts.dayofweek) % 7)


def fri_before(ts: pd.Timestamp) -> pd.Timestamp:
    return ts - pd.Timedelta(days=(ts.dayofweek - 4) % 7)


def _rule_date(kind: str, r) -> pd.Timestamp:
    if kind in ("inv", "bill"):
        return r.base_date
    n = r.party
    days = SO_DAYS["servpro"] if "servpro" in n else SO_DAYS["amazon"] if "amazon" in n else SO_DAYS["other"]
    return r.base_date + pd.Timedelta(days=days)


def _week(kind: str, d: pd.Timestamp, T: pd.Timestamp) -> pd.Timestamp:
    w = fri_before(d) if kind == "bill" else fri_after(d)      # same convention as the engine
    return max(w, T)


def backtest_kind(tab: pd.DataFrame, kind: str, cutoffs: Iterable[pd.Timestamp], horizon_weeks: int = 12) -> list[dict]:
    out = []
    for T in cutoffs:
        done = tab[tab["paid_on"] <= T]
        model = TimingModel.fit(done, kind)
        if model is None:
            continue
        open_ = tab[(tab["known_date"] <= T) & (tab["paid_on"] > T)].copy()
        if kind != "inv":
            open_ = open_[open_["base_date"].notna()]
        if len(open_) < 15:
            continue
        pred = model.predict(open_)
        open_["rule"] = [_rule_date(kind, r) for r in open_.itertuples()]
        open_["ml"] = [r.base_date + pd.Timedelta(days=int(round(p))) if model.stats.n(r.party) >= 3 else r.rule
                       for r, p in zip(open_.itertuples(), pred[:, 1])]
        res = {"cutoff": str(T.date()), "n": int(len(open_))}
        end = T + pd.Timedelta(weeks=horizon_weeks)
        for name in ("rule", "ml"):
            err = (open_[name] - open_["paid_on"]).dt.days.abs()
            wk_pred = open_[name].map(lambda d: _week(kind, d, T))
            wk_act = open_["paid_on"].map(lambda d: _week(kind, d, T))
            weeks = pd.date_range(T, end, freq="7D")
            p = open_.groupby(wk_pred)["amount"].sum().reindex(weeks, fill_value=0.0)
            a = open_.groupby(wk_act)["amount"].sum().reindex(weeks, fill_value=0.0)
            res[name] = {"mae_days": round(float(err.mean()), 2), "median_abs_err_days": round(float(err.median()), 1),
                         "same_week_pct": round(float((wk_pred == wk_act).mean() * 100), 1),
                         "within_1wk_pct": round(float(((wk_pred - wk_act).abs() <= pd.Timedelta(days=7)).mean() * 100), 1),
                         "wape_12w_pct": round(float((p - a).abs().sum() / max(a.sum(), 1) * 100), 1)}
        out.append(res)
    return out


def default_cutoffs(tab: pd.DataFrame, n: int = 6, step_weeks: int = 8) -> list[pd.Timestamp]:
    last = fri_before(tab["paid_on"].max()) - pd.Timedelta(weeks=14)         # leave 12+ weeks to observe outcomes
    return [last - pd.Timedelta(weeks=step_weeks * i) for i in range(n)][::-1]


def run_backtest(history_path, n_cutoffs: int = 6) -> dict:
    tables = build_tables(history_path)
    report = {}
    for kind, tab in tables.items():
        if tab is None or tab.empty:
            continue
        rows = backtest_kind(tab, kind, default_cutoffs(tab, n_cutoffs))
        if not rows:
            continue
        summ = {}
        for name in ("rule", "ml"):
            summ[name] = {k: round(float(np.mean([r[name][k] for r in rows])), 2) for k in rows[0][name]}
        report[kind] = {"cutoffs": rows, "average": summ}
    return report
