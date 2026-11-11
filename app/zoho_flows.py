"""Last-90-day sales (invoiced) and cost of goods sold, read live from Zoho Books, cached for TTL_SECONDS.

Used for DSO and DPO. Read-only. Any Zoho failure returns None so the page shows "not available" instead of a wrong number.
Sales are invoices dated in the window (not draft, not void). COGS is the Cost of Goods Sold section total of the
Zoho Profit and Loss report for the same window (accrual basis).
"""
import logging
import threading
import time
from datetime import date, timedelta

log = logging.getLogger(__name__)
TTL_SECONDS = 600
_lock = threading.Lock()
_CACHE: dict = {}  # window end date -> (read at, value)


def _find_total(nodes, name: str) -> float | None:
    """Total of the section called `name` anywhere in the P&L tree (Zoho nests Cost of Goods Sold under Gross Profit)."""
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        if str(n.get("name", "")).strip().lower() == name and n.get("total") is not None:
            return float(n["total"])
        for v in n.values():
            if isinstance(v, list):
                found = _find_total(v, name)
                if found is not None:
                    return found
    return None


def _cogs_from_report(report: dict) -> float | None:
    return _find_total(report.get("profit_and_loss"), "cost of goods sold")


def _sales(invoices: list[dict]) -> tuple[float, dict[str, float]]:
    total = 0.0
    by: dict[str, float] = {}
    for i in invoices:
        if str(i.get("status", "")).lower().replace(" ", "_") in {"draft", "void"}:
            continue
        v = float(i.get("total") or 0)
        total += v
        k = i.get("customer_name") or "Unknown"
        by[k] = by.get(k, 0.0) + v
    return round(total, 2), by


def read_flows(client, today: date, window: int = 90) -> dict:
    from zoho.fetch import fetch_invoices
    start, end = (today - timedelta(days=window)).isoformat(), today.isoformat()
    sales, by = _sales(fetch_invoices(client, params={"date_start": start, "date_end": end}))
    report = client.get("reports/profitandloss", params={"from_date": start, "to_date": end, "cash_based": "false"})
    return {"sales": sales, "sales_by_customer": by, "cogs": _cogs_from_report(report), "from": start, "to": end}


def get_flows(client=None, today: date | None = None) -> dict | None:
    """Flows for the 90 days ending `today` (default: today). Cached per end date for TTL_SECONDS."""
    today = today or date.today()
    with _lock:
        hit = _CACHE.get(today)
        if hit and time.time() - hit[0] < TTL_SECONDS:
            return hit[1]
        try:
            if client is None:
                from zoho.client import ZohoClient
                client = ZohoClient()
            value = read_flows(client, today)
        except Exception:
            log.exception("Could not read 90-day sales and COGS from Zoho")
            value = None
        _CACHE[today] = (time.time(), value)
        return value
