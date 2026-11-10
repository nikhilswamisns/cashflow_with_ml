"""Actual cash, read-only from Zoho: the opening-cash accounts' balance at the end of each past Friday.

Zoho's account ledger (chartofaccounts/transactions) lists every posting with its date. Starting from today's balance
and undoing the postings dated after a day gives that day's balance. It is the balance per today's books: entries
posted late with an earlier date change the past, so recent weeks can still move until the books are reconciled.
"""
import json
import logging
import time
from datetime import date, timedelta

from app.ml import ROOT

log = logging.getLogger(__name__)
_CACHE: dict = {}
TTL_SECONDS = 600


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _day(t: dict) -> str:
    return str(t.get("transaction_date") or t.get("date") or "")[:10]


def rebuild(now_balance: float, rows: list[dict], days: list[date]) -> dict[date, float]:
    """Balance at the end of each day = balance now minus the net (debit - credit) of entries dated after it."""
    out = {}
    for d in days:
        after = sum(_num(t.get("debit_amount")) - _num(t.get("credit_amount")) for t in rows if _day(t) > d.isoformat())
        out[d] = round(now_balance - after, 2)
    return out


def _ledger(client, account_id: str, since: date) -> list[dict]:
    """Ledger rows from `since` to now, newest first, 200 per page, with a retry (Zoho sometimes returns an empty page)."""
    rows = []
    for page in range(1, 40):
        batch = []
        for attempt in range(3):
            r = client.get("chartofaccounts/transactions", params={"account_id": account_id, "page": page})
            batch = r.get("transactions") or []
            if batch or page == 1 and attempt == 2:
                break
            time.sleep(0.6)
        rows += batch
        more = (r.get("page_context") or {}).get("has_more_page")
        if not batch or not more or min(_day(t) for t in batch) < since.isoformat():
            break
    return [t for t in rows if _day(t) >= since.isoformat()]


def _accounts(client) -> list[dict]:
    from zoho.snapshot import pull_accounts
    wanted = {n.strip().lower() for n in json.loads((ROOT / "app" / "config" / "forecast_rules.json")
              .read_text(encoding="utf-8"))["opening_cash"]["zoho_cash_account_names"]}
    cash, _ = pull_accounts(client)
    return [a for a in cash if (a["name"] or "").strip().lower() in wanted and a.get("account_id")]


def weekly_actuals(fridays: list[date], today: date | None = None, client=None) -> dict:
    """{'points': [{'date', 'balance', 'kind'}], 'as_of'}: one point per past Friday plus today's balance."""
    today = today or date.today()
    past = sorted(f for f in set(fridays) if f <= today)
    key = (tuple(past), today)
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < TTL_SECONDS:
        return hit[1]
    if client is None:
        from zoho.client import ZohoClient
        client = ZohoClient()
    since = (past[0] if past else today) - timedelta(days=1)
    totals = {d: 0.0 for d in past + [today]}
    for acct in _accounts(client):
        rows = _ledger(client, acct["account_id"], since)
        for d, v in rebuild(acct["balance"], rows, past).items():
            totals[d] += v
        totals[today] += acct["balance"]
    pts = [{"date": d.isoformat(), "balance": round(totals[d], 2), "kind": "week_end"} for d in past]
    if not past or today != past[-1]:
        pts.append({"date": today.isoformat(), "balance": round(totals[today], 2), "kind": "today"})
    result = {"points": pts, "as_of": today.isoformat(), "source": "Zoho ledger"}
    _CACHE[key] = (time.time(), result)
    return result
