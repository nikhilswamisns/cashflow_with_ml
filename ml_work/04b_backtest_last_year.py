"""Step 4b: the same chart as step 4, but run in the PAST so we can see forecast vs what really happened.

Train on the first 4 years only (Oct 2021 - Sep 2025), forecast the 5th year (Oct 2025 - Sep 2026), then draw the
actual revenue on top. The range uses only errors that were already known at Sep 2025 (earlier test, Jan-Sep 2025).
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import OUT

m = pd.read_csv(OUT / "monthly_table.csv", index_col=0, parse_dates=True)
y = m["Total"]
WINDOW = 24
ORIGIN = pd.Timestamp("2025-09-01")


def linear_trend(h, n, w=WINDOW):
    s = h.iloc[-w:]; t = np.arange(len(s))
    b, a = np.polyfit(t, np.log(s.values), 1)
    return np.exp(a + b * (len(s) + np.arange(n))), (np.exp(a + b * t), s.index)


train, actual = y.loc[:ORIGIN], y.loc[y.index > ORIGIN]
n = len(actual)

# range: how wrong the same model was Jan-Sep 2025 (origin Dec 2024) - all of that was known before Oct 2025
past_actual = y.loc["2025-01-01":"2025-09-01"]
past_fc, _ = linear_trend(y.loc[:"2024-12-01"], len(past_actual))
ratios = past_actual.values / past_fc
q10, q50, q90 = np.percentile(ratios, [10, 50, 90])
print(f"Range learned before the test: {len(ratios)} months, actual/forecast  P10={q10:.2f}  median={q50:.2f}  P90={q90:.2f}")

fc, (fit, fit_idx) = linear_trend(train, n)
res = pd.DataFrame({"actual": actual.values, "forecast": fc, "low_P10": fc * q10, "typical_P50": fc * q50, "high_P90": fc * q90}, index=actual.index)
res["miss_$"] = res.actual - res.forecast
res["miss_%"] = 100 * res["miss_$"] / res.actual
res["inside_range"] = (res.actual >= res.low_P10) & (res.actual <= res.high_P90)
res["above_trend"] = res.actual > res.forecast
res.round(0).to_csv(OUT / "04b_backtest_last_year.csv")

pd.options.display.float_format = "{:,.0f}".format
print(f"\nTrained on {train.index[0]:%b %Y} - {train.index[-1]:%b %Y} ({len(train)} months = 4 years); forecast {actual.index[0]:%b %Y} - {actual.index[-1]:%b %Y}")
print(res[["actual", "forecast", "miss_$", "miss_%", "low_P10", "high_P90", "inside_range"]].to_string())
tot_a, tot_f = res.actual.sum(), res.forecast.sum()
print(f"\nYear total: actual ${tot_a:,.0f} | forecast ${tot_f:,.0f} | miss ${tot_a - tot_f:+,.0f} ({100 * (tot_a - tot_f) / tot_a:+.0f}% of actual)")
print(f"Average monthly miss {res['miss_%'].abs().mean():.0f}% | inside the P10-P90 range in {int(res.inside_range.sum())} of {n} months | actual above trend in {int(res.above_trend.sum())} of {n}")

fig, a = plt.subplots(figsize=(13, 6.2))
a.plot(train.index, train.values, color="k", lw=1.5, marker="o", ms=3, label="history the model saw (4 years)")
a.plot(fit_idx, fit, color="#1f77b4", lw=2, label=f"trend fitted to last {WINDOW} months")
a.fill_between(res.index, res.low_P10, res.high_P90, color="#ff7f0e", alpha=.25, label="range (P10 - P90, learned before the test)")
a.plot(res.index, res.forecast, color="#d62728", lw=2.5, ls="--", marker="o", ms=4, label="FORECAST made at Sep 2025")
a.plot(res.index, res.typical_P50, color="#ff7f0e", lw=1.5, ls=":", label="typical outcome")
a.plot(res.index, res.actual, color="k", lw=2.8, marker="o", ms=6, label="WHAT REALLY HAPPENED")
a.fill_between(res.index, res.forecast, res.actual, where=res.actual >= res.forecast, color="#d62728", alpha=.12, interpolate=True)
a.fill_between(res.index, res.forecast, res.actual, where=res.actual < res.forecast, color="#1f77b4", alpha=.18, interpolate=True)
a.axvline(ORIGIN + pd.offsets.MonthEnd(0), color="grey", ls=":")
a.set_ylabel("monthly revenue ($)")
a.set_title("Backtest: train on the first 4 years, forecast year 5, compare with reality\n"
            f"Year total: actual \\${tot_a / 1e6:.1f}M vs forecast \\${tot_f / 1e6:.1f}M ({100 * (tot_a - tot_f) / tot_a:+.0f}%). "
            f"Inside the range in {int(res.inside_range.sum())} of {n} months. Red shading = revenue came in above the forecast", fontsize=10.5)
a.legend(loc="upper left", fontsize=9)
plt.tight_layout(); plt.savefig(OUT / "04b_backtest_last_year.png", dpi=110)
print("\nSaved ml_work/outputs/04b_backtest_last_year.png and 04b_backtest_last_year.csv")
