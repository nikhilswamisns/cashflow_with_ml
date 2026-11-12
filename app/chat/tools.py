"""The three read-only chat tools. Each returns plain dicts of real numbers, with where they came from.

cash_outlook          forecast cash for the coming week(s), from the run's matrix
customer_payments     what one customer has paid us, from the Zoho history, plus what they still owe (live open invoices)
rank_customers        who pays best: average days from due date to payment, from paid invoices in the Zoho history
working_capital       A/R and A/P aging, DSO / DPO, customer concentration (same numbers as the Working capital tab)
actions               overdue invoices to chase and bills to pay soon (same list as the Actions tab)
outflows_by_purpose   where forecast cash goes each week, grouped like the "Where cash goes" chart
"""
from __future__ import annotations

import difflib
from datetime import date, timedelta

import pandas as pd

from app.chat import history_store
from app.ml.history import invoice_table, norm

MIN_PAID_INVOICES = 5
MARKETPLACE_WORDS = ("amazon",)   # marketplace payouts are settlements, not a customer's payment behaviour
OPEN_STATUS_SKIP = {"draft", "void", "paid", "written_off"}


def cash_outlook(matrix: dict, today: date, weeks: int = 1, run_date: str | None = None, ml: dict | None = None) -> dict:
    """Forecast cash for the next `weeks` forecast weeks (weeks end on Fridays), starting with the week that contains today.
    `ml` is the rules-vs-ML comparison for the run; when given, each week also carries the AI-model ending cash and its range."""
    rows = matrix.get("weeks", [])
    upcoming = [w for w in rows if date.fromisoformat(w["week_ending_friday"]) >= today][:max(1, min(int(weeks), 13))]
    if not upcoming:
        return {"error": "The forecast has no weeks on or after today. Run a fresh Sync from Zoho."}
    first = date.fromisoformat(upcoming[0]["week_ending_friday"])
    out = [{"week_ending": w["week_ending_friday"], "opening_cash": w["opening_cash"], "money_in": w["total_revenue"],
            "ending_cash": w["ending_cash"],
            "money_out": round(w["opening_cash"] + w["total_revenue"] - w["ending_cash"], 2)} for w in upcoming]
    low = min(out, key=lambda w: w["ending_cash"])
    res = {"today": today.isoformat(), "forecast_start": matrix.get("forecast_start_friday"), "run": run_date,
           "this_week_ends": first.isoformat(), "weeks": out,
           "lowest_in_range": {"week_ending": low["week_ending"], "ending_cash": low["ending_cash"]},
           "note": "ending_cash is the forecast closing balance on the Friday that ends each week, according to our assumptions. "
                   "money_out is everything paid out that week."}
    if ml:
        at = {d: i for i, d in enumerate(ml.get("weeks", []))}
        for w in out:
            i = at.get(w["week_ending"])
            if i is not None:
                w["ending_cash_ml"] = ml["ending_cash_ml"][i]
                w["ml_range_low"], w["ml_range_high"] = ml["bands"]["p10"][i], ml["bands"]["p90"][i]
        withml = [w for w in out if "ending_cash_ml" in w]
        if withml:
            lm = min(withml, key=lambda w: w["ending_cash_ml"])
            res["lowest_in_range_ml"] = {"week_ending": lm["week_ending"], "ending_cash": lm["ending_cash_ml"]}
            res["note"] += (" ending_cash_ml is the same balance according to the AI model, which learns from how each customer has paid in the past; "
                            "ml_range_low/high is the AI model's likely range. The AI model does not give money in/out.")
    else:
        res["ml_note"] = "The AI model is not available right now; only our assumptions are shown."
    return res


def _match(name: str, names: list[str]) -> list[str]:
    q = norm(name)
    exact = [n for n in names if n == q]
    if exact:
        return exact
    contains = [n for n in names if q in n]
    if contains:
        return contains
    return difflib.get_close_matches(q, names, n=5, cutoff=0.6)


def customer_payments(name: str, open_invoices: list[dict] | None = None, history: dict | None = None) -> dict:
    """Total paid by one customer. When several customer names fit, the choices are returned instead of guessing."""
    h = history if history is not None else history_store.load()
    if h is None:
        return {"error": "The Zoho payment history file is not available on this server."}
    pay, inv = h["payments"], h["invoices"]
    labels = history_store.display_names(pd.concat([pay[["name", "customer_name"]], inv[["name", "customer_name"]]]))
    found = _match(name, sorted(labels))
    if not found:
        return {"error": f"No customer matching '{name}' in our data."}
    if len(found) > 1 and norm(name) not in found:
        allp = pay[pay["name"].isin(found)]
        return {"needs_choice": True, "total_matches": len(found), "matches": [labels[n] for n in found[:8]],
                "combined_paid_all_matches": round(float(allp["amount"].sum()), 2),
                "note": "More than one customer fits. Give the combined total if useful, and ask which one they mean."}
    key = found[0]
    p = pay[pay["name"] == key]
    i = inv[inv["name"] == key]
    i = i[~i["status"].isin(["draft", "void"])]
    out = {"customer": labels[key], "source": h["source"], "history_ends": h["last_date"],
           "total_paid": round(float(p["amount"].sum()), 2), "payments": int(len(p)),
           "first_payment": p["pdate"].min().date().isoformat() if len(p) else None,
           "last_payment": p["pdate"].max().date().isoformat() if len(p) else None,
           "total_invoiced": round(float(i["total"].sum()), 2), "invoices": int(len(i))}
    if open_invoices is not None:
        mine = [r for r in open_invoices if norm(r.get("customer")) == key
                and float(r.get("balance") or 0) > 0.005 and str(r.get("status") or "").lower() not in OPEN_STATUS_SKIP]
        out["open_now"] = {"count": len(mine), "balance": round(sum(float(r["balance"]) for r in mine), 2)}
    return out


