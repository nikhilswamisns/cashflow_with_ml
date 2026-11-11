"""Working capital: A/R and A/P aging, DSO / DPO, and customer concentration.

Open items come from the snapshot stored with a run (unpaid invoices and bills only). Aging counts days past the due
date as of the day Zoho was read; items not yet due are their own "Not due" bucket so the four requested buckets
(0-30, 31-60, 61-90, 90+) only hold items that are actually late.
DSO = A/R / last-90-day sales x 90 and DPO = A/P / last-90-day COGS x 90. The 90-day flows are not in the snapshot
(it holds unpaid items only); they come from app/zoho_flows.py and are None when Zoho could not be read.
"""
from datetime import date

from app.actions import SKIP_STATUS, _day

WINDOW = 90
BUCKETS = ["Not due", "0-30", "31-60", "61-90", "90+"]
FOCUS_CUSTOMER = "SERVPRO"
TOP_N = 5


def _open(rec: dict) -> bool:
    return float(rec.get("balance") or 0) > 0.005 and str(rec.get("status") or "").lower() not in SKIP_STATUS


def _bucket(days_late: int) -> str:
    if days_late <= 0:
        return "Not due"
    if days_late <= 30:
        return "0-30"
    if days_late <= 60:
        return "31-60"
    if days_late <= 90:
        return "61-90"
    return "90+"


def aging(rows: list[dict], as_of: date, party_key: str) -> dict:
    """Open balance and count per bucket, plus the total. Items with no due date count as Not due and are reported."""
    amt = {b: 0.0 for b in BUCKETS}
    cnt = {b: 0 for b in BUCKETS}
    no_due = 0
    for r in rows:
        if not _open(r):
            continue
        due = _day(r.get("due_date"))
        if due is None:
            no_due += 1
        b = _bucket((as_of - due).days) if due else "Not due"
        amt[b] += float(r["balance"])
        cnt[b] += 1
    total = sum(amt.values())
    return {"total": round(total, 2), "count": sum(cnt.values()), "missing_due_date": no_due,
            "buckets": [{"label": b, "amount": round(amt[b], 2), "count": cnt[b],
                         "share": round(amt[b] / total, 4) if total else 0.0} for b in BUCKETS]}


def _share_rows(totals: dict[str, float], focus: str | None) -> dict:
    grand = sum(totals.values())
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    top = [{"party": k, "amount": round(v, 2), "share": round(v / grand, 4) if grand else 0.0} for k, v in ranked[:TOP_N]]
    f = sum(v for k, v in totals.items() if focus and focus.lower() in k.lower())
    return {"total": round(grand, 2), "top": top,
            "top_share": round(sum(v for _, v in ranked[:TOP_N]) / grand, 4) if grand else 0.0,
            "focus_name": focus, "focus_amount": round(f, 2), "focus_share": round(f / grand, 4) if grand else 0.0}


def concentration(open_invoices: list[dict], sales_by_customer: dict[str, float] | None) -> dict:
    """Share of open A/R and of last-90-day invoiced sales held by the focus customer and the top five."""
    ar: dict[str, float] = {}
    for r in open_invoices:
        if _open(r):
            k = r.get("customer") or "Unknown"
            ar[k] = ar.get(k, 0.0) + float(r["balance"])
    return {"ar": _share_rows(ar, FOCUS_CUSTOMER),
            "sales": _share_rows(sales_by_customer, FOCUS_CUSTOMER) if sales_by_customer else None}


def days_ratio(balance: float, flow: float | None, window: int = WINDOW) -> float | None:
    """balance / flow x window, or None when the flow is unknown or not positive."""
    if flow is None or flow <= 0:
        return None
    return round(balance / flow * window, 1)


def build_working_capital(snapshot: dict, as_of: date, flows: dict | None) -> dict:
    flows = flows or {}
    ar = aging(snapshot.get("invoices", []), as_of, "customer")
    ap = aging(snapshot.get("bills", []), as_of, "vendor")
    return {"as_of": as_of.isoformat(), "window_days": WINDOW,
            "ar": ar, "ap": ap,
            "dso": days_ratio(ar["total"], flows.get("sales")),
            "dpo": days_ratio(ap["total"], flows.get("cogs")),
            "sales_90": flows.get("sales"), "cogs_90": flows.get("cogs"),
            "flows_available": bool(flows),
            "concentration": concentration(snapshot.get("invoices", []), flows.get("sales_by_customer"))}
