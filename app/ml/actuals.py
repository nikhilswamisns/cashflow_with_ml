"""Actual cash, read-only from Zoho: the opening-cash accounts' balance at a run's start and at the end of each past Friday.

Zoho's account ledger (chartofaccounts/transactions) lists every posting with its date. Starting from today's balance
and undoing the postings dated after a day gives that day's balance. It is the balance per today's books: entries
posted late with an earlier date change the past, so recent weeks can still move until the books are reconciled.

Zoho is slow (one call per page), so the account list and the ledgers are read in parallel, once, and shared by every run
for TTL_SECONDS (then refreshed in the background). The ledger is read from LOOKBACK_DAYS back, or further if a run needs it.
"""
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from app.ml import ROOT

log = logging.getLogger(__name__)
TTL_SECONDS = 600
LOOKBACK_DAYS = 35
_lock = threading.Lock()
_STATE: dict = {"at": 0.0, "since": None, "accounts": [], "ledgers": {}, "refreshing": False}


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
        for attempt in range(2):   # Zoho sometimes returns an empty page that is fine a moment later
            r = client.get("chartofaccounts/transactions", params={"account_id": account_id, "page": page})
            batch = r.get("transactions") or []
            if batch:
                break
            time.sleep(0.4)
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


def _refresh(client, since: date) -> None:
    """Read the accounts and all their ledgers (in parallel: Zoho is one call per page) into the shared state."""
    accounts = _accounts(client)
    with ThreadPoolExecutor(max_workers=max(1, len(accounts))) as ex:
        rows = list(ex.map(lambda a: _ledger(client, a["account_id"], since), accounts))
    _STATE.update(at=time.time(), since=since, accounts=accounts,
                  ledgers={a["account_id"]: r for a, r in zip(accounts, rows)})


def _background_refresh(since: date) -> None:
    def work():
        try:
            from zoho.client import ZohoClient
            _refresh(ZohoClient(), since)
        except Exception as e:  # noqa: BLE001 - keep serving the older data
            log.warning("actuals refresh failed: %s", e)
        finally:
            _STATE["refreshing"] = False
    _STATE["refreshing"] = True
    threading.Thread(target=work, daemon=True, name="actuals-refresh").start()


def _data(client, need_since: date, today: date) -> dict:
    """Shared Zoho data covering `need_since`. Once it is older than TTL_SECONDS it is still served at once while a
    background refresh runs, so a visitor never waits for Zoho after the first load."""
    with _lock:
        covers = _STATE["since"] is not None and _STATE["since"] <= need_since
        if covers and time.time() - _STATE["at"] < TTL_SECONDS:
            return _STATE
        if covers:
            if not _STATE["refreshing"]:
                _background_refresh(min(need_since, today - timedelta(days=LOOKBACK_DAYS)))
            return _STATE
        _refresh(client, min(need_since, today - timedelta(days=LOOKBACK_DAYS)))
        return _STATE


def warm(client=None) -> None:
    """Fill the shared data at server start so the first dashboard load does not wait for Zoho."""
    today = date.today()
    if client is None:
        from zoho.client import ZohoClient
        client = ZohoClient()
    _data(client, today - timedelta(days=LOOKBACK_DAYS), today)


def weekly_actuals(fridays: list[date], today: date | None = None, client=None, start: date | None = None) -> dict:
    """Points: the run's start (kind 'start'), each past Friday ('week_end') and today's balance ('today')."""
    today = today or date.today()
    past = sorted(f for f in set(fridays) if f <= today)
    days = sorted(set(past) | ({start} if start and start <= today else set()))
    if client is None:
        from zoho.client import ZohoClient
        client = ZohoClient()
    state = _data(client, min(days + [today]), today)
    totals = {d: 0.0 for d in days}
    now_total = 0.0
    for acct in state["accounts"]:
        for d, v in rebuild(acct["balance"], state["ledgers"].get(acct["account_id"], []), days).items():
            totals[d] += v
        now_total += acct["balance"]
    pts = []
    if start and start in totals:
        pts.append({"date": start.isoformat(), "balance": round(totals[start], 2), "kind": "start"})
    pts += [{"date": d.isoformat(), "balance": round(totals[d], 2), "kind": "week_end"} for d in past if d != start]
    if not past or today != past[-1]:
        if start != today:
            pts.append({"date": today.isoformat(), "balance": round(now_total, 2), "kind": "today"})
    return {"points": pts, "as_of": today.isoformat(), "source": "Zoho ledger"}


def clear_cache() -> None:
    _STATE.update(at=0.0, since=None, accounts=[], ledgers={}, refreshing=False)