def rank_customers(months: int = 24, top: int = 10, min_invoices: int = MIN_PAID_INVOICES,
                   include_marketplaces: bool = False, history: dict | None = None, today: date | None = None) -> dict:
    """Customers ranked by average days between invoice due date and payment (lower is better; negative = early)."""
    h = history if history is not None else history_store.load()
    if h is None:
        return {"error": "The Zoho payment history file is not available on this server."}
    raw = {"invoices": h["invoices"], "customer payments": h["payments"]}
    t = invoice_table(raw)
    if t.empty:
        return {"error": "No paid invoices with payment dates in the history."}
    cutoff = pd.Timestamp((today or date.today()) - timedelta(days=30 * int(months)))
    t = t[t["paid_on"] >= cutoff]
    if not include_marketplaces:
        t = t[~t["party"].str.contains("|".join(MARKETPLACE_WORDS))]
    labels = history_store.display_names(h["invoices"])
    g = t.groupby("party").agg(paid_invoices=("y", "size"), avg_days_to_pay=("y", "mean"),
                               on_time_share=("y", lambda s: float((s <= 0).mean())),
                               total_paid=("amount", "sum"))
    g = g[g["paid_invoices"] >= min_invoices].sort_values("avg_days_to_pay")
    rows = [{"rank": n, "customer": labels.get(k, k), "paid_invoices": int(r.paid_invoices),
             "avg_days_vs_due": round(float(r.avg_days_to_pay), 1), "paid_on_time_pct": round(100 * r.on_time_share),
             "total_paid": round(float(r.total_paid), 2)}
            for n, (k, r) in enumerate(g.head(max(1, min(int(top), 25))).iterrows(), 1)]
    return {"window_months": months, "marketplaces_excluded": not include_marketplaces, "min_paid_invoices": min_invoices, "customers_ranked": int(len(g)),
            "history_ends": h["last_date"], "best": rows,
            "slowest": [{"customer": labels.get(k, k), "avg_days_vs_due": round(float(r.avg_days_to_pay), 1),
                         "paid_invoices": int(r.paid_invoices)} for k, r in g.tail(3).iloc[::-1].iterrows()],
            "note": "avg_days_vs_due = days after the due date the invoice was paid (negative = paid early). Ranked best first."}


def working_capital(snapshot: dict | None, as_of: date, flows: dict | None) -> dict:
    if snapshot is None:
        return {"error": "This run has no open invoices and bills stored with it."}
    from app.working_capital import build_working_capital
    wc = build_working_capital(snapshot, as_of, flows)
    if not wc["flows_available"]:
        wc["note"] = "DSO, DPO and sales concentration need the last 90 days of Zoho sales and are not available right now."
    elif wc.get("flows_snapshot"):
        saved = (wc["flows_snapshot"].get("saved_at") or "an earlier date")[:10]
        wc["note"] = (f"Zoho could not be read just now, so DSO, DPO and sales concentration use the 90-day sales saved on {saved}. "
                      "They may be out of date. Say so when you give them.")
    return wc


def actions(snapshot: dict | None, as_of: date, limit: int = 10) -> dict:
    if snapshot is None:
        return {"error": "This run has no open invoices and bills stored with it."}
    from app.actions import build_actions
    limit = max(1, min(int(limit), 25))
    out = build_actions(snapshot, as_of, limit=500)
    # sums for the groupings people ask about, so the model never has to add bills up (and round) itself
    bills = out["bills"]["items"]
    for days in (3, 7):
        out["bills"][f"due_within_{days}_days"] = {
            "count": sum(1 for b in bills if b["days_overdue"] == 0 and b["days_until_due"] <= days),
            "total": round(sum(b["amount"] for b in bills if b["days_overdue"] == 0 and b["days_until_due"] <= days), 2)}
    for k in ("invoices", "bills"):
        out[k]["items"] = out[k]["items"][:limit]
        hidden = out[k]["items"] and out[k]["count"] - len(out[k]["items"])
        if hidden:
            rest = round(out[k]["total"] - sum(x["amount"] for x in out[k]["items"]), 2)
            out[k]["not_shown"] = {"count": hidden, "total": rest,
                                   "note": f"Only the first {len(out[k]['items'])} of {out[k]['count']} are listed. Say how many are not shown."}
    return out


def outflows_by_purpose(matrix: dict, today: date, weeks: int = 4) -> dict:
    """Money out per forecast week split into purposes (inventory, payroll, marketing, loans...). Payroll is an assumption."""
    from app.outflow_buckets import outflow_buckets
    rows = [w for w in matrix.get("weeks", []) if date.fromisoformat(w["week_ending_friday"]) >= today][:max(1, min(int(weeks), 13))]
    if not rows:
        return {"error": "The forecast has no weeks on or after today."}
    out, totals = [], {}
    for w in rows:
        total = round(w["opening_cash"] + w["total_revenue"] - w["ending_cash"], 2)
        b = outflow_buckets(w, total)
        out.append({"week_ending": w["week_ending_friday"], "total_out": total, "by_purpose": b})
        for k, v in b.items():
            totals[k] = round(totals.get(k, 0.0) + v, 2)
    return {"weeks": out, "totals_over_range": totals,
            "note": "Payroll lines are assumptions in the forecast, not Zoho actuals. 'Other' is everything not in a named purpose."}
