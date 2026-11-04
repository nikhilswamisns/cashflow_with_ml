"""Step 5b: which trend shape should the forecast use? Walk-forward test of three, all fitted on the last 24 months.

  A  log-linear   : straight line on log(revenue), so growth is a constant % per month (what steps 4 / 5 use)
  B  dollar-line  : straight line on revenue, so growth is a constant $ per month
  C  damped trend : Holt exponential smoothing on dollars where the trend fades out month by month

For every past month from Sep 2023 on, each trend is fitted using only data known then and forecasts up to 12 months ahead.
Scored on (1) every 1-12 month forecast, by horizon, and (2) the 12-month total, where a full 12 months of outcome exists.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from common import OUT

m = pd.read_csv(OUT / "monthly_table.csv", index_col=0, parse_dates=True)
y = m["Total"]
W, H = 24, 12


def log_linear(s, n):
    t = np.arange(len(s)); b, a = np.polyfit(t, np.log(s.values), 1)
    return np.exp(a + b * (len(s) + np.arange(n)))


def dollar_line(s, n):
    t = np.arange(len(s)); b, a = np.polyfit(t, s.values, 1)
    return np.maximum(a + b * (len(s) + np.arange(n)), 0)


def damped(s, n):
    fit = ExponentialSmoothing(s.values, trend="add", damped_trend=True, initialization_method="estimated").fit()
    return np.maximum(fit.forecast(n), 0)


MODELS = {"A log-linear": log_linear, "B dollar-line": dollar_line, "C damped trend": damped}

rows = []
for oi in range(W - 1, len(y) - 1):
    s = y.iloc[oi + 1 - W: oi + 1]
    n = min(H, len(y) - oi - 1)
    for name, f in MODELS.items():
        fc = f(s, n)
        for k in range(n):
            rows.append((name, y.index[oi], k + 1, y.iloc[oi + 1 + k], fc[k]))
D = pd.DataFrame(rows, columns=["model", "origin", "h", "actual", "forecast"])
D["pct"] = (D.forecast - D.actual) / D.actual * 100            # + means forecast too high
D["abs_pct"] = D.pct.abs()

# (1) monthly errors by horizon
bands = {"months 1-3": (1, 3), "months 4-7": (4, 7), "months 8-12": (8, 12), "all 1-12": (1, 12)}
S = pd.DataFrame({name: {b: D[(D.model == name) & D.h.between(*r)].abs_pct.mean() for b, r in bands.items()} for name in MODELS})
B = pd.DataFrame({name: {b: D[(D.model == name) & D.h.between(*r)].pct.mean() for b, r in bands.items()} for name in MODELS})
print("Average monthly miss, % (lower is better), all past forecast origins")
print(S.round(1).to_string())
print("\nAverage bias, % (+ = forecast too high, - = too low)")
print(B.round(1).to_string())

# (2) 12-month totals, only origins with a full 12 months of outcome
full = D[D.groupby(["model", "origin"]).h.transform("max") == H]
T = full.groupby(["model", "origin"]).agg(actual=("actual", "sum"), forecast=("forecast", "sum")).reset_index()
T["pct"] = (T.forecast - T.actual) / T.actual * 100
tot = T.groupby("model").agg(origins=("pct", "size"), avg_abs_miss_pct=("pct", lambda v: v.abs().mean()),
                             bias_pct=("pct", "mean"), worst_miss_pct=("pct", lambda v: v.abs().max()))
print("\n12-month total: how far off was each model, over all origins with a full year of outcome")
print(tot.round(1).to_string())
last = T[T.origin == T.origin.max()].set_index("model")
print(f"\nMost recent full test (forecast made {T.origin.max():%b %Y}): actual {last.actual.iloc[0]:,.0f}")
print(last.forecast.round(0).to_string())

# what each model says for the next 12 months
fut = {name: f(y.iloc[-W:], H) for name, f in MODELS.items()}
print("\nNext 12 months (Oct 2026 - Sep 2027) total:")
for name, v in fut.items():
    print(f"  {name:16s} {v.sum():>12,.0f}   ({v.sum() / y.iloc[-12:].sum() * 100 - 100:+.0f}% vs last 12 months)")

S.to_csv(OUT / "05b_trend_monthly_error.csv")
tot.to_csv(OUT / "05b_trend_12m_total_error.csv")
pd.DataFrame(fut, index=pd.date_range("2026-10-01", periods=H, freq="MS")).round(0).to_csv(OUT / "05b_trend_next_12.csv")

# chart
colors = {"A log-linear": "#d62728", "B dollar-line": "#1f77b4", "C damped trend": "#2ca02c"}
f, ax = plt.subplots(1, 3, figsize=(17, 5.2))
for name in MODELS:
    d = D[D.model == name].groupby("h").abs_pct.mean()
    ax[0].plot(d.index, d.values, marker="o", color=colors[name], label=name)
ax[0].set_title("Average monthly miss by months ahead (lower is better)"); ax[0].set_xlabel("months ahead"); ax[0].set_ylabel("% miss"); ax[0].legend()
for name in MODELS:
    t = T[T.model == name]
    ax[1].plot(t.origin, t.pct, marker="o", ms=3, color=colors[name], label=name)
ax[1].axhline(0, color="k", lw=.8); ax[1].set_title("12-month total: forecast vs actual, % (0 = perfect)"); ax[1].set_ylabel("% error"); ax[1].legend()
ax[2].plot(y.index[-36:], y.values[-36:], color="k", lw=1.8, label="actual")
idx = pd.date_range("2026-10-01", periods=H, freq="MS")
for name, v in fut.items():
    ax[2].plot(idx, v, ls="--", marker="o", ms=3, color=colors[name], label=f"{name}: {v.sum() / 1e6:.1f}M")
ax[2].set_title("Next 12 months under each trend"); ax[2].legend(loc="upper left", fontsize=9)
plt.tight_layout(); plt.savefig(OUT / "05b_trend_comparison.png", dpi=110)
print("\nSaved 05b_trend_comparison.png and three 05b_*.csv in ml_work/outputs/")
