"""Step 1: look at the data before modelling anything."""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import load_history, OUT

OUT.mkdir(exist_ok=True)
x = load_history()

# ---- invoices: what counts as revenue? -------------------------------------------------
inv = x["invoices"].copy()
inv["date"] = pd.to_datetime(inv["date"])
print("Invoice status counts:", inv.status.value_counts().to_dict())
print("Zero/negative totals:", int((inv.total <= 0).sum()), "| duplicate invoice numbers:", int(inv.invoice_number.duplicated().sum()))
inv = inv[~inv.status.isin(["void", "draft"])]
inv["is_servpro"] = inv.customer_name.str.contains("SERVPRO", case=False, na=False)
inv["is_amazon"] = inv.customer_name.str.contains("Amazon", case=False, na=False)
inv["segment"] = "Other"
inv.loc[inv.is_amazon, "segment"] = "Amazon"
inv.loc[inv.is_servpro, "segment"] = "SERVPRO"

weekly = (inv.set_index("date").groupby("segment").total.resample("W-FRI").sum().unstack(0).fillna(0))
weekly["Total"] = weekly.sum(axis=1)
print("\nWeekly invoiced revenue: %d weeks (%s to %s)" % (len(weekly), weekly.index.min().date(), weekly.index.max().date()))
print("Zero-revenue weeks:", int((weekly.Total == 0).sum()))
print("Weekly total  mean %.0f | median %.0f | max %.0f (week %s)" % (
    weekly.Total.mean(), weekly.Total.median(), weekly.Total.max(), weekly.Total.idxmax().date()))
big = inv.nlargest(5, "total")[["date", "customer_name", "total"]]
print("\nFive biggest single invoices:\n", big.to_string(index=False))

# ---- cash: bank balance -----------------------------------------------------------------
b = x["bank transactions"].copy()
b["date"] = pd.to_datetime(b["date"])
chk = b[b.bank_account == "BUSINESS FUNDAMENTALS CHK"].sort_values(["date"])
bal = chk.groupby("date").running_balance.last()
print("\nChecking account: %d txns, %s to %s, balance now %.0f, min %.0f, max %.0f" % (
    len(chk), bal.index.min().date(), bal.index.max().date(), bal.iloc[-1], bal.min(), bal.max()))
print("Days with a transaction: %d of %d calendar days" % (len(bal), (bal.index.max() - bal.index.min()).days))

# ---- money in vs out by type ------------------------------------------------------------
b["year"] = b.date.dt.year
flow = b[b.bank_account == "BUSINESS FUNDAMENTALS CHK"].groupby(["year", "transaction_type"]).amount.sum().unstack(0).round(0)
print("\nChecking-account flow by type and year ($):\n", flow.to_string())

# ---- charts -----------------------------------------------------------------------------
fig, ax = plt.subplots(3, 1, figsize=(11, 10))
weekly[["SERVPRO", "Amazon", "Other"]].plot.area(ax=ax[0], alpha=.8)
ax[0].set_title("Weekly invoiced revenue by segment ($)")
weekly["Total"].rolling(13).mean().plot(ax=ax[1], color="k")
ax[1].set_title("Total weekly revenue, 13-week rolling average ($) - the trend")
bal.plot(ax=ax[2], lw=.8)
ax[2].set_title("Checking account balance, end of day ($)")
plt.tight_layout()
plt.savefig(OUT / "01_overview.png", dpi=110)
weekly.to_csv(OUT / "weekly_revenue_by_segment.csv")
print("\nSaved ml_work/outputs/01_overview.png and weekly_revenue_by_segment.csv")
