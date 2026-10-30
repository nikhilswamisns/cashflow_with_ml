"""Read-only Zoho Books pull -> normalized forecast snapshot.

Everything the forecast engine needs is collected here in ONE place and
normalized into plain dicts, so the engine never sees raw API shapes and the
same engine code can be tested on Zoho export files (tools/snapshot_from_exports.py).

Only GET requests are made. Nothing is written to Zoho.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from zoho.client import ZohoAPIError, ZohoClient
from zoho.fetch import _fetch_all_pages

logger = logging.getLogger("zoho.snapshot")


def _num(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _status(v: Any) -> str:
    return str(v or "").strip().lower().replace(" ", "_")


def _safe_list(client: ZohoClient, endpoint: str, key: str, params: dict) -> list[dict]:
    """List call that tolerates an unsupported status filter (returns [] and logs)."""
    try:
        return _fetch_all_pages(client, endpoint, key, params=params)
    except ZohoAPIError as e:  # e.g. a status value this org's API does not accept
        logger.warning("List %s %s failed: %s", endpoint, params, e)
        return []


def _detail(client: ZohoClient, endpoint: str, key: str, rec_id: str) -> dict:
    try:
        return client.get(f"{endpoint}/{rec_id}").get(key, {}) or {}
    except ZohoAPIError as e:
        logger.warning("Detail %s/%s failed: %s", endpoint, rec_id, e)
        return {}


def _uninvoiced_from_lines(total: float, lines: list[dict], qty_done_key: str) -> Optional[float]:
    """Share of the document total whose line quantities are not yet invoiced/billed."""
    full = 0.0
    open_ = 0.0
    for li in lines or []:
        qty = _num(li.get("quantity"))
        if qty <= 0:
            continue
        done = _num(li.get(qty_done_key)) + _num(li.get("quantity_cancelled"))
        line_total = _num(li.get("item_total")) or qty * _num(li.get("rate"))
        full += line_total
        open_ += line_total * max(qty - done, 0.0) / qty
    if full <= 0:
        return None
    return round(total * open_ / full, 2)


# ---------------------------------------------------------------- sections

def pull_invoices(client: ZohoClient) -> list[dict]:
    out: dict[str, dict] = {}
    wanted = {"sent", "overdue", "partially_paid", "unpaid", "viewed", "draft"}
    for st in ("unpaid", "draft"):
        for inv in _safe_list(client, "invoices", "invoices", {"status": st}):
            if _status(inv.get("status")) in wanted:
                out[inv.get("invoice_id") or inv.get("invoice_number")] = inv
    result = []
    for inv in out.values():
        status = _status(inv.get("status"))
        so_number = None
        if status == "draft":
            det = _detail(client, "invoices", "invoice", inv.get("invoice_id", ""))
            so_number = det.get("salesorder_number")
            if not so_number and det.get("salesorders"):
                so_number = (det["salesorders"][0] or {}).get("salesorder_number")
        result.append({
            "number": inv.get("invoice_number"),
            "customer": inv.get("customer_name"),
            "status": status,
            "date": inv.get("date"),
            "due_date": inv.get("due_date"),
            "total": _num(inv.get("total")),
            "balance": _num(inv.get("balance")) if status != "draft" else _num(inv.get("total")),
            "salesorder_number": so_number,
        })
    return result


def pull_sales_orders(client: ZohoClient) -> list[dict]:
    seen: dict[str, dict] = {}
    # 'overdue' = confirmed order whose expected shipment date has passed (still open in Zoho)
    wanted = {"confirmed", "open", "overdue", "draft", "partially_invoiced"}
    for st in ("confirmed", "overdue", "draft", "partially_invoiced"):
        for so in _safe_list(client, "salesorders", "salesorders", {"status": st}):
            # Zoho may ignore an unsupported status filter and return every order: keep only wanted ones
            if _status(so.get("status")) in wanted or _status(so.get("order_status")) in wanted:
                seen[so.get("salesorder_id")] = so
    result = []
    for so_id, so in seen.items():
        det = _detail(client, "salesorders", "salesorder", so_id) or so
        _sample("salesorder_detail", det)
        total = _num(det.get("total", so.get("total")))
        linked = [i for i in det.get("invoices", []) or [] if _status(i.get("status")) != "void"]
        if det.get("total_invoiced_amount") not in (None, ""):
            invoiced = _num(det.get("total_invoiced_amount"))
            uninv = round(total - invoiced, 2)
        elif linked:  # same basis as Zoho total_invoiced_amount: sum of linked (non-void) invoice totals
            invoiced = round(sum(_num(i.get("total")) for i in linked), 2)
            uninv = round(total - invoiced, 2)
        else:
            uninv = _uninvoiced_from_lines(total, det.get("line_items", []), "quantity_invoiced")
            uninv = total if uninv is None else uninv
            invoiced = round(total - uninv, 2)
        st = _status(det.get("status") or so.get("status"))
        result.append({
            "number": so.get("salesorder_number"),
            "customer": so.get("customer_name"),
            "status": "confirmed" if st == "overdue" else st,
            "date": so.get("date"),
            "shipment_date": det.get("shipment_date") or so.get("shipment_date") or None,
            "payment_terms_days": det.get("payment_terms"),
            "total": total,
            "invoiced": invoiced,
            "uninvoiced": uninv,
        })
    return result


def pull_purchase_orders(client: ZohoClient) -> list[dict]:
    seen: dict[str, dict] = {}
    wanted = {"open", "issued", "draft", "partially_billed"}
    for st in ("open", "draft", "partially_billed"):
        for po in _safe_list(client, "purchaseorders", "purchaseorders", {"status": st}):
            if _status(po.get("status")) in wanted or _status(po.get("order_status")) in wanted:
                seen[po.get("purchaseorder_id")] = po
    result = []
    for po_id, po in seen.items():
        det = _detail(client, "purchaseorders", "purchaseorder", po_id) or po
        total = _num(det.get("total", po.get("total")))
        unbilled = _uninvoiced_from_lines(total, det.get("line_items", []), "quantity_billed")
        accounts = sorted({li.get("account_name") for li in det.get("line_items", []) if li.get("account_name")})
        cf = {c.get("label"): c.get("value") for c in det.get("custom_fields", []) or []}
        result.append({
            "number": po.get("purchaseorder_number"),
            "vendor": po.get("vendor_name"),
            "status": _status(det.get("status") or po.get("status")),
            "date": po.get("date"),
            "delivery_date": det.get("delivery_date") or po.get("delivery_date") or None,
            "total": total,
            "unbilled": total if unbilled is None else unbilled,
            "payment_terms_days": det.get("payment_terms"),
            "payment_terms_label": det.get("payment_terms_label"),
            "cf_payment_term": cf.get("Payment Term(Formula)") or cf.get("Payment Term"),
            "accounts": accounts,
            "ordered_qty": sum(_num(li.get("quantity")) for li in det.get("line_items", [])),
            "received_qty": sum(_num(li.get("quantity_received") or li.get("received_quantity"))
                                for li in det.get("line_items", [])),
            "received_status": _status(det.get("received_status") or po.get("received_status") or ""),
        })
    return result


def pull_bills(client: ZohoClient) -> list[dict]:
    result = []
    for b in _safe_list(client, "bills", "bills", {"status": "unpaid"}):
        if _status(b.get("status")) not in {"open", "overdue", "partially_paid", "unpaid"}:
            continue
        det = _detail(client, "bills", "bill", b.get("bill_id", "")) or b
        accounts = sorted({li.get("account_name") for li in det.get("line_items", []) if li.get("account_name")})
        result.append({
            "number": b.get("bill_number"),
            "vendor": b.get("vendor_name"),
            "status": _status(b.get("status")),
            "date": b.get("date"),
            "due_date": b.get("due_date"),
            "total": _num(b.get("total")),
            "balance": _num(b.get("balance")),
            "reference": b.get("reference_number"),
            "accounts": accounts,
        })
    return result


def pull_accounts(client: ZohoClient) -> tuple[list[dict], list[dict]]:
    cash, cards = [], []
    for acc in client.get("bankaccounts").get("bankaccounts", []):
        row = {
            "account_id": acc.get("account_id"),
            "name": acc.get("account_name"),
            "type": _status(acc.get("account_type")),
            "balance": _num(acc.get("bcy_balance", acc.get("balance"))),
        }
        (cards if row["type"] == "credit_card" else cash).append(row)
    cash += _pull_named_cash_accounts(client, {(c["name"] or "").strip().lower() for c in cash})
    return cash, cards


def _pull_named_cash_accounts(client: ZohoClient, have: set) -> list[dict]:
    """Opening-cash accounts named in forecast_rules.json that are not bank accounts in Zoho (e.g. Stripe Clearing,
    an 'other current asset'): read their balance from the Chart of Accounts (read-only)."""
    try:
        import json as _json
        from pathlib import Path as _Path
        rules = _json.loads((_Path(__file__).resolve().parents[1] / "app" / "config" / "forecast_rules.json")
                            .read_text(encoding="utf-8"))
        wanted = {n.strip().lower(): n for n in rules["opening_cash"]["zoho_cash_account_names"]} 
    except Exception:
        return []
    missing = {k: v for k, v in wanted.items() if k not in have}
    if not missing:
        return []
    out = []
    try:
        accts = _fetch_all_pages(client, "chartofaccounts", "chartofaccounts", params={})
    except ZohoAPIError as e:
        logger.warning("Chart of accounts pull failed (%s) - %s not in opening cash", e, ", ".join(missing.values()))
        return []
    for a in accts:
        name = (a.get("account_name") or "").strip()
        if name.lower() not in missing:
            continue
        bal = a.get("current_balance")
        if bal is None:
            det = _detail(client, "chartofaccounts", "chart_of_account", a.get("account_id", ""))
            bal = det.get("current_balance", det.get("closing_balance"))
        if bal is None:
            logger.warning("No balance returned for %s - not in opening cash", name)
            continue
        out.append({"account_id": a.get("account_id"), "name": name,
                    "type": _status(a.get("account_type") or "other_current_asset"), "balance": _num(bal)})
    return out


_CARD_CHARGE = {"expense", "bill_payment", "vendor_payment", "owner_drawings", "card_charge", "debit"}
_CARD_PAYMENT = {"card_payment", "transfer_fund", "deposit", "bill", "payment"}
_CARD_REFUND = {"refund", "expense_refund", "vendor_credit_refund", "credit"}


def pull_card_transactions(client: ZohoClient, cards: list[dict], date_start: date, date_end: date) -> list[dict]:
    """Posted activity on each credit-card account between date_start and date_end (Banking module, read-only).

    Rows that do not belong to the card account or fall outside the cycle are dropped, so a filter the API
    ignores can never pull in company-wide activity.
    """
    out = []
    for card in cards:
        params = {"account_id": card["account_id"], "date.start": date_start.isoformat(),
                  "date.end": date_end.isoformat(), "filter_by": "Status.All"}
        rows = _safe_list(client, "banktransactions", "banktransactions", params)
        for t in rows[:3]:
            _sample("banktransaction", t)
        for t in rows:
            if t.get("account_id") and str(t.get("account_id")) != str(card["account_id"]):
                continue
            d = str(t.get("date") or t.get("transaction_date") or "")[:10]
            if not d or not (date_start.isoformat() <= d <= date_end.isoformat()):
                continue
            ttype = _status(t.get("transaction_type"))
            amt = abs(_num(t.get("amount")))
            if ttype in _CARD_PAYMENT:
                debit, credit, kind = amt, 0.0, "payment"
            elif ttype in _CARD_REFUND:
                debit, credit, kind = amt, 0.0, "refund"
            else:
                debit, credit, kind = 0.0, amt, "charge"
            out.append({
                "card": card["name"], "date": d, "type": kind if kind != "charge" else (ttype or "charge"),
                "details": next((v for v in (t.get("offset_account_name"), t.get("payee"), t.get("vendor_name"),
                                             t.get("customer_name"), t.get("description"), t.get("account_name"))
                                 if v and str(v).strip() != card["name"]), ""),
                "debit": debit, "credit": credit,
            })
    return out


_SAMPLES: dict[str, list] = {}


def _sample(kind: str, rec: dict) -> None:
    """Keep up to 3 raw API records per kind in the snapshot, to diagnose field-name differences."""
    lst = _SAMPLES.setdefault(kind, [])
    if len(lst) < 3:
        lst.append(rec)


def last_card_cycle(run_date: date, close_day: int, due_day: int = 20) -> tuple[date, date]:
    """(start, close) of the oldest card cycle whose statement is still unpaid at the run date.

    Run 9/25 -> cycle Aug 27 - Sep 26; run 10/2 -> the same cycle (its statement is due 10/20), not Sep 27 - Oct 26."""
    this_close = run_date.replace(day=close_day)
    closed = this_close if this_close <= run_date else (run_date.replace(day=1) - timedelta(days=1)).replace(day=close_day)
    due = (closed.replace(day=1) + timedelta(days=32)).replace(day=due_day)
    lands = due - timedelta(days=(due.weekday() - 4) % 7)
    close = closed if lands >= run_date else (closed.replace(day=1) + timedelta(days=32)).replace(day=close_day)
    prev = (close.replace(day=1) - timedelta(days=1)).replace(day=close_day)
    return prev + timedelta(days=1), close


def card_history_start(cycle_start: date, cycles_back: int = 2) -> date:
    """First day of the cycle `cycles_back` cycles before the one starting on cycle_start (same day of month)."""
    d = cycle_start
    for _ in range(cycles_back):
        d = (d.replace(day=1) - timedelta(days=1)).replace(day=cycle_start.day)
    return d


def pull_snapshot(client: ZohoClient, run_date: date, card_close_day: int = 26) -> dict:
    _SAMPLES.clear()
    print("Zoho sync: bank + card accounts...", flush=True)
    cash, cards = pull_accounts(client)
    start, close = last_card_cycle(run_date, card_close_day)
    # Card activity from the start of the two cycles before the unpaid one (outbound-freight card share over the last
    # three cycles) up to today (charges posted after the close belong to the next statement).
    hist_start, pulled_to = card_history_start(start), date.today()
    card_txns = pull_card_transactions(client, cards, hist_start, pulled_to)
    return {
        "source": "zoho_live_api",
        "run_date": run_date.isoformat(),
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "cash_accounts": cash,
        "card_accounts": cards,
        "card_cycle": {"start": start.isoformat(), "close": close.isoformat(),
                       "history_start": hist_start.isoformat(), "pulled_to": pulled_to.isoformat()},
        "card_transactions": card_txns,
        "invoices": _step("invoices", pull_invoices, client),
        "sales_orders": _step("sales orders", pull_sales_orders, client),
        "purchase_orders": _step("purchase orders", pull_purchase_orders, client),
        "bills": _step("bills", pull_bills, client),
        "_raw_samples": _SAMPLES,
    }


def _step(label: str, fn, client: ZohoClient) -> list[dict]:
    print(f"Zoho sync: {label}...", flush=True)
    rows = fn(client)
    print(f"Zoho sync: {label} done ({len(rows)})", flush=True)
    return rows
