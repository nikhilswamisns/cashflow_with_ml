"""Step 2: clean the invoices and build one row per month (the table the models will learn from)."""
import pandas as pd
from common import load_history, OUT

OUT.mkdir(exist_ok=True)
inv = load_history()["invoices"].copy()
inv["date"] = pd.to_datetime(inv["date"])
n_raw = len(inv)

# --- cleaning rules (each one is counted so nothing disappears silently) ---------------------
drops = {
    "void": inv.status.eq("void"),
    "draft": inv.status.eq("draft"),
    "zero total": inv.total.le(0),
}
keep = pd.Series(True, index=inv.index)
for name, mask in drops.items():
    print(f"  drop {name:<11}: {int((mask & keep).sum()):>4} invoices")
    keep &= ~mask
inv = inv[keep].copy()
print(f"  kept {len(inv)} of {n_raw} invoices, total ${inv.total.sum():,.0f}")

# --- segments: SERVPRO and Amazon are separate businesses in practice -------------------------
inv["segment"] = "Other"
inv.loc[inv.customer_name.str.contains("Amazon", case=False, na=False), "segment"] = "Amazon"
inv.loc[inv.customer_name.str.contains("SERVPRO", case=False, na=False), "segment"] = "SERVPRO"

# --- monthly table ------------------------------------------------------------------------------
m = inv.set_index("date").groupby("segment").total.resample("MS").sum().unstack(0).fillna(0)
m["Total"] = m.sum(axis=1)
m["invoices"] = inv.set_index("date").total.resample("MS").count()
m["customers"] = inv.set_index("date").customer_id.resample("MS").nunique()

# the last month is only part-way through (history ends 2026-10-07), so it must not be used
last_full = pd.Timestamp("2026-09-01")
partial = m.loc[m.index > last_full]
m = m.loc[m.index <= last_full]
print(f"\n  dropped partial month(s): {[d.strftime('%Y-%m') for d in partial.index]} (${partial.Total.sum():,.0f} so far)")

# --- calendar features -------------------------------------------------------------------------
m["month"] = m.index.month
m["quarter"] = m.index.quarter
m["t"] = range(len(m))          # time index, lets a model learn the growth trend

# --- checks ---------------------------------------------------------------------------------------
full = pd.date_range(m.index.min(), m.index.max(), freq="MS")
assert len(full) == len(m), "missing months"
assert abs(m.Total.sum() - (inv[inv.date <= "2026-09-30"].total.sum())) < 1, "monthly table does not add up to invoices"
print(f"\n  OK: {len(m)} months, {m.index.min():%Y-%m} to {m.index.max():%Y-%m}, no gaps, totals reconcile to the invoices")

pd.options.display.float_format = "{:,.0f}".format
print("\nLast 12 months:")
print(m[["SERVPRO", "Amazon", "Other", "Total", "invoices", "customers"]].tail(12).to_string())
print("\nYear totals ($):")
print(m.groupby(m.index.year)[["SERVPRO", "Amazon", "Other", "Total"]].sum().to_string())
print("\nMonth-of-year average share of the year's revenue (all years, rough seasonality):")
share = (m.Total / m.Total.groupby(m.index.year).transform("sum")).groupby(m.month).mean()
print((share * 100).round(1).to_string())

m.to_csv(OUT / "monthly_table.csv")
print("\nSaved ml_work/outputs/monthly_table.csv")
