"""Step 3: train several forecasting models on the past and test them on months they never saw.

Time-based split (never random): the model sees history up to an 'origin' month, forecasts the
following months in one go (like the weeks 14-52 problem), and is scored against what happened.
Two origins are used, so one lucky or unlucky stretch cannot decide the result.
"""
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from common import OUT

warnings.filterwarnings("ignore")
m = pd.read_csv(OUT / "monthly_table.csv", index_col=0, parse_dates=True)
y = m["Total"]
LOG = lambda s: np.log(np.asarray(s, dtype=float))


# ---- models: each takes (history series, horizon) and returns `horizon` forecasts -----------------
def same_month_last_year(h, n):               # baseline 1: no growth, no learning
    return np.array([h.iloc[-12 + (i % 12)] for i in range(n)])


def last_6_month_average(h, n):               # baseline 2: flat line at the recent level
    return np.repeat(h.iloc[-6:].mean(), n)


def linear_trend(window=None):
    def f(h, n):
        s = h if window is None else h.iloc[-window:]
        t = np.arange(len(s))
        b, a = np.polyfit(t, LOG(s), 1)        # straight line on log revenue = steady % growth
        return np.exp(a + b * (len(s) + np.arange(n)))
    return f


def holt_damped(h, n):
    fit = ExponentialSmoothing(LOG(h), trend="add", damped_trend=True).fit()
    return np.exp(fit.forecast(n))


def holt_winters(h, n):
    fit = ExponentialSmoothing(LOG(h), trend="add", damped_trend=True, seasonal="add", seasonal_periods=12).fit()
    return np.exp(fit.forecast(n))


def _lag_features(vals, month):
    v = np.asarray(vals, dtype=float)
    return [v[-1], v[-2], v[-3], v[-12], v[-3:].mean(), v[-12:].mean(), month]


def recursive_tree(make_model):
    """Learns revenue from its own recent past (lags, rolling means, month), then feeds its predictions back in."""
    def f(h, n):
        lv = list(LOG(h))
        idx = list(h.index)
        X = [_lag_features(lv[:i], idx[i].month) for i in range(12, len(lv))]
        mdl = make_model().fit(X, lv[12:])
        out = []
        d = idx[-1]
        for _ in range(n):
            d = d + pd.offsets.MonthBegin(1)
            p = float(mdl.predict([_lag_features(lv, d.month)])[0])
            lv.append(p); out.append(np.exp(p))
        return np.array(out)
    return f


def trend_plus_forest(h, n):
    """Straight-line growth + a forest that learns what is left over (month effects). Trees cannot extrapolate growth; the line does."""
    t = np.arange(len(h)); b, a = np.polyfit(t, LOG(h), 1)
    resid = LOG(h) - (a + b * t)
    feats = lambda d: [d.month, d.quarter]
    rf = RandomForestRegressor(200, min_samples_leaf=3, random_state=0).fit([feats(d) for d in h.index], resid)
    d = h.index[-1]; out = []
    for i in range(n):
        d = d + pd.offsets.MonthBegin(1)
        out.append(np.exp(a + b * (len(h) + i) + rf.predict([feats(d)])[0]))
    return np.array(out)


class AvgMLP:
    """Small neural network (2 hidden layers). 5 copies with different random starts are averaged, because one tiny network on ~50 points is unstable."""
    def __init__(self, seeds=5, hidden=(16, 8)):
        self.seeds, self.hidden = seeds, hidden

    def fit(self, X, y):
        self.sc = StandardScaler().fit(X)
        Xs = self.sc.transform(X)
        self.nets = [MLPRegressor(hidden_layer_sizes=self.hidden, activation="relu", solver="lbfgs", alpha=1e-2, max_iter=3000, random_state=k).fit(Xs, y)
                     for k in range(self.seeds)]
        return self

    def predict(self, X):
        Xs = self.sc.transform(X)
        return np.mean([n.predict(Xs) for n in self.nets], axis=0)


def _time_features(i, d):
    return [i, np.sin(2 * np.pi * d.month / 12), np.cos(2 * np.pi * d.month / 12)]


def neural_time(h, n):
    """Neural net that sees only the time index and month - has to learn the growth curve by itself."""
    X = [_time_features(i, d) for i, d in enumerate(h.index)]
    net = AvgMLP().fit(X, LOG(h))
    fi = pd.date_range(h.index[-1] + pd.offsets.MonthBegin(1), periods=n, freq="MS")
    return np.exp(net.predict([_time_features(len(h) + i, d) for i, d in enumerate(fi)]))


def trend_plus_net(h, n):
    """Straight-line growth (last 24 months) + a small neural net that learns only the month-of-year leftovers.
    The line carries the growth, so the net cannot run away the way the raw networks do."""
    w = h.iloc[-24:]; t = np.arange(len(w)); b, a = np.polyfit(t, LOG(w), 1)
    resid = LOG(w) - (a + b * t)
    feats = lambda d: [np.sin(2 * np.pi * d.month / 12), np.cos(2 * np.pi * d.month / 12)]
    net = AvgMLP(hidden=(4,)).fit([feats(d) for d in w.index], resid)
    fi = pd.date_range(w.index[-1] + pd.offsets.MonthBegin(1), periods=n, freq="MS")
    return np.exp(a + b * (len(w) + np.arange(n)) + net.predict([feats(d) for d in fi]))


