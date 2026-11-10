"""Actual cash, read-only from Zoho: the opening-cash accounts' balance at a run's start and at the end of each past Friday.

Zoho's account ledger (chartofaccounts/transactions) lists every posting with its date. Starting from today's balance
and undoing the postings dated after a day gives that day's balance. It is the balance per today's books: entries
posted late with an earlier date change the past, so recent weeks can still move until the books are reconciled.

Zoho is slow (one call per page), so the account list and each account's ledger are fetched once and shared by every
run and by the forecast-vs-actual table for TTL_SECONDS. The ledger is read from LOOKBACK_DAYS back, or further if a run needs it.
"""
import json
import logging
import threading
import time
from datetime import date, timedelta

from app.ml import ROOT

log = logging.getLogger(__name__)
TTL_SECONDS = 600
LOOKBACK_DAYS = 70
_lock = threading.Lock()
_ACCOUNTS: list = [0.0, []]            # [fetched_at, accounts]
_LEDGERS: dict[str, tuple] = {}        # account_id -> (fetched_at, since, rows)


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
        batch, r = [], {}
        for attempt in range(3):
            r = client.get("chartofaccounts/transactions", params={"account_id": account_id, "page": page})
            batch = r.get("transactions") or []
            if batch or page > 1:
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


def _accounts_cached(client) -> list[dict]:
    if time.time() - _ACCOUNTS[0] > TTL_SECONDS or not _ACCOUNTS[1]:
        _ACCOUNTS[:] = [time.time(), _accounts(client)]
    return _ACCOUNTS[1]


def _ledger_cached(client, account_id: str, since: date) -> list[dict]:
    hit = _LEDGERS.get(account_id)
    if hit and time.time() - hit[0] < TTL_SECONDS and hit[1] <= since:
        return hit[2]
    rows = _ledger(client, account_id, since)
    _LEDGERS[account_id] = (time.time(), since, rows)
    return rows


def weekly_actuals(fridays: list[date], today: date | None = None, client=None, start: date | None = None) -> dict:
    """Points: the run's start (kind 'start'), each past Friday ('week_end') and today's balance ('today')."""
    today = today or date.today()
    past = sorted(f for f in set(fridays) if f <= today)
    days = sorted(set(past) | ({start} if start and start <= today else set()))
    if client is None:
        from zoho.client import ZohoClient
        client = ZohoClient()
    since = min([today - timedelta(days=LOOKBACK_DAYS)] + days)
    totals = {d: 0.0 for d in days}
    now_total = 0.0
    with _lock:   # one Zoho fetch at a time; concurrent requests then find the cache filled
        for acct in _accounts_cached(client):
            rows = _ledger_cached(client, acct["account_id"], since)
            for d, v in rebuild(acct["balance"], rows, days).items():
                totals[d] += v
            now_total += acct["balance"]
    pts = []
    if start and start in totals:
        pts.append({"date": start.isoformat(), "balance": round(totals[start], 2), "kind": "start"})
    pts += [{"date": d.isoformat(), "balance": round(totals[d], 2), "kind": "week_end"} for d in past]
    if not past or today != past[-1]:
        if start != today:
            pts.append({"date": today.isoformat(), "balance": round(now_total, 2), "kind": "today"})
    return {"points": pts, "as_of": today.isoformat(), "source": "Zoho ledger"}


def clear_cache() -> None:
    _ACCOUNTS[:] = [0.0, []]
    _LEDGERS.clear()
