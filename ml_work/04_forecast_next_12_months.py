"""Step 4: train the chosen model on ALL history and forecast the next 12 months, with a range.

Model: straight-line growth trend (on log revenue) fitted to the last 24 months - the best of 12 models in step 3.
Range: how far off that same model was in the two backtests (21 test months). Each past month gives a ratio
actual / forecast; the 10th and 90th percentile of those ratios scale today's forecast into a low and high case.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import OUT

m = pd.read_csv(OUT / "monthly_table.csv", index_col=0, parse_dates=True)
y = m["Total"]
WINDOW, HORIZON = 24, 12


def linear_trend(h, n, w=WINDOW):            # same model as step 3, written out so this script stands alone
    s = h.iloc[-w:]; t = np.arange(len(s))
    b, a = np.polyfit(t, np.log(s.values), 1)
    return np.exp(a + b * (len(s) + np.arange(n))), (np.exp(a + b * t), s.index), b


# ---- 1. how wrong was this model in the past? (the two backtests from step 3) ----------------------------
ratios = []
for origin, n in [("2024-12-01", 12), ("2025-12-01", 9)]:
    actual = y.loc[y.index > origin].iloc[:n]
    fc, _, _ = linear_trend(y.loc[:origin], len(actual))
    ratios += list(actual.values / fc)
ratios = np.array(ratios)
q10, q50, q90 = np.percentile(ratios, [10, 50, 90])
print(f"Backtest: {len(ratios)} months, actual/forecast ratio  P10={q10:.2f}  median={q50:.2f}  P90={q90:.2f}")
print(f"  actual beat the trend line in {(ratios > 1).sum()} of {len(ratios)} months")

# ---- 2. final model on everything --------------------------------------------------------------------------------------
fc, (fit, fit_idx), growth = linear_trend(y, HORIZON)
future = pd.date_range(y.index[-1] + pd.offsets.MonthBegin(1), periods=HORIZON, freq="MS")
out = pd.DataFrame({"trend_forecast": fc, "low_P10": fc * q10, "typical_P50": fc * q50, "high_P90": fc * q90}, index=future)
out.index.name = "month"
out.round(0).to_csv(OUT / "04_forecast_next_12_months.csv")

pd.options.display.float_format = "{:,.0f}".format
print(f"\nTrained on {y.index[0]:%b %Y} - {y.index[-1]:%b %Y} ({len(y)} months); trend fitted on the last {WINDOW}: "
      f"{fit_idx[0]:%b %Y} - {fit_idx[-1]:%b %Y}, growth {100 * (np.exp(growth) - 1):.1f}% per month")
print("\nNext 12 months ($):")
print(out.to_string())
last12 = y.iloc[-12:].sum()
print(f"\nLast 12 months actual : {last12:>12,.0f}")
print(f"Next 12 months trend  : {out.trend_forecast.sum():>12,.0f}   ({100 * (out.trend_forecast.sum() / last12 - 1):+.0f}% vs last 12)")
print(f"Next 12 months range  : {out.low_P10.sum():>12,.0f}  to  {out.high_P90.sum():,.0f}   (typical {out.typical_P50.sum():,.0f})")

# ---- 3. chart ----------------------------------------------------------------------------------------------------------------------
fig, a = plt.subplots(figsize=(13, 6))
a.plot(y.index, y.values, color="k", lw=1.5, marker="o", ms=3, label="actual monthly revenue")
a.plot(fit_idx, fit, color="#1f77b4", lw=2, label=f"trend fitted to last {WINDOW} months")
a.fill_between(out.index, out.low_P10, out.high_P90, color="#ff7f0e", alpha=.25, label="range (P10 - P90 of past forecast errors)")
a.plot(out.index, out.trend_forecast, color="#d62728", lw=2.5, ls="--", marker="o", ms=4, label="FORECAST (trend)")
a.plot(out.index, out.typical_P50, color="#ff7f0e", lw=1.5, ls=":", label="typical outcome (median of past errors)")
a.axvline(y.index[-1] + pd.offsets.MonthEnd(0), color="grey", ls=":")
a.text(out.index[0], a.get_ylim()[1] * .97, "  forecast ->", color="grey", va="top")
a.set_ylabel("monthly revenue ($)")
a.set_title("Revenue forecast, Oct 2026 - Sep 2027: growth trend with a range\n"
            f"In past tests the model was low in {(ratios > 1).sum()} of {len(ratios)} months; single months miss by about 20-30%", fontsize=11)
a.legend(loc="upper left", fontsize=9)
plt.tight_layout(); plt.savefig(OUT / "04_forecast_next_12_months.png", dpi=110)
print("\nSaved ml_work/outputs/04_forecast_next_12_months.png and 04_forecast_next_12_months.csv")
