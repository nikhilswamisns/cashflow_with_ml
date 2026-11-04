"""Step 1 of the 4 Nov plan: weekly receipts, weeks 1-52, rules only vs rules plus the revenue forecast.

Known first, forecast fills the gap: for each calendar month,
    gap = max(0, monthly revenue forecast x share of the month inside the window - receipts the rules already show in that month)
and the gap is spread evenly over that month's forecast weeks. Receipts only (no costs). Read-only: the engine
and its Excel output are not touched.

Simplifications (stated on the chart): forecast revenue is invoice-month revenue and is treated as cash in the
same month (no payment lag); a week belongs to the month of its Friday.
"""
import calendar
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import OUT  # noqa: E402
from app import db  # noqa: E402
from app.engine.v10_engine import ROW_TOTAL_REVENUE  # noqa: E402
from app.output.v10_adapter import forecast_for_run  # noqa: E402

run = db.list_runs()[0]
f = forecast_for_run(run["run_id"])
fridays = f.fridays
rules = f.values[ROW_TOTAL_REVENUE]
docs = [0.0] * len(fridays)          # booked documents: open invoices and sales orders
for r in f.revenue:
    if r.week in fridays:
        docs[fridays.index(r.week)] += r.amount
runrate = [max(t - d, 0.0) for t, d in zip(rules, docs)]   # what is left: the flat reseller run-rate, other lines
fc = pd.read_csv(OUT / "05_forecast_new_range.csv", index_col=0, parse_dates=True)

# extend the log-linear trend past Sep 2027 so weeks 49-52 are covered: constant monthly growth factor, band = fixed multiples
while fc.index[-1] < pd.Timestamp(fridays[-1].year, fridays[-1].month, 1):
    nxt = fc.index[-1] + pd.offsets.MonthBegin(1)
    fc.loc[nxt] = fc.iloc[-1] * (fc.iloc[-1] / fc.iloc[-2])

by_month = defaultdict(list)
for i, d in enumerate(fridays):
    by_month[(d.year, d.month)].append(i)

added, low_add, high_add = [0.0] * len(fridays), [0.0] * len(fridays), [0.0] * len(fridays)
rows = []
for (y, m), idx in by_month.items():
    key = pd.Timestamp(y, m, 1)
    if key not in fc.index:
        continue
    booked = sum(rules[i] for i in idx)
    # only the share of the month that falls inside the window (Oct 2026 has 1 of its 5 Fridays)
    fridays_in_month = sum(1 for w in range(1, calendar.monthrange(y, m)[1] + 1) if calendar.weekday(y, m, w) == 4)
    share = len(idx) / fridays_in_month
    for col, arr in (("trend_forecast", added), ("low", low_add), ("high", high_add)):
        gap = max(0.0, float(fc.loc[key, col]) * share - booked)
        for i in idx:
            arr[i] = gap / len(idx)
    rows.append({"month": key.strftime("%Y-%m"), "weeks_in_window": len(idx), "rules_receipts": round(booked),
                 "revenue_forecast_in_window": round(float(fc.loc[key, "trend_forecast"]) * share), "added_by_forecast": round(added[idx[0]] * len(idx)),
                 "booked_documents": round(sum(docs[i] for i in idx)), "flat_run_rate": round(sum(runrate[i] for i in idx)),
                 "forecast_low_in_window": round(float(fc.loc[key, "low"]) * share),
                 "known_above_low_edge": booked > float(fc.loc[key, "low"]) * share})

table = pd.DataFrame(rows)
table.to_csv(OUT / "06_receipts_by_month.csv", index=False)
print(f"Run {run['run_id'][:8]} (week 1 = {fridays[0]})")
print(table.to_string(index=False))
tot_rules, tot_add = sum(rules), sum(added)
print(f"\n52-week receipts: rules {tot_rules:,.0f} | rules + forecast {tot_rules + tot_add:,.0f} | added {tot_add:,.0f}")

weeks = list(range(1, len(fridays) + 1))
comb = [r + a for r, a in zip(rules, added)]
BLUE, LIGHT, ORANGE = "#5b8def", "#a9c3f5", "#f0a43a"
fig, (ax, bx) = plt.subplots(2, 1, figsize=(12, 10.5), gridspec_kw={"height_ratios": [1.1, 1]})
money = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k")

ax.fill_between(weeks, [r + a for r, a in zip(rules, low_add)], [r + a for r, a in zip(rules, high_add)],
                color=ORANGE, alpha=0.15, label="Forecast range (low to high)")
ax.bar(weeks, docs, color=BLUE, label="Known: booked invoices and orders")
ax.bar(weeks, runrate, bottom=docs, color=LIGHT, label="Known: flat run-rate (an assumption)")
ax.bar(weeks, added, bottom=rules, color=ORANGE, alpha=0.9, label="Added by revenue forecast")
ax.axvline(13.5, color="grey", ls=":", lw=1)
ax.set_xlabel("Forecast week")
ax.set_ylabel("Weekly receipts ($)")
ax.yaxis.set_major_formatter(money)
ax.set_title("Weekly receipts, weeks 1 to 52: rules only vs rules plus revenue forecast")
ax.legend(loc="upper left", frameon=False, fontsize=9)

m = table.copy()
x = range(len(m))
bx.bar(x, m["booked_documents"], color=BLUE, label="Known: booked invoices and orders")
bx.bar(x, m["flat_run_rate"], bottom=m["booked_documents"], color=LIGHT, label="Known: flat run-rate")
bx.bar(x, m["added_by_forecast"], bottom=m["rules_receipts"], color=ORANGE, alpha=0.9, label="Added by revenue forecast")
bx.plot(x, m["revenue_forecast_in_window"], "k_", markersize=26, mew=2, label="Revenue forecast (month total)")
bx.plot(x, m["forecast_low_in_window"], marker="_", color="grey", ls="", markersize=26, mew=1.5, label="Forecast low edge")
for i, flag in enumerate(m["known_above_low_edge"]):
    if flag:
        bx.annotate("known above\nlow edge", (i, m["rules_receipts"][i]), ha="center", va="bottom", color="#c0392b", fontsize=8)
bx.set_xticks(list(x))
bx.set_xticklabels(m["month"], rotation=45, ha="right")
bx.yaxis.set_major_formatter(money)
bx.set_ylabel("Monthly receipts ($)")
bx.set_title("Month by month: what is known vs what the forecast adds (red flag = known beats the forecast's low edge)")
bx.legend(loc="upper left", frameon=False, fontsize=9)

fig.text(0.01, 0.005, "Forecast revenue treated as cash in the same month (no payment lag). Receipts only: costs not included.\n"
         "Weeks 49-52 extend the same trend past Sep 2027. Oct 2026 counts only its 1 week in the window.",
         fontsize=8, color="grey")
fig.tight_layout(rect=(0, 0.035, 1, 1))
fig.savefig(OUT / "06_receipts_rules_vs_forecast.png", dpi=130)
print("Months where known receipts beat the forecast low edge:", list(m.loc[m["known_above_low_edge"], "month"]) or "none")
print("Saved", OUT / "06_receipts_rules_vs_forecast.png")
