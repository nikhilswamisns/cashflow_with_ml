"""Step 5: find a range (low / high band) that is honest - it should contain the real outcome about 80% of the time.

Walk-forward test: for every past forecast origin from Dec 2024 on, the band is built ONLY from forecast errors whose
outcome was already known at that origin, then checked against what happened next. Same trend model as step 4.
Methods compared:
  A  past errors, P10-P90 of actual/forecast   (what steps 4 / 4b used - it carries the past bias with it)
  B  symmetric +/- % around the trend          (size from the 80th percentile of past absolute % errors)
  C  past errors but re-centred on the trend   (keeps the spread, drops the bias)
  D  like A but only the last 12 months of errors (adapts when the bias changes)
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import OUT

m = pd.read_csv(OUT / "monthly_table.csv", index_col=0, parse_dates=True)
y = m["Total"]
W, H, TARGET = 24, 12, 0.80


def trend(h, n):
    s = h.iloc[-W:]; t = np.arange(len(s))
    b, a = np.polyfit(t, np.log(s.values), 1)
    return np.exp(a + b * (len(s) + np.arange(n))), (np.exp(a + b * t), s.index)


# every forecast ever made by this model (monthly origins) and what actually happened
rows = []
for oi in range(W - 1, len(y) - 1):
    n = min(H, len(y) - oi - 1)
    fc, _ = trend(y.iloc[:oi + 1], n)
    for k in range(n):
        rows.append((y.index[oi], y.index[oi + 1 + k], k + 1, y.iloc[oi + 1 + k] / fc[k]))
P = pd.DataFrame(rows, columns=["origin", "month", "h", "ratio"])


def band(method, pool, o):
    r = pool.ratio.values
    if method == "A":
        lo, hi = np.percentile(r, [10, 90])
    elif method == "B":
        k = np.percentile(np.abs(r - 1), 80); lo, hi = max(1 - k, .05), 1 + k
    elif method == "C":
        q10, q50, q90 = np.percentile(r, [10, 50, 90]); lo, hi = q10 / q50, q90 / q50
    elif method == "D":
        rec = pool[pool.month > o - pd.DateOffset(months=12)].ratio.values
        lo, hi = np.percentile(rec if len(rec) >= 10 else r, [10, 90])
    return lo, hi


NAMES = {"A": "A  past errors P10-P90 (steps 4/4b)", "B": "B  symmetric +/- %", "C": "C  past spread, re-centred", "D": "D  last 12 months of errors"}
recs = []
for o in sorted(P.origin.unique()):
    if o < pd.Timestamp("2024-12-01"):
        continue
    pool, test = P[P.month <= o], P[P.origin == o]
    for meth in NAMES:
        lo, hi = band(meth, pool, o)
        for _, r in test.iterrows():
            recs.append((meth, r.h, lo <= r.ratio <= hi, r.ratio < lo, r.ratio > hi, hi / lo))
R = pd.DataFrame(recs, columns=["method", "h", "inside", "below", "above", "width"])
R["hb"] = pd.cut(R.h, [0, 3, 7, 12], labels=["months 1-3", "months 4-7", "months 8-12"])
S = R.groupby("method").agg(coverage=("inside", "mean"), below=("below", "mean"), above=("above", "mean"), width_high_over_low=("width", "median"), n=("inside", "size"))
S = S.join(R.pivot_table(index="method", columns="hb", values="inside", aggfunc="mean"))
S.index = [NAMES[i] for i in S.index]
pd.options.display.float_format = "{:.2f}".format
print(f"Walk-forward coverage ({int(S.n.iloc[0])} forecast months per method, target {TARGET:.0%}; below/above = share of outcomes that fell outside):\n")
print(S.drop(columns="n").to_string())
best = min("ABCD", key=lambda k: (abs(S.loc[NAMES[k], "coverage"] - TARGET), S.loc[NAMES[k], "width_high_over_low"]))
print(f"\nClosest to {TARGET:.0%}: method {NAMES[best]}  (coverage {S.loc[NAMES[best], 'coverage']:.0%})")
S.to_csv(OUT / "05_range_methods.csv")

# ---- charts -----------------------------------------------------------------------------------------------------
fig, a = plt.subplots(figsize=(9, 4))
cols = ["#d62728" if k != best else "#2ca02c" for k in "ABCD"]
a.barh(list(S.index)[::-1], (S.coverage * 100).values[::-1], color=cols[::-1])
a.axvline(80, color="k", ls="--"); a.text(81, 0.1, "target 80%", fontsize=9)
a.set_xlabel("% of real outcomes that landed inside the band"); a.set_xlim(0, 100)
a.set_title("How honest is each range? (walk-forward, only past errors used)")
plt.tight_layout(); plt.savefig(OUT / "05_range_coverage.png", dpi=110)


def draw(origin, n, title, fname, actual=True):
    o = pd.Timestamp(origin)
    train = y.loc[:o]
    fc, (fit, fit_idx) = trend(train, n)
    lo, hi = band(best, P[P.month <= o], o)
    idx = pd.date_range(o + pd.offsets.MonthBegin(1), periods=n, freq="MS")
    f, a = plt.subplots(figsize=(13, 6.2))
    a.plot(train.index, train.values, color="k", lw=1.5, marker="o", ms=3, label="history the model saw")
    a.plot(fit_idx, fit, color="#1f77b4", lw=2, label=f"trend fitted to last {W} months")
    a.fill_between(idx, fc * lo, fc * hi, color="#2ca02c", alpha=.22, label=f"range: method {best}, built from errors known at the time")
    a.plot(idx, fc, color="#d62728", lw=2.5, ls="--", marker="o", ms=4, label="FORECAST (trend)")
    sub = ""
    if actual:
        act = y.reindex(idx)
        inside = ((act >= fc * lo) & (act <= fc * hi)).sum()
        a.plot(idx, act, color="k", lw=2.8, marker="o", ms=6, label="WHAT REALLY HAPPENED")
        sub = f"\nYear total: actual {act.sum() / 1e6:.1f}M vs forecast {fc.sum() / 1e6:.1f}M. Inside the range in {inside} of {n} months"
    a.axvline(o + pd.offsets.MonthEnd(0), color="grey", ls=":")
    a.set_ylabel("monthly revenue (USD)"); a.set_title(title + sub, fontsize=10.5); a.legend(loc="upper left", fontsize=9)
    plt.tight_layout(); plt.savefig(OUT / fname, dpi=110)
    return fc, lo, hi, idx


fc, lo, hi, idx = draw("2025-09-01", 12, "Backtest with the calibrated range: train on 4 years, forecast year 5", "05_backtest_new_range.png")
act = y.reindex(idx)
pd.DataFrame({"actual": act, "forecast": fc, "low": fc * lo, "high": fc * hi,
              "miss_pct": (act - fc) / act * 100, "inside_range": (act >= fc * lo) & (act <= fc * hi)},
             index=idx).round(1).to_csv(OUT / "05_backtest_new_range.csv")
print(f"\nBacktest band (built before Oct 2025): low = {lo:.2f} x trend, high = {hi:.2f} x trend")
fc, lo, hi, idx = draw("2026-09-01", 12, "Forecast Oct 2026 - Sep 2027 with the calibrated range", "05_forecast_new_range.png", actual=False)
pd.DataFrame({"trend_forecast": fc, "low": fc * lo, "high": fc * hi}, index=idx).round(0).to_csv(OUT / "05_forecast_new_range.csv")
print(f"Forecast band: low = {lo:.2f} x trend, high = {hi:.2f} x trend; next 12 months trend {fc.sum():,.0f}, range {fc.sum() * lo:,.0f} to {fc.sum() * hi:,.0f}")
print("\nSaved 05_range_coverage.png, 05_backtest_new_range.png, 05_forecast_new_range.png (+csv) in ml_work/outputs/")
