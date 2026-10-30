"""Quantile gradient-boosting model for "how many days after <base date> does the cash move?".

One TimingModel per document kind (invoice / sales order / bill).  It predicts the 10th, 50th and 90th percentile
of the delay, so the engine gets a best guess (P50) and the Monte-Carlo step gets a realistic spread.

Honest-by-construction features: a party's history statistics for a training row are computed ONLY from payments
that had already happened when that document was issued (no peeking at the future), exactly as at forecast time.
Training is deterministic (fixed seed) so the same history always gives the same forecast.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from app.ml.history import Y_MAX, Y_MIN, is_amazon, is_servpro

QUANTILES = (0.1, 0.5, 0.9)
FEATURES = ["p_n", "p_med", "p_mean", "p_std", "p_rec_med", "p_rec_std", "terms", "log_amt",
            "month", "dow", "dom", "servpro", "amazon"]
RECENT = 8                     # "recent behaviour" = the party's last 8 payments
HALF_LIFE_DAYS = 540           # a payment 18 months old counts half as much as a new one (behaviour drifts)


class PartyStats:
    """Per-party payment history, sorted by payment date, queryable 'as of' any date."""

    def __init__(self, df: pd.DataFrame):
        self.hist: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for p, g in df.groupby("party"):
            g = g.sort_values("paid_on")
            self.hist[p] = (g["paid_on"].values.astype("datetime64[D]"), g["y"].values.astype(float))

    def n(self, party: str) -> int:
        return len(self.hist[party][1]) if party in self.hist else 0

    def at(self, party: str, as_of: Optional[np.datetime64] = None) -> list[float]:
        if party not in self.hist:
            return [0, np.nan, np.nan, np.nan, np.nan, np.nan]
        dts, ys = self.hist[party]
        if as_of is not None:
            ys = ys[: np.searchsorted(dts, as_of, side="left")]      # only payments before as_of
        if len(ys) == 0:
            return [0, np.nan, np.nan, np.nan, np.nan, np.nan]
        r = ys[-RECENT:]
        return [len(ys), float(np.median(ys)), float(ys.mean()), float(ys.std()), float(np.median(r)), float(r.std())]


def feature_frame(rows: pd.DataFrame, stats: PartyStats, as_of_known: bool) -> pd.DataFrame:
    """as_of_known=True (training): stats as of each row's known_date.  False (forecast): all history."""
    recs = []
    for r in rows.itertuples(index=False):
        st = stats.at(r.party, np.datetime64(r.known_date.date()) if as_of_known else None)
        b = r.base_date
        recs.append(st + [getattr(r, "terms", np.nan), np.log1p(max(float(r.amount), 0.0)),
                          b.month, b.dayofweek, b.day, is_servpro(r.party), is_amazon(r.party)])
    return pd.DataFrame(recs, columns=FEATURES)


@dataclass
class TimingModel:
    kind: str
    models: dict            # quantile -> fitted HistGradientBoostingRegressor
    stats: PartyStats
    n_train: int
    trained_through: str
    fallback_q: tuple       # global (q10, q50, q90) if a prediction cannot be made
    feats: list = field(default_factory=lambda: list(FEATURES))   # columns actually used (see fit)

    @classmethod
    def fit(cls, table: pd.DataFrame, kind: str, min_rows: int = 150) -> Optional["TimingModel"]:
        if table is None or len(table) < min_rows:
            return None
        table = table.sort_values("paid_on").reset_index(drop=True)
        stats = PartyStats(table)
        X = feature_frame(table, stats, as_of_known=True)
        # A column with fewer than 2 distinct values carries no information (e.g. 'terms' is empty for sales orders)
        # and makes some scikit-learn versions crash while binning, so it is left out.
        feats = [c for c in FEATURES if X[c].nunique(dropna=True) >= 2]
        X = X[feats]
        y = table["y"].clip(Y_MIN, Y_MAX).values
        age = (table["known_date"].max() - table["known_date"]).dt.days.values
        w = 0.5 ** (age / HALF_LIFE_DAYS)
        models = {}
        for q in QUANTILES:
            m = HistGradientBoostingRegressor(loss="quantile", quantile=q, max_depth=4, learning_rate=0.06,
                                              max_iter=250, min_samples_leaf=25, l2_regularization=1.0,
                                              random_state=42)
            m.fit(X, y, sample_weight=w)
            models[q] = m
        fb = tuple(float(np.quantile(y, q)) for q in QUANTILES)
        return cls(kind, models, stats, len(table), str(table["paid_on"].max().date()), fb, feats)

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        """rows: party, base_date, known_date, amount, terms.  Returns (n, 3) days for P10/P50/P90 (sorted)."""
        X = feature_frame(rows, self.stats, as_of_known=False)[self.feats]
        out = np.column_stack([self.models[q].predict(X) for q in QUANTILES])
        out.sort(axis=1)                                   # quantiles must not cross
        return np.clip(out, Y_MIN, Y_MAX)
