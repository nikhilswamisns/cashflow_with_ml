"""Compare a forecast run with a later refresh pull of the same week 1 ("Changes Since Run").

Both forecasts are built by the same engine, with the same rules and the same week 1, from two Zoho snapshots:
the run's own snapshot (the baseline, whose numbers stay in the main sheets) and a later read-only refresh pull.
Every difference therefore comes from Zoho data that changed between the two pulls.

The bridge explains the change in horizon-end cash exactly:
    change in opening cash
  + change in every receipt line (invoices / sales orders)            - item by item
  - change in every payment line (bills / purchase orders)            - item by item
  + change in the run-rate revenue rows, - change in the expense rows (normally 0)
  - change in card statements (row "Credit Card Payment Due") + change in card add-back (normally from card balances)
  - change in loan repayments (manual entries)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from app.engine.v10_engine import (COGS_3100, COGS_3101, COGS_3102, ROW_AMAZON, ROW_AR, ROW_CC_DEFERRED,
                                   ROW_CC_PAYMENT, ROW_ENDING, ROW_LOAN, ROW_RESELLERS, ROW_SERVPRO, ROW_TOTAL_COGS,
                                   ROW_TOTAL_REVENUE, TOTAL_ROWS, Forecast, fmt_md, revenue_row)

COGS_ROW = {COGS_3100: 18, COGS_3101: 19, COGS_3102: 20}
REVENUE_DETAIL_ROWS = (ROW_SERVPRO, ROW_AMAZON, ROW_AR)
RUNRATE_REVENUE_ROWS = tuple(r for r in TOTAL_ROWS[ROW_TOTAL_REVENUE] if r not in REVENUE_DETAIL_ROWS)
EXPENSE_TOTALS = tuple(t for t in TOTAL_ROWS if t not in (ROW_TOTAL_REVENUE, ROW_TOTAL_COGS))

# dataset -> (key field, party field, fields compared, area label)
DATASETS = {
    "invoices": ("number", "customer", ("status", "due_date", "total", "balance"), "Invoices"),
    "sales_orders": ("number", "customer", ("status", "date", "shipment_date", "total", "invoiced", "uninvoiced"),
                     "Sales orders"),
    "purchase_orders": ("number", "vendor", ("status", "date", "delivery_date", "payment_terms_days", "total", "unbilled",
                                             "received_status"), "Purchase orders"),
    "bills": ("number", "vendor", ("status", "due_date", "total", "balance"), "Bills"),
}
MONEY_FIELDS = {"total", "balance", "invoiced", "uninvoiced", "unbilled"}
GONE_TEXT = {"invoices": "No longer open in Zoho (paid, credited or voided)",
             "sales_orders": "No longer open in Zoho (fully invoiced, closed or cancelled)",
             "purchase_orders": "No longer open in Zoho (fully billed, closed or cancelled)",
             "bills": "No longer unpaid in Zoho (paid or voided)"}


@dataclass
class Comparison:
    run_pulled_at: str
    refresh_pulled_at: str
    week1: date
    fridays: list[date]
    summary: list[tuple] = field(default_factory=list)          # (label, run, refresh, kind)
    weekly: list[tuple] = field(default_factory=list)           # (week, run ending, refresh ending)
    bridge: list[tuple] = field(default_factory=list)           # (group, label, amount, note)
    bridge_total: float = 0.0
    horizon_change: float = 0.0
    blocks: dict[str, list[dict]] = field(default_factory=dict)  # area -> rows
    notes: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    cell_items: dict[tuple, list[dict]] = field(default_factory=dict)  # (cfm row, week index) -> drill-down items

    def to_json(self) -> dict:
        def j(v):
            if isinstance(v, date):
                return v.isoformat()
            if isinstance(v, (list, tuple)):
                return [j(x) for x in v]
            if isinstance(v, dict):
                return {k: j(x) for k, x in v.items()}
            return v
        return {"run_pulled_at": self.run_pulled_at, "refresh_pulled_at": self.refresh_pulled_at,
                "week1": self.week1.isoformat(), "summary": j(self.summary), "weekly": j(self.weekly),
                "bridge": j(self.bridge), "bridge_total": self.bridge_total, "horizon_change": self.horizon_change,
                "blocks": j(self.blocks), "notes": self.notes, "counts": self.counts}


# ----------------------------------------------------------------------------------------------- helpers
def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _fmt(field_name: str, v) -> str:
    if v in (None, ""):
        return "(blank)"
    if field_name in MONEY_FIELDS:
        return f"{_num(v):,.2f}"
    return str(v)


def _same(field_name: str, a, b) -> bool:
    if field_name in MONEY_FIELDS or field_name == "payment_terms_days":
        return abs(_num(a) - _num(b)) < 0.005
    return (a or "") == (b or "")


def _buckets(f: Forecast) -> dict[str, dict[tuple, float]]:
    """ref -> {(cfm row, week): signed cash amount} for every detail line the forecast carries (in or after window)."""
    out: dict[str, dict[tuple, float]] = {}
    for r in f.revenue:
        b = out.setdefault(r.ref, {})
        k = (revenue_row(r.source), r.week)
        b[k] = b.get(k, 0.0) + r.amount
    for r in f.cogs:
        b = out.setdefault(r.ref, {})
        k = (COGS_ROW.get(r.category, 18), r.week)
        b[k] = b.get(k, 0.0) - r.amount
    return out


def _detail_index(f: Forecast) -> dict[str, list]:
    idx: dict[str, list] = {}
    for r in list(f.revenue) + list(f.cogs):
        idx.setdefault(r.ref, []).append(r)
    return idx


def _excluded_refs(f: Forecast) -> dict[str, str]:
    return {r.ref: r.basis for r in f.excluded_bills}


def _weeks_txt(bk: dict[tuple, float], fridays: set) -> str:
    ws = sorted({w for (_, w) in bk})
    return ", ".join(fmt_md(w) + ("" if w in fridays else " (after window)") for w in ws) or "-"


def _in_window_total(bk: dict[tuple, float], fridays: set) -> float:
    return sum(v for (_, w), v in bk.items() if w in fridays)


# ----------------------------------------------------------------------------------------------- main
def compare(base_snap: dict, ref_snap: dict, base: Forecast, ref: Forecast,
            rules_changed_note: Optional[str] = None) -> Comparison:
    fr = set(base.fridays)
    n = len(base.fridays)
    c = Comparison(run_pulled_at=str(base_snap.get("pulled_at") or ""), refresh_pulled_at=str(ref_snap.get("pulled_at") or ""),
                   week1=base.run_date, fridays=list(base.fridays))
    if ref.run_date != base.run_date:
        c.notes.append(f"WARNING: the refresh has week 1 {fmt_md(ref.run_date)}, the run {fmt_md(base.run_date)}.")
    if rules_changed_note:
        c.notes.append(rules_changed_note)

    # ---------------- summary
    kb, kr = base.kpis, ref.kpis
    eb, er = base.values[ROW_ENDING], ref.values[ROW_ENDING]

    def neg_txt(k):
        neg = k["negative_weeks"]
        return f"{len(neg)}" + (f" ({fmt_md(neg[0])} to {fmt_md(neg[-1])})" if neg else "")

    def unbilled(s):
        return round(sum(_num(p.get("unbilled")) for p in s.get("purchase_orders", [])), 2)

    def cards(f):
        return round(sum(_num(x.get("balance")) for x in f.card_accounts), 2)

    def next_stmt(f):
        cyc = (f.card.get("cycles") or [{}])[0]
        return (f"{fmt_md(cyc['lands'])}: {cyc['total']:,.2f}" if cyc.get("lands") else "-"), _num(cyc.get("total"))

    c.summary = [
        ("Opening cash (Zoho cash + adjustments)", base.opening_cash, ref.opening_cash, "money"),
        (f"Week 1 ending cash (w/e {fmt_md(base.fridays[0])})", eb[0], er[0], "money"),
        (f"Week 2 ending cash (w/e {fmt_md(base.fridays[1])})", eb[1], er[1], "money"),
        (f"Week 3 ending cash (w/e {fmt_md(base.fridays[2])})", eb[2], er[2], "money"),
        ("Lowest point", kb["trough"], kr["trough"], "money"),
        ("Lowest point - week", fmt_md(kb["trough_week"]), fmt_md(kr["trough_week"]), "text"),
        ("Negative weeks", neg_txt(kb), neg_txt(kr), "text"),
        (f"Horizon end (w/e {fmt_md(base.fridays[-1])})", eb[-1], er[-1], "money"),
        ("Open A/R - unpaid invoices", kb["open_ar"], kr["open_ar"], "money"),
        ("Open A/R - number of unpaid invoices", kb["open_ar_count"], kr["open_ar_count"], "count"),
        ("Uninvoiced sales orders in the forecast", kb["so_total"], kr["so_total"], "money"),
        ("Open A/P - unpaid bills", kb["ap_total"], kr["ap_total"], "money"),
        ("Open A/P - number of unpaid bills", kb["ap_count"], kr["ap_count"], "count"),
        ("Unbilled purchase orders", unbilled(base_snap), unbilled(ref_snap), "money"),
        ("Credit card balances (all cards)", cards(base), cards(ref), "money"),
        ("Next card statement (lands w/e : amount)", next_stmt(base)[0], next_stmt(ref)[0], "text"),
    ]
    c.weekly = [(base.fridays[i], eb[i], er[i]) for i in range(min(13, n))]

    # ---------------- record-level changes + forecast effect
    bb, br = _buckets(base), _buckets(ref)
    ib, ir = _detail_index(base), _detail_index(ref)
    xb, xr = _excluded_refs(base), _excluded_refs(ref)
    handled: set[str] = set()
    blocks: dict[str, list[dict]] = {}
    cell_items: dict[tuple, list[dict]] = {}

    def effect_row(area, key, party, change, details, refkey):
        bk, rk = bb.get(refkey, {}), br.get(refkey, {})
        before_amt = sum(abs(v) for v in bk.values())
        after_amt = sum(abs(v) for v in rk.values())
        eff = round(_in_window_total(rk, fr) - _in_window_total(bk, fr), 2)
        note = ""
        if not bk and not rk:
            note = "Not in the forecast" + (f" - {xr.get(refkey) or xb.get(refkey)}" if (refkey in xr or refkey in xb) else "")
        elif abs(eff) < 0.005 and bk != rk:
            note = "Timing only" if _weeks_txt(bk, fr) != _weeks_txt(rk, fr) else ""
        elif abs(eff) < 0.005:
            note = "No cash effect"
        row = {"area": area, "ref": key, "party": party, "change": change, "details": details,
               "before_amount": round(before_amt, 2) if bk else None, "before_weeks": _weeks_txt(bk, fr) if bk else "-",
               "after_amount": round(after_amt, 2) if rk else None, "after_weeks": _weeks_txt(rk, fr) if rk else "-",
               "cash_effect": eff, "note": note}
        # drill-down items for the app's Difference view, in the row's own units (refresh minus run)
        for (cfm_row, w), v in bk.items():
            if w in fr and abs(rk.get((cfm_row, w), 0.0) - v) > 0.005:
                cell_items.setdefault((cfm_row, base.fridays.index(w)), []).append(
                    {"amount": round(-abs(v), 2), "label": f"Run: {change}",
                     "raw_ref": f"{key} ({party}) - was {abs(v):,.2f}"})
        for (cfm_row, w), v in rk.items():
            if w in fr and abs(bk.get((cfm_row, w), 0.0) - v) > 0.005:
                cell_items.setdefault((cfm_row, base.fridays.index(w)), []).append(
                    {"amount": round(abs(v), 2), "label": f"Refresh: {change}",
                     "raw_ref": f"{key} ({party}) - now {abs(v):,.2f}"})
        return row

    for ds, (kf, pf, fields, area) in DATASETS.items():
        rows = []
        mb = {str(x.get(kf)): x for x in base_snap.get(ds, []) if isinstance(x, dict)}
        mr = {str(x.get(kf)): x for x in ref_snap.get(ds, []) if isinstance(x, dict)}
        for key in sorted(set(mb) | set(mr)):
            a, b = mb.get(key), mr.get(key)
            party = str((b or a).get(pf) or "")
            if a is None:
                change = "New"
                details = "; ".join(f"{f_} {_fmt(f_, b.get(f_))}" for f_ in fields if b.get(f_) not in (None, ""))
            elif b is None:
                change = "No longer open"
                details = GONE_TEXT[ds] + f". Was: status {a.get('status')}" + (
                    f", {('balance' if 'balance' in a else 'amount')} {_fmt('total', a.get('balance', a.get('uninvoiced', a.get('unbilled'))))}")
            else:
                diffs = [f_ for f_ in fields if not _same(f_, a.get(f_), b.get(f_))]
                if not diffs:
                    continue
                partly = (ds in ("invoices", "bills") and _num(b.get("balance")) < _num(a.get("balance")) - 0.005
                          and _same("total", a.get("total"), b.get("total")))
                if partly:
                    change = "Partly paid"
                elif "status" in diffs:
                    change = f"Status {a.get('status')} → {b.get('status')}"
                elif any(f_ in MONEY_FIELDS for f_ in diffs):
                    change = "Amount changed"
                elif any("date" in f_ for f_ in diffs):
                    change = "Date changed"
                else:
                    change = "Changed"
                details = "; ".join(f"{f_} {_fmt(f_, a.get(f_))} → {_fmt(f_, b.get(f_))}" for f_ in diffs)
            rows.append(effect_row(area, key, party, change, details, key))
            handled.add(key)
        blocks[area] = rows

    # forecast lines that moved without a record change of their own (e.g. a sales order whose draft invoice changed)
    linked = []
    for key in sorted((set(bb) | set(br)) - handled):
        if bb.get(key) != br.get(key):
            r0 = (ir.get(key) or ib.get(key))[0]
            linked.append(effect_row("Linked changes", key, r0.party, "Forecast line changed",
                                     "Changed through a linked record (e.g. its invoice or parent order)", key))
    if linked:
        blocks["Linked changes"] = linked

    # opening cash per account
    acc_rows = []
    names = {(x.get("name") or ""): x for x in base_snap.get("cash_accounts", [])}
    names_r = {(x.get("name") or ""): x for x in ref_snap.get("cash_accounts", [])}
    used = {(x.get("name") or "").strip().lower() for x in base.cash_accounts} | {
        (x.get("name") or "").strip().lower() for x in ref.cash_accounts}
    for nm in sorted(set(names) | set(names_r)):
        a, b = _num((names.get(nm) or {}).get("balance")), _num((names_r.get(nm) or {}).get("balance"))
        if abs(a - b) > 0.005:
            inc = nm.strip().lower() in used
            acc_rows.append({"area": "Opening cash", "ref": nm, "party": "", "change": "Balance changed",
                             "details": f"{a:,.2f} → {b:,.2f}", "before_amount": round(a, 2), "before_weeks": "",
                             "after_amount": round(b, 2), "after_weeks": "", "cash_effect": round(b - a, 2) if inc else 0.0,
                             "note": "In opening cash" if inc else "Not in opening cash"})
    if abs(ref.opening_cash - base.opening_cash - (ref.zoho_cash - base.zoho_cash)) > 0.005:
        acc_rows.append({"area": "Opening cash", "ref": "Manual adjustment", "party": "", "change": "Changed",
                         "details": "", "before_amount": round(base.opening_cash - base.zoho_cash, 2), "before_weeks": "",
                         "after_amount": round(ref.opening_cash - ref.zoho_cash, 2), "after_weeks": "",
                         "cash_effect": round((ref.opening_cash - ref.zoho_cash) - (base.opening_cash - base.zoho_cash), 2),
                         "note": ""})
    blocks["Opening cash"] = acc_rows

    # credit cards: balances, statements, new transactions
    card_rows = []
    cb = {(x.get("name") or ""): _num(x.get("balance")) for x in base_snap.get("card_accounts", [])}
    cr = {(x.get("name") or ""): _num(x.get("balance")) for x in ref_snap.get("card_accounts", [])}
    for nm in sorted(set(cb) | set(cr)):
        if abs(cb.get(nm, 0) - cr.get(nm, 0)) > 0.005:
            card_rows.append({"area": "Credit cards", "ref": nm, "party": "", "change": "Balance changed",
                              "details": f"{cb.get(nm, 0):,.2f} → {cr.get(nm, 0):,.2f}", "before_amount": cb.get(nm, 0),
                              "before_weeks": "", "after_amount": cr.get(nm, 0), "after_weeks": "", "cash_effect": None,
                              "note": "Effect shown in the statement lines below"})
    def stmts(f):
        out: dict[date, float] = {}
        for x in f.card.get("cycles", []) + ([f.card["corp_row"]] if f.card.get("corp_row") else []):
            out[x["lands"]] = out.get(x["lands"], 0.0) + x["total"]
        return out
    sb, sr = stmts(base), stmts(ref)
    for lands in sorted(set(sb) | set(sr)):
        wk = fmt_md(lands)
        a, b = sb.get(lands, 0.0), sr.get(lands, 0.0)
        if abs(a - b) > 0.005:
            card_rows.append({"area": "Credit cards", "ref": f"Statement landing w/e {wk}", "party": "", "change": "Statement changed",
                              "details": f"{a:,.2f} → {b:,.2f}", "before_amount": round(a, 2), "before_weeks": wk,
                              "after_amount": round(b, 2), "after_weeks": wk, "cash_effect": None,
                              "note": "Cash effect included in the card line of the bridge"})

    def tx_key(t):
        return (t.get("card"), t.get("date"), t.get("details"), round(_num(t.get("debit")), 2), round(_num(t.get("credit")), 2))
    from collections import Counter
    # only the unpaid cycle onward: the earlier cycles (pulled for the outbound-freight card share) are history
    lo = str((base_snap.get("card_cycle") or {}).get("start") or "")
    tb = Counter(tx_key(t) for t in base_snap.get("card_transactions", []) if str(t.get("date") or "") >= lo)
    tr = Counter(tx_key(t) for t in ref_snap.get("card_transactions", []) if str(t.get("date") or "") >= lo)
    for k, cnt in (tr - tb).items():
        for _ in range(cnt):
            card_rows.append({"area": "Credit cards", "ref": f"{k[0]} {k[1]}", "party": k[2] or "", "change": "New card transaction",
                              "details": f"charge {k[4]:,.2f}" if k[4] else f"payment/refund {k[3]:,.2f}",
                              "before_amount": None, "before_weeks": "", "after_amount": k[4] or k[3], "after_weeks": "",
                              "cash_effect": None, "note": ""})
    for k, cnt in (tb - tr).items():
        for _ in range(cnt):
            card_rows.append({"area": "Credit cards", "ref": f"{k[0]} {k[1]}", "party": k[2] or "", "change": "Card transaction no longer in the pull",
                              "details": f"charge {k[4]:,.2f}" if k[4] else f"payment/refund {k[3]:,.2f}",
                              "before_amount": k[4] or k[3], "before_weeks": "", "after_amount": None, "after_weeks": "",
                              "cash_effect": None, "note": ""})
    blocks["Credit cards"] = card_rows

    # manual entries
    me_rows = []
    mb_ = {(m.get("label"), m.get("cfm_row"), str(m.get("week"))): m for m in base.manual_entries}
    mr_ = {(m.get("label"), m.get("cfm_row"), str(m.get("week"))): m for m in ref.manual_entries}
    for k in set(mb_) | set(mr_):
        a, b = mb_.get(k), mr_.get(k)
        if a is None or b is None or abs(a["amount"] - b["amount"]) > 0.005 or a["applied"] != b["applied"]:
            me_rows.append({"area": "Manual entries", "ref": k[0], "party": "", "change": "Added" if a is None else ("Removed" if b is None else "Changed"),
                            "details": (b or a)["status"], "before_amount": a["amount"] if a else None, "before_weeks": "",
                            "after_amount": b["amount"] if b else None, "after_weeks": "", "cash_effect": None, "note": ""})
    blocks["Manual entries"] = me_rows
    c.blocks = blocks
    c.cell_items = cell_items

    # ---------------- bridge (exact, horizon-end cash)
    def wsum(f, row):
        return sum(f.values[row][i] for i in range(n))

    d_open = round(ref.opening_cash - base.opening_cash, 2)
    rec = [r for area in DATASETS.values() for r in blocks.get(area[3], [])] + blocks.get("Linked changes", [])
    settled_kinds = ("No longer open", "Partly paid")
    gone_in = round(sum(r["cash_effect"] for r in rec if r["change"] in settled_kinds and r["area"] in ("Invoices", "Sales orders")), 2)
    gone_out = round(sum(r["cash_effect"] for r in rec if r["change"] in settled_kinds and r["area"] in ("Bills", "Purchase orders")), 2)
    new_in = round(sum(r["cash_effect"] for r in rec if r["change"] == "New" and r["area"] in ("Invoices", "Sales orders")), 2)
    new_out = round(sum(r["cash_effect"] for r in rec if r["change"] == "New" and r["area"] in ("Bills", "Purchase orders")), 2)
    other_rec = round(sum(r["cash_effect"] for r in rec if r["change"] not in ("New",) + settled_kinds), 2)
    d_runrate = round(sum(wsum(ref, r) - wsum(base, r) for r in RUNRATE_REVENUE_ROWS), 2)
    d_exp = round(-sum(wsum(ref, t) - wsum(base, t) for t in EXPENSE_TOTALS), 2)
    d_card = round(-(wsum(ref, ROW_CC_PAYMENT) - wsum(base, ROW_CC_PAYMENT)) + (wsum(ref, ROW_CC_DEFERRED) - wsum(base, ROW_CC_DEFERRED)), 2)
    d_loan = round(-(wsum(ref, ROW_LOAN) - wsum(base, ROW_LOAN)), 2)
    c.horizon_change = round(er[-1] - eb[-1], 2)
    settled = round(d_open + gone_in + gone_out, 2)
    c.bridge = [
        ("Settled activity", "Opening cash change (Zoho cash accounts)", d_open, "Cash that came in or went out between the two pulls"),
        ("Settled activity", "Receipts no longer open or partly collected (collected, credited, voided, fully invoiced)", gone_in,
         "Removed from the forecast; if collected, the cash is in the opening cash change above"),
        ("Settled activity", "Payments no longer open or partly paid (paid, voided, fully billed)", gone_out,
         "Removed from the forecast; if paid, the cash is in the opening cash change above"),
        ("Settled activity", "Settled activity - net", settled,
         "Close to 0 when the cash moved simply settled forecast items; otherwise the difference is cash not explained by them (e.g. deposits, uncategorized items)"),
        ("Real changes", "New receipts (new invoices / sales orders)", new_in, ""),
        ("Real changes", "New payments (new bills / purchase orders)", new_out, ""),
        ("Real changes", "Amount, status and date changes on existing items (incl. moves into / out of the window)", other_rec, ""),
        ("Real changes", "Credit card statements and card charges", d_card, "Card balances and card transactions changed"),
        ("Real changes", "Run-rate revenue rows", d_runrate, "Normally 0 (assumptions unchanged)"),
        ("Real changes", "Expense rows", d_exp, "Normally 0 (assumptions unchanged)"),
        ("Real changes", "Loan repayments / manual entries", d_loan, "Normally 0"),
    ]
    c.bridge_total = round(settled + new_in + new_out + other_rec + d_card + d_runrate + d_exp + d_loan, 2)
    if abs(c.bridge_total - c.horizon_change) > 0.05:
        c.notes.append(f"CHECK: the bridge totals {c.bridge_total:,.2f} but horizon-end cash changed by "
                       f"{c.horizon_change:,.2f} - difference {c.bridge_total - c.horizon_change:,.2f}.")
    c.counts = {area: len(rows) for area, rows in blocks.items()}
    return c


def rules_changed_note(archived_rules_path) -> Optional[str]:
    """Compare the rules file archived with the run against the current one."""
    try:
        from app.engine.v10_engine import RULES
        if archived_rules_path is None or not archived_rules_path.exists():
            return None
        if json.loads(archived_rules_path.read_text(encoding="utf-8")) != json.loads(RULES.read_text(encoding="utf-8")):
            return ("NOTE: forecast_rules.json has changed since the run was synced. Both sides of this comparison use the "
                    "current rules, so the differences below come from Zoho only.")
    except Exception:
        return None
    return None