MODELS = {
    "Same month last year (baseline)": same_month_last_year,
    "Last 6-month average (baseline)": last_6_month_average,
    "Linear growth trend (all history)": linear_trend(),
    "Linear growth trend (last 24 mo)": linear_trend(24),
    "Holt damped trend": holt_damped,
    "Holt-Winters (trend + season)": holt_winters,
    "Random forest (lags)": recursive_tree(lambda: RandomForestRegressor(300, min_samples_leaf=2, random_state=0)),
    "Gradient boosting (lags)": recursive_tree(lambda: GradientBoostingRegressor(random_state=0)),
    "Trend + forest on leftovers": trend_plus_forest,
    "Neural network (lags)": recursive_tree(AvgMLP),
    "Neural network (time + month)": neural_time,
    "Trend + neural net on leftovers": trend_plus_net,
}

# ---- evaluation ------------------------------------------------------------------------------------------
FOLDS = {"Fold A: learn to Dec 2024, predict 2025 (12 mo)": ("2024-12-01", 12),
         "Fold B: learn to Dec 2025, predict Jan-Sep 2026 (9 mo)": ("2025-12-01", 9)}
rows, preds = [], {}
for fold, (origin, n) in FOLDS.items():
    hist = y.loc[:origin]
    actual = y.loc[y.index > origin].iloc[:n]
    n = len(actual)
    for name, fn in MODELS.items():
        p = fn(hist, n)
        err = p - actual.values
        rows.append(dict(fold=fold[:6], model=name, MAE=np.abs(err).mean(), MAPE=100 * np.abs(err / actual.values).mean(),
                         total_error_pct=100 * err.sum() / actual.sum()))
        preds[(fold[:6], name)] = pd.Series(p, index=actual.index)
    preds[(fold[:6], "Actual")] = actual
res = pd.DataFrame(rows)
summary = res.pivot(index="model", columns="fold", values=["MAPE", "total_error_pct"])
summary["avg_MAPE"] = res.groupby("model").MAPE.mean()
summary = summary.sort_values("avg_MAPE")

pd.options.display.float_format = "{:,.1f}".format
print("MAPE = average % miss per month (lower is better).  total_error_pct = % over/under on the whole period's revenue.\n")
print(summary.to_string())
best = summary.index[0]
print(f"\nBest on average: {best}  (avg monthly miss {summary.avg_MAPE.iloc[0]:.0f}%)")
res.to_csv(OUT / "03_model_scores.csv", index=False)

# ---- charts ------------------------------------------------------------------------------------------------------
show = ["Same month last year (baseline)", "Linear growth trend (last 24 mo)", "Holt damped trend", "Random forest (lags)", "Trend + forest on leftovers", "Trend + neural net on leftovers"]
cols = ["#999999", "#d62728", "#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd"]
fig, ax = plt.subplots(2, 2, figsize=(14, 9))
for j, fold in enumerate(["Fold A", "Fold B"]):
    a = ax[0, j]
    hist_end = pd.Timestamp(list(FOLDS.values())[j][0])
    y.loc[hist_end - pd.DateOffset(months=18):hist_end].plot(ax=a, color="k", lw=1.5, label="history")
    preds[(fold, "Actual")].plot(ax=a, color="k", lw=2.5, marker="o", label="ACTUAL")
    for name, c in zip(show, cols):
        preds[(fold, name)].plot(ax=a, color=c, ls="--", marker=".", label=name)
    a.axvline(hist_end, color="grey", ls=":")
    a.set_title(list(FOLDS)[j]); a.set_ylabel("monthly revenue ($)")
    if j == 0: a.legend(fontsize=7)
s = summary["avg_MAPE"][::-1]
ax[1, 0].barh(s.index, s.values, color=["#2ca02c" if i == s.index[-1] else "#7f7f7f" for i in s.index])
ax[1, 0].set_title("Average monthly miss across both folds (MAPE %, lower = better)")
tot = summary["total_error_pct"].reindex(s.index)
tot.plot.barh(ax=ax[1, 1], width=.8)
ax[1, 1].axvline(0, color="k", lw=.8)
ax[1, 1].set_title("Bias: % error on total revenue (negative = under-forecast)\nFold A (blue) / Fold B (orange)")
ax[1, 1].set_yticklabels([])
ax[1, 1].set_ylabel("")
plt.tight_layout()
plt.savefig(OUT / "03_model_comparison.png", dpi=105)
print("\nSaved ml_work/outputs/03_model_comparison.png, 03_model_scores.csv")

# ---- chart 2: the headline test on the FULL history (train Oct 2021 - Dec 2025, predict 2026) ----------------
fig, a = plt.subplots(figsize=(13, 5.5))
a.axvspan(y.index.min(), pd.Timestamp("2025-12-31"), color="#1f77b4", alpha=.07, label="TRAINING data (Oct 2021 - Dec 2025)")
a.axvspan(pd.Timestamp("2026-01-01"), y.index.max() + pd.offsets.MonthEnd(0), color="#ff7f0e", alpha=.10, label="TEST months (Jan - Sep 2026, hidden from the models)")
a.plot(y.index, y.values, color="k", lw=1.6, marker="o", ms=3, label="actual revenue")
for name, c in zip(["Linear growth trend (last 24 mo)", "Holt damped trend", "Random forest (lags)", "Trend + forest on leftovers", "Trend + neural net on leftovers"], ["#d62728", "#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd"]):
    a.plot(preds[("Fold B", name)].index, preds[("Fold B", name)].values, color=c, ls="--", marker=".", lw=2, label=name)
a.set_title("Learn from the start to Dec 2025, then predict Jan-Sep 2026"); a.set_ylabel("monthly revenue ($)"); a.legend(fontsize=8, loc="upper left")
plt.tight_layout(); plt.savefig(OUT / "03_train_to_2025_predict_2026.png", dpi=110)
print("Saved ml_work/outputs/03_train_to_2025_predict_2026.png")
