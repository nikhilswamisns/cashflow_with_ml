"""This week's actions: which overdue invoices to chase and which bills to pay, from the open items stored with a run.

Invoices: overdue ones, biggest first by amount x days overdue.
Bills: due within WINDOW_DAYS (or already overdue). Overdue bills come first by amount x days overdue, then the
upcoming ones by due date (soonest first), then amount.
"Overdue" is judged on the day the data was pulled from Zoho (as_of), not on today, so an old run stays consistent.
"""
from datetime import date, datetime, timedelta

WINDOW_DAYS = 14
SKIP_STATUS = {"draft", "void", "paid", "written_off"}


def _day(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _open(rec: dict) -> bool:
    return float(rec.get("balance") or 0) > 0.005 and str(rec.get("status") or "").lower() not in SKIP_STATUS


def build_actions(snapshot: dict, as_of: date, window_days: int = WINDOW_DAYS, limit: int = 10) -> dict:
    inv = []
    for r in snapshot.get("invoices", []):
        due = _day(r.get("due_date"))
        if not _open(r) or due is None or due >= as_of:
            continue
        days = (as_of - due).days
        inv.append({"number": r.get("number"), "party": r.get("customer"), "due_date": due.isoformat(),
                    "days_overdue": days, "amount": round(float(r["balance"]), 2), "score": round(float(r["balance"]) * days, 2)})
    inv.sort(key=lambda x: (-x["score"], x["due_date"]))

    bills = []
    last = as_of + timedelta(days=window_days)
    for r in snapshot.get("bills", []):
        due = _day(r.get("due_date"))
        if not _open(r) or due is None or due > last:
            continue
        over = max((as_of - due).days, 0)
        bills.append({"number": r.get("number"), "party": r.get("vendor"), "due_date": due.isoformat(),
                      "days_overdue": over, "days_until_due": max((due - as_of).days, 0),
                      "amount": round(float(r["balance"]), 2), "score": round(float(r["balance"]) * over, 2)})
    bills.sort(key=lambda x: (0, -x["score"], x["due_date"]) if x["days_overdue"] else (1, x["due_date"], -x["amount"]))

    def pack(rows, **extra):
        return {"count": len(rows), "total": round(sum(x["amount"] for x in rows), 2), "items": rows[:limit], **extra}

    return {"as_of": as_of.isoformat(), "window_days": window_days,
            "invoices": pack(inv),
            "bills": pack(bills, overdue_count=sum(1 for b in bills if b["days_overdue"]),
                          overdue_total=round(sum(b["amount"] for b in bills if b["days_overdue"]), 2))}


def snapshot_date(snapshot: dict, run: dict) -> date:
    """The day the open items were read from Zoho."""
    d = _day(snapshot.get("pulled_at"))
    return d or datetime.fromisoformat(run["created_at"]).date()
