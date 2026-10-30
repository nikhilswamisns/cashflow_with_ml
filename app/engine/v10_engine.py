"""Deterministic weekly cash-flow engine that reproduces the v10 canonical workbook.

Input : a normalized Zoho snapshot (zoho/snapshot.py or tools/snapshot_from_exports.py)
        + app/config/forecast_rules.json
        + the assumption sheets of app/templates/v10_template.xlsx
          ('General Info' fixed amounts / tax schedule, 'Expense Assumptions' col E,
           'Revenue Detail' B6-B11 run-rate inputs)
Output: a Forecast object holding every detail row, every Cash Flow Model row value
        (and the Excel formula that produces it), the card roll-forward and the KPIs.

Cash Flow Model rows are the 1 Oct 2026 layout: row 10 = 1100.3 Amazon (new), so every row from Adjustments down is
one below its Version 10 number (Ending Cash = row 98).

Row timing follows the Assumptions & Rules sheet exactly as applied in v10:
  revenue ............ row 8 SERVPRO / row 10 Amazon / row 14 A/R Collection from Revenue Detail
  weekly ............. rows 9 (from week 5), 25, 26, 31 (rows 11-13 from week 2)
  biweekly ........... anchor 2026-08-21, every 14 days (rows 29,42,43,44,47,55-58,70)
  card cycle ......... Friday on/after the 15th (rows 24,27,28,32,39-41,45,46,52,53,59,64,72,76-81,83)
  1st Friday ......... rows 30, 51, 66, 90; interest $6,250 in Jun & Dec
  2nd Friday ......... row 60 (commission); row 30 outbound-freight card share
  2nd Tuesday-week ... row 87 (health insurance, Friday of that week)
  3rd / 4th Friday ... interest $250 / $1,000 (row 68)
  4th Friday April ... row 71 (accounting)
  last Friday ........ row 95 (loan repayment)
  tax dates .......... rows 88 / 89, Friday on/before Jan 15 / Apr 15 / Jun 15 / Sep 15 (past dates skipped)
  receipts ........... Friday ON OR AFTER the due / cash-in date
  payments ........... Friday ON OR BEFORE the due date; anything overdue -> week 1
"""
from __future__ import annotations

import calendar
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import openpyxl

ROOT = Path(__file__).parent.parent
TEMPLATE = ROOT / "templates" / "v10_template.xlsx"
RULES = ROOT / "config" / "forecast_rules.json"

COGS_3100 = "Cost of Goods Sold (3100)"
COGS_3101 = "Inbound Freight (3101)"
COGS_3102 = "Inbound Duty & Gov't Fees (3102)"


# ------------------------------------------------------------------ dates

def d(v: Any) -> Optional[date]:
    if v in (None, "", "None"):
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def fri_on_or_after(x: date) -> date:
    return x + timedelta(days=(4 - x.weekday()) % 7)


def fri_on_or_before(x: date) -> date:
    return x - timedelta(days=(x.weekday() - 4) % 7)


def first_open_cycle_close(run_date: date, close_day: int, due_day: int) -> date:
    """Close date of the oldest card cycle whose statement is still unpaid at the run date.

    The last cycle that has CLOSED on/before the run date is still owed if its statement lands (Friday on/before
    the due date) on/after the run date - e.g. run 10/2: the 9/26 statement is due 10/20 and lands w/e 10/16.
    Otherwise the first cycle is the one that closes next."""
    this_close = run_date.replace(day=close_day)
    closed = this_close if this_close <= run_date else (run_date.replace(day=1) - timedelta(days=1)).replace(day=close_day)
    due = (closed.replace(day=1) + timedelta(days=32)).replace(day=due_day)
    if fri_on_or_before(due) >= run_date:
        return closed
    return (closed.replace(day=1) + timedelta(days=32)).replace(day=close_day)


def nth_friday(y: int, m: int, n: int) -> date:
    return fri_on_or_after(date(y, m, 1)) + timedelta(weeks=n - 1)


def last_friday(y: int, m: int) -> date:
    return fri_on_or_before(date(y, m, calendar.monthrange(y, m)[1]))


def second_tuesday_week_friday(y: int, m: int) -> date:
    first_tue = date(y, m, 1) + timedelta(days=(1 - date(y, m, 1).weekday()) % 7)
    return first_tue + timedelta(days=7 + 3)


def fmt_md(x: date) -> str:
    return f"{x.month}/{x.day}/{x:%y}"


def money(x: float) -> str:
    return f"${x:,.2f}" if x >= 0 else f"-${-x:,.2f}"


# ------------------------------------------------------------ assumptions

_REF = re.compile(r"'General Info'!\$?B\$?(\d+)")


class Assumptions:
    """Numbers read from the template's General Info / Expense Assumptions / Revenue Detail."""

    def __init__(self, template: Path = TEMPLATE):
        wb = openpyxl.load_workbook(template)
        gi, ea, rd = wb["General Info"], wb["Expense Assumptions"], wb["Revenue Detail"]
        self.gi: dict[int, float] = {}
        for r in range(1, 45):
            v = gi.cell(r, 2).value
            if isinstance(v, (int, float)):
                self.gi[r] = float(v)
            elif isinstance(v, str):
                try:
                    self.gi[r] = float(v)
                except ValueError:
                    pass
        self.ea: dict[int, float] = {}
        self.ea_formula: dict[int, str] = {}
        for r in range(3, 47):
            v = ea.cell(r, 5).value
            if v is None:
                continue
            self.ea_formula[r] = str(v)
            self.ea[r] = self._eval(v)
        self.rd: dict[int, float] = {}
        for r in (6, 7, 9, 10, 11):
            self.rd[r] = float(rd.cell(r, 2).value)
        self.rd[8] = self.rd[6] / self.rd[7]

    def _eval(self, v: Any) -> float:
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s.startswith("="):
            return float(s)
        expr = _REF.sub(lambda m: repr(self.gi[int(m.group(1))]), s[1:])
        expr = expr.replace("MAX(", "max(")
        if not re.fullmatch(r"[0-9.+\-*/(), max]*", expr):
            raise ValueError(f"Unsupported assumption formula: {s}")
        return float(eval(expr, {"__builtins__": {}}, {"max": max}))


# ----------------------------------------------------------------- output

@dataclass
class DetailRow:
    source: str
    ref: str
    party: str
    basis: str
    amount: float
    week: date
    status: str = ""
    category: str = ""
    ml: Optional[dict] = None      # set only when ML timing was applied: {"p10","p50","p90","shift_days","kind"}


@dataclass
class Forecast:
    run_date: date
    fridays: list[date]
    snapshot_source: str
    pulled_at: str
    cash_accounts: list[dict]
    card_accounts: list[dict]
    zoho_cash: float
    manual_adjustments: list[dict]
    opening_cash: float
    revenue: list[DetailRow] = field(default_factory=list)
    held: list[DetailRow] = field(default_factory=list)
    cogs: list[DetailRow] = field(default_factory=list)
    excluded_bills: list[DetailRow] = field(default_factory=list)
    duckbill: list[dict] = field(default_factory=list)   # row 95 Duckbill lines: week, amount, source
    paid_since_prior: list[DetailRow] = field(default_factory=list)
    realised_since_prior: list[DetailRow] = field(default_factory=list)
    prior_info: Optional[dict] = None          # week 1 and pull time of the prior forecast compared against
    # Cash Flow Model: row -> list of (value, formula|None) per week
    cfm: dict[int, list[tuple[float, Optional[str]]]] = field(default_factory=dict)
    values: dict[int, list[float]] = field(default_factory=dict)
    card: dict[str, Any] = field(default_factory=dict)
    kpis: dict[str, Any] = field(default_factory=dict)
    exceptions: list[str] = field(default_factory=list)
    restatements: list[tuple] = field(default_factory=list)
    open_items: list[dict] = field(default_factory=list)
    v10_open_items: list[dict] = field(default_factory=list)
    fixed_items: list[dict] = field(default_factory=list)
    manual_entries: list[dict] = field(default_factory=list)
    assumptions: Optional[Assumptions] = None
    rules: dict = field(default_factory=dict)


# card-funded Cash Flow Model rows (Credit Card Payments Block A rows 5-26), in v10 order
CARD_ROWS = [(5, 24), (6, 27), (7, 28), (8, 32), (9, 39), (10, 40), (11, 41), (12, 45), (13, 46), (14, 47),
             (15, 51), (16, 52), (17, 53), (18, 59), (19, 64), (20, 76), (21, 77), (22, 78), (23, 79),
             (24, 80), (25, 81), (26, 83)]

# General Info row of the first MANUAL ENTRIES line (block title on row 48, column headers on row 49)
MANUAL_ENTRY_FIRST_GI_ROW = 50

# Cash Flow Model row numbers used by name elsewhere
ROW_SERVPRO, ROW_RESELLERS, ROW_AMAZON, ROW_AR = 8, 9, 10, 14
ROW_TOTAL_REVENUE, ROW_TOTAL_COGS, ROW_GROSS = 15, 21, 35
ROW_CC_PAYMENT, ROW_LOAN, ROW_CC_DEFERRED, ROW_ENDING = 94, 95, 96, 98

def revenue_row(source: str) -> int:
    """Cash Flow Model row a Revenue Detail line feeds, by its Source label."""
    if source.startswith("SERVPRO"):
        return ROW_SERVPRO
    if source.startswith("Amazon"):
        return ROW_AMAZON
    return ROW_AR


TOTAL_ROWS = {15: range(7, 15), 21: (18, 19, 20), 33: range(24, 33), 48: range(38, 48), 61: range(51, 61),
              73: range(64, 73), 84: range(76, 84), 91: range(87, 91)}


class V10Engine:
    def __init__(self, snapshot: dict, rules: Optional[dict] = None, assumptions: Optional[Assumptions] = None,
                 prior_snapshot: Optional[dict] = None):
        self.s = snapshot
        self.rules = rules or json.loads(RULES.read_text(encoding="utf-8"))
        self.a = assumptions or Assumptions()
        self.prior = prior_snapshot
        self.run_date = fri_on_or_before(d(snapshot["run_date"]))
        n = int(self.rules.get("window_weeks", 52))
        self.fridays = [self.run_date + timedelta(weeks=i) for i in range(n)]
        self.idx = {f: i for i, f in enumerate(self.fridays)}
        # ML timing layer (app/ml). Off unless forecast_rules.json has "ml": {"enabled": true}.
        self.ml = None
        self._ml_warning = None
        mlcfg = self.rules.get("ml") or {}
        if mlcfg.get("enabled"):
            try:
                from app.ml.predictor import MLTiming
                self.ml = MLTiming.load(mlcfg)
            except Exception as e:      # never break a forecast because of ML: fall back to the rules and say so
                self._ml_warning = f"ML timing is switched on but could not be used ({e}); the fixed rules were applied."

    # ------------------------------------------------------------ helpers
    def _ml_apply(self, row: "DetailRow", info: Optional[dict], kind: str) -> None:
        if not info:
            return
        row.ml = {**info, "kind": kind}
        word = {"inv": "customer's payment history", "so": "customer's order-to-cash history", "bill": "vendor's payment history"}[kind]
        row.basis += (f" | ML: expected {info['p50'].isoformat()} (P10 {info['p10'].isoformat()}, P90 {info['p90'].isoformat()}; "
                      f"{info['shift_days']:+d} d vs rule) from this {word}, {info['party_n']} past payments")

    def ml_receipt_invoice(self, inv: dict, due: date, amt: float):
        rule = self.receipt_week(due)
        if self.ml is None or due < self.run_date:          # overdue items stay in week 1 (rule)
            return rule, None
        info = self.ml.invoice(inv, due, amt, due)
        return (self.receipt_week(info["p50"]), info) if info else (rule, None)

    def ml_receipt_so(self, so: dict, ship: date, cash_in: date, amt: float):
        rule = self.receipt_week(cash_in)
        if self.ml is None:
            return rule, None
        info = self.ml.sales_order(so, ship, amt, cash_in)
        return (self.receipt_week(info["p50"]), info) if info else (rule, None)

    def ml_payment_bill(self, b: dict, due: date, amt: float):
        rule = self.payment_week(due)
        if self.ml is None or due < self.run_date:
            return rule, None
        info = self.ml.bill(b, due, amt, due)
        return (self.payment_week(info["p50"]), info) if info else (rule, None)
    def receipt_week(self, due: date) -> date:
        w = fri_on_or_after(due)
        return max(w, self.run_date)

    def payment_week(self, due: date) -> date:
        w = fri_on_or_before(due)
        return max(w, self.run_date)

    def in_window(self, w: date) -> bool:
        return w in self.idx

    def is_servpro(self, name: str) -> bool:
        return (name or "").strip() in self.rules["servpro_customer_names"]

    def is_amazon(self, name: str) -> bool:
        """Amazon marketplace customers (Assumptions & Rules row 7): customer name contains 'Amazon'."""
        n = (name or "").lower()
        return any(k.lower() in n for k in self.rules.get("amazon", {}).get("customer_name_contains", ["Amazon"]))

    # ------------------------------------------------------------ build
    def run(self) -> Forecast:
        f = self._opening()
        if self._ml_warning:
            f.exceptions.append(self._ml_warning)
        self._revenue(f)
        self._cogs(f)
        self._prior_compare(f)
        self._cash_flow_model(f)
        self._kpis(f)
        self._open_items(f)
        return f

    def _opening(self) -> Forecast:
        oc = self.rules["opening_cash"]
        names = [n.strip().lower() for n in oc["zoho_cash_account_names"]]
        # exactly the named accounts - no other Zoho account type can slip into opening cash
        cash = [c for c in self.s["cash_accounts"] if (c.get("name") or "").strip().lower() in names]
        zoho_cash = round(sum(c["balance"] for c in cash), 2)
        adj = [a for a in oc.get("manual_adjustments", []) if d(a.get("as_of")) is None or d(a["as_of"]) <= self.run_date]
        opening = round(zoho_cash + sum(a["amount"] for a in adj), 2)
        return Forecast(run_date=self.run_date, fridays=self.fridays, snapshot_source=self.s.get("source", ""),
                        pulled_at=self.s.get("pulled_at", ""), cash_accounts=cash, card_accounts=self.s["card_accounts"],
                        zoho_cash=zoho_cash, manual_adjustments=adj, opening_cash=opening, assumptions=self.a,
                        rules=self.rules)

    # ------------------------------------------------------------ revenue
    def _revenue(self, f: Forecast) -> None:
        R = self.rules
        inv_ok = set(R["invoices"]["include_statuses"])
        for inv in self.s["invoices"]:
            st = inv["status"]
            if st not in inv_ok:
                continue
            amt = inv["total"] if st == "draft" else inv["balance"]
            due = d(inv["due_date"])
            if amt <= 0 or due is None:
                if due is None:
                    f.exceptions.append(f"Invoice {inv['number']} has no due date - not forecast.")
                continue
            sp = self.is_servpro(inv["customer"])
            amz = (not sp) and self.is_amazon(inv["customer"])
            if st == "draft":
                so = f" from {inv['salesorder_number']}" if inv.get("salesorder_number") else ""
                basis = f"DRAFT invoice{so} — due {due.isoformat()}"
            else:
                basis = f"Due {due.isoformat()} ({st})"
            w, ml_info = self.ml_receipt_invoice(inv, due, amt)
            src = "SERVPRO Invoice" if sp else ("Amazon Invoice" if amz else "A/R Collection")
            row = DetailRow(src, inv["number"], inv["customer"], basis, round(amt, 2), w, st)
            self._ml_apply(row, ml_info, "inv")
            f.revenue.append(row)

        held = R.get("hold_for_client_review", {}).get("sales_orders", {})
        so_cfg = R["sales_orders"]
        for so in self.s["sales_orders"]:
            st = so["status"]
            sp = self.is_servpro(so["customer"])
            amz = (not sp) and self.is_amazon(so["customer"])
            ok = so_cfg["servpro_include_statuses"] if sp else so_cfg["reseller_include_statuses"]
            if st not in ok:
                continue
            amt = round(so["uninvoiced"], 2)
            if amt <= 0.005:
                continue
            days = (so_cfg["servpro_days_after_ship"] if sp else
                    int(self.rules.get("amazon", {}).get("days_after_ship", 30)) if amz else so_cfg["reseller_days_after_ship"])
            ship = d(so.get("shipment_date"))
            label = {"confirmed": "Open", "open": "Open", "overdue": "Open", "draft": "Draft SO",
                     "partially_invoiced": "Partially invoiced"}.get(st, st)
            if ship:
                cash_in = ship + timedelta(days=days)
                late = ", ship overdue" if ship < self.run_date and st != "draft" else ""
                basis = f"Ship {ship.isoformat()} +{days} → {cash_in.isoformat()}. {label}{late}"
            else:
                od = d(so["date"])
                cash_in = od + timedelta(days=days)
                basis = f"Order {od.isoformat()} +{days} → {cash_in.isoformat()}. NO SHIP DATE — order date +{days} — UNVERIFIED"
            if so["invoiced"] > 0.005:
                basis += (f". UNINVOICED REMAINDER: total {so['total']:,.2f} less {so['invoiced']:,.2f} invoiced")
            parent = so_cfg.get("parent_orders", {}).get(so["number"])
            fills_total = (sum(float(v) for v in parent.get("fills", {}).values()) if isinstance(parent, dict) else 0.0)
            if isinstance(parent, dict) and so["total"] < fills_total - 0.005:
                # Zoho already took the fills out of the parent (its total is now below the fills): forecast the
                # parent's own uninvoiced amount as it stands - deducting the fills again would drop it.
                basis = (f"PARENT ORDER — fills already removed from this order in Zoho (total now {so['total']:,.2f}, "
                         f"below the fills {fills_total:,.2f}); forecast as it stands. " + basis)
                parent = None
            if isinstance(parent, dict):
                parts = []
                for fill_so, fill_total in parent.get("fills", {}).items():
                    # the fill order's own total (closed, fully invoiced SO) - cross-checked against its invoices
                    val = round(float(fill_total), 2)
                    linked = [i for i in self.s["invoices"] if (i.get("salesorder_number") or "") == fill_so
                              and (i.get("status") or "") not in ("void", "voided")]
                    src = ", ".join(i["number"] for i in linked) if linked else "invoice not in this pull"
                    if linked and abs(sum(i["total"] for i in linked) - val) > 0.01:
                        f.exceptions.append(f"{so['number']}: partial fill {fill_so} is {val:,.2f} in the rules but its "
                                            f"open/draft invoices ({src}) total {sum(i['total'] for i in linked):,.2f} - check.")
                    parts.append((fill_so, val, src))
                amt = round(max(amt - sum(v for _, v, _ in parts), 0.0), 2)
                basis = ("PARENT ORDER — UNINVOICED REMAINDER ONLY. Total " + f"{so['total']:,.2f}" + " less partial fills "
                         "raised under their own order numbers: " + "; ".join(f"{a} {v:,.2f} ({src})" for a, v, src in parts)
                         + f" = {amt:,.2f}. " + basis)
                if amt <= 0.005:
                    continue
            so_week, ml_info = (self.ml_receipt_so(so, ship, cash_in, amt) if ship
                                else (self.receipt_week(cash_in), None))
            row = DetailRow("SERVPRO Sales Order" if sp else ("Amazon Sales Order" if amz else "A/R Sales Order"),
                            so["number"], so["customer"], basis,
                            amt, so_week, st)
            self._ml_apply(row, ml_info, "so")
            if so["number"] in held:
                row.basis = held[so["number"]]
                f.held.append(row)
            else:
                f.revenue.append(row)
        for r in f.revenue:
            if not self.in_window(r.week):
                f.exceptions.append(f"{r.ref} cash-in w/e {fmt_md(r.week)} falls after the forecast window - not in totals.")

    # --------------------------------------------------------------- cogs
    def cogs_category(self, vendor: str, accounts: list[str]) -> str:
        for k, v in self.rules["cogs_category_by_vendor"].items():
            if k.lower() in (vendor or "").lower():
                return v
        for a in accounts or []:
            for k, v in self.rules["cogs_category_by_account"].items():
                if k.lower() in a.lower():
                    return v
        return COGS_3100

    def is_duckbill(self, b: dict) -> bool:
        D = self.rules.get("duckbill") or {}
        if not D:
            return False
        v, accts = (b.get("vendor") or "").lower(), " ".join(b.get("accounts") or []).lower()
        return bool(D.get("vendor_contains") and D["vendor_contains"].lower() in v) or \
            bool(D.get("account_contains") and D["account_contains"].lower() in accts)

    def _duckbill(self, f: Forecast, put) -> None:
        """Row 95 Duckbill repayment: open Zoho bills on the 1st Friday of the month after the bill date (overdue -> week 1),
        then General Info B32 on the 1st Friday of every later month through the end month."""
        D = self.rules.get("duckbill") or {}
        if not D:
            return
        gi_row = int(D.get("general_info_row", 32))
        monthly = self.a.gi.get(gi_row, 0.0)
        ey, em = (int(x) for x in str(D.get("end_month", "2099-12")).split("-"))
        covered = set()
        for b in getattr(self, "_duckbill_bills", []):
            bd = d(b.get("date")) or d(b.get("due_date"))
            ny, nm = (bd.year + (bd.month // 12), bd.month % 12 + 1)
            covered.add((ny, nm))
            wk = max(nth_friday(ny, nm, 1), self.run_date)
            amt = round(b["balance"], 2)
            if wk not in self.idx:
                continue
            formula = f"='General Info'!$B${gi_row}" if abs(amt - monthly) < 0.005 else f"={amt}"
            if abs(amt - monthly) >= 0.005:
                f.exceptions.append(f"Duckbill bill {b['number']} is {money(amt)}, not the monthly {money(monthly)} "
                                    "(General Info B32) - the bill amount is used.")
            put(ROW_LOAN, self.idx[wk], amt, formula)
            f.duckbill.append({"week": wk, "amount": amt, "source": f"Zoho bill {b['number']}"})
        for x in self.fridays:
            if nth_friday(x.year, x.month, 1) != x or (x.year, x.month) in covered or (x.year, x.month) > (ey, em):
                continue
            put(ROW_LOAN, self.idx[x], monthly, f"='General Info'!$B${gi_row}")
            f.duckbill.append({"week": x, "amount": monthly, "source": "Schedule (General Info B32)"})

    def _cogs(self, f: Forecast) -> None:
        B = self.rules["bills"]
        self._duckbill_bills = []
        card_vendors = [v.lower() for v in B["card_statement_vendors"]]
        f.card["corp_bill"] = None
        f.card["statement_bills"] = []
        plat_acct = self.rules["credit_cards"]["platinum_name_contains"].lower()
        for b in self.s["bills"]:
            if b["status"] not in B["include_statuses"] or b["balance"] <= 0:
                continue
            due = d(b["due_date"]) or d(b["date"])
            vend = b["vendor"] or ""
            if any(cv in vend.lower() or cv in (b["number"] or "").lower() for cv in card_vendors):
                f.card["corp_bill"] = {"number": b["number"], "balance": b["balance"], "due": due}
                continue
            if any(plat_acct in (a or "").lower() for a in b.get("accounts", [])):
                # Zoho moves the Amex Platinum statement into A/P as a bill posted to the card account. Creating the
                # bill shows as a "payment" on the card, but no cash has left: it leaves when the bill is paid. The
                # open balance is the statement still due (Credit Card Payments B31, Cash Flow Model row 94).
                f.card["statement_bills"].append({"number": b["number"], "balance": round(b["balance"], 2),
                                                  "total": round(b.get("total") or b["balance"], 2),
                                                  "date": d(b["date"]), "due": due})
                row = DetailRow("Bill", b["number"], vend, "", round(b["balance"], 2), self.payment_week(due),
                                {"overdue": "Overdue", "partially_paid": "PartiallyPaid"}.get(b["status"], "Open"), "")
                row.basis = (f"Due {due.isoformat()}. Amex Platinum statement bill - paid on Cash Flow Model row 94 "
                             "(Credit Card Payments B31), not in COGS")
                f.excluded_bills.append(row)
                continue
            if self.is_duckbill(b):
                # Client decision 6 Oct 2026: paid on Cash Flow Model row 95 (1st Friday of the month after the bill date)
                self._duckbill_bills.append(b)
                row = DetailRow("Bill", b["number"], vend, "", round(b["balance"], 2), self.payment_week(due),
                                {"overdue": "Overdue", "partially_paid": "PartiallyPaid"}.get(b["status"], "Open"), "")
                row.basis = (f"Due {due.isoformat()}. Duckbill repayment (IP rights payable) - paid on Cash Flow Model "
                             "row 95 (Loan Repayments), 1st Friday of the month after the bill date")
                f.excluded_bills.append(row)
                continue
            excl = next((why for k, why in B["excluded_vendors"].items() if k.lower() in vend.lower()), None)
            is_cogs = any(any(k in a.lower() for k in B["cogs_accounts_keywords"]) for a in b.get("accounts", []))
            if not b.get("accounts"):
                is_cogs = True  # no line detail available: treat as supplier bill (v10 behaviour)
            if excl is None and not is_cogs:
                excl = f"Non-COGS bill ({', '.join(b['accounts'])}) - implicit in the Expense Assumptions run-rates"
            bill_week, ml_info = self.ml_payment_bill(b, due, b["balance"])
            row = DetailRow("Bill", b["number"], vend, "", round(b["balance"], 2), bill_week,
                            {"overdue": "Overdue", "partially_paid": "PartiallyPaid"}.get(b["status"], "Open"),
                            self.cogs_category(vend, b.get("accounts", [])))
            if excl:
                row.basis = f"Due {due.isoformat()}. {excl}"
                f.excluded_bills.append(row)
                if excl.startswith("Non-COGS bill"):
                    f.restatements.append((f"{b['number']} {vend} — excluded from COGS", -row.amount,
                                           f"{excl} (same treatment as the Prudent 3PL bills; v10 carried it in COGS)"))
            else:
                row.basis = f"Bill-confirmed — due {due.isoformat()}"
                self._ml_apply(row, ml_info, "bill")
                f.cogs.append(row)

        P = self.rules["purchase_orders"]
        for po in self.s["purchase_orders"]:
            if po["status"] not in P["include_statuses"]:
                continue
            amt = round(po["unbilled"], 2)
            if amt <= 0.005:
                continue
            # Timing rule (Assumptions & Rules row 13, "Supplier terms"): every open PO is dated from its
            # delivery date (or PO date, UNVERIFIED) + the Zoho supplier Payment Terms (Net 30/60/90, Due on
            # Receipt = 0), whether or not goods have been received. Received quantity is shown for information.
            received = (float(po.get("received_qty") or 0) > 0
                        or po.get("received_status") in ("received", "partially_received"))
            cf = str(po.get("cf_payment_term") or "").strip("' ")
            cf_days = int(cf) if cf.lstrip("-").isdigit() else None
            terms = P["terms_override_days"].get(po["number"], po.get("payment_terms_days"))
            terms_lbl = po.get("payment_terms_label") or (f"Net {terms}" if terms is not None else "")
            if terms is None:
                terms = P["default_terms_days"]
                terms_lbl = f"default +{terms} (no Zoho terms)"
            if received:
                terms_lbl += " (goods received)"
            deliv = d(po.get("delivery_date"))
            base = deliv or d(po["date"])
            due = base + timedelta(days=int(terms))
            draft = "Draft PO — " if po["status"] == "draft" else ""
            what = f"Delivery {fmt_md(deliv)}" if deliv else f"PO {fmt_md(d(po['date']))} (no delivery date)"
            basis = f"PO-estimate — {draft}{what} + {terms_lbl}"
            basis += f" → due {due.isoformat()}"
            if not deliv:
                basis += " — UNVERIFIED"
            if due < self.run_date:
                basis += " (overdue, clamped to wk 1)"
            if po["unbilled"] < po["total"] - 0.005:
                basis += f" — unbilled balance of {po['total']:,.2f}"
            if cf_days is not None and cf_days != int(terms):
                cf_week = self.payment_week(base + timedelta(days=cf_days))
                if cf_week != self.payment_week(due):
                    f.restatements.append((f"{po['number']} {po['vendor']} — Zoho supplier terms {terms_lbl} used "
                                           f"(custom field says {cf} days)", amt,
                                           f"Pays w/e {fmt_md(self.payment_week(due))} instead of w/e {fmt_md(cf_week)} "
                                           "(Assumptions & Rules row 13: supplier terms)"))
            f.cogs.append(DetailRow("PO", po["number"], po["vendor"], basis, amt, self.payment_week(due),
                                    "Open/Draft PO", self.cogs_category(po["vendor"], po.get("accounts", []))))
        for r in f.cogs:
            if not self.in_window(r.week):
                f.exceptions.append(f"{r.ref} payment w/e {fmt_md(r.week)} falls after the forecast window - not in totals.")

    # --------------------------------------------------------------- prior
    def _prior_compare(self, f: Forecast) -> None:
        if not self.prior:
            return
        f.prior_info = {"week1": d(self.prior.get("run_date")), "pulled_at": str(self.prior.get("pulled_at") or "")[:16]}
        cur_bills = {b["number"] for b in self.s["bills"]}
        for b in self.prior.get("bills", []):
            if b["number"] not in cur_bills and b["balance"] > 0:
                f.paid_since_prior.append(DetailRow("Bill", b["number"], b["vendor"],
                                                    "No longer unpaid in Zoho - cash is inside the opening balance",
                                                    b["balance"], self.run_date, "Paid / closed"))
        cur_inv = {i["number"] for i in self.s["invoices"]}
        for i in self.prior.get("invoices", []):
            if i["number"] not in cur_inv:
                f.realised_since_prior.append(DetailRow("Invoice", i["number"], i["customer"],
                                                        "No longer open in Zoho (collected, credited or voided)",
                                                        i["balance"], self.run_date, i["status"]))

    # ----------------------------------------------------- cash flow model
    def _cash_flow_model(self, f: Forecast) -> None:
        A, n = self.a, len(self.fridays)
        cfm: dict[int, list[tuple[float, Optional[str]]]] = {}

        def put(row: int, i: int, val: float, formula: Optional[str]) -> None:
            cur = cfm.setdefault(row, [(0.0, None)] * n)
            v0, f0 = cur[i]
            if f0 is None:
                cur[i] = (val, formula)
            else:  # two schedules land in the same week -> add them
                cur[i] = (v0 + val, f"{f0}+{formula.lstrip('=')}")

        months = sorted({(x.year, x.month) for x in self.fridays} | {(self.fridays[-1].year, self.fridays[-1].month)})

        def dates(kind: str) -> list[date]:
            out = []
            for (y, m) in months:
                if kind == "card":
                    out.append(fri_on_or_after(date(y, m, 15)))
                elif kind == "first":
                    out.append(nth_friday(y, m, 1))
                elif kind == "second":
                    out.append(nth_friday(y, m, 2))
                elif kind == "third":
                    out.append(nth_friday(y, m, 3))
                elif kind == "fourth":
                    out.append(nth_friday(y, m, 4))
                elif kind == "last":
                    out.append(last_friday(y, m))
                elif kind == "health":
                    out.append(second_tuesday_week_friday(y, m))
            return [x for x in out if x in self.idx]

        anchor = date(2026, 8, 21)
        biweekly = [x for x in self.fridays if (x - anchor).days % 14 == 0]
        share = self._card_share(f)

        EA = "'Expense Assumptions'!$E$"
        sched = {
            # (Cash Flow Model row, Expense Assumptions row[, multiplier])
            "card": [(24, 39, 1), (27, 41, 1), (28, 42, 1), (32, 45, 1), (39, 4, 4), (40, 5, 4), (41, 6, 4),
                     (45, 7, 4), (46, 8, 4), (52, 14, 1), (53, 15, 1), (59, 21, 1), (64, 23, 1), (72, 28, 1),
                     (76, 30, 1), (77, 31, 1), (78, 32, 1), (79, 33, 1), (80, 34, 1), (81, 35, 1), (83, 36, 1)],
            "bi": [(29, 29), (42, 10), (43, 11), (44, 12), (47, 9), (56, 18), (57, 19), (58, 20), (70, 26)],
            "first": [(51, 13), (66, 25), (90, 38)],
        }
        for row, er, mult in sched["card"]:
            for x in dates("card"):
                put(row, self.idx[x], A.ea[er] * mult, f"={EA}{er}" + (f"*{mult}" if mult != 1 else ""))
        for row, er in sched["bi"]:
            for x in biweekly:
                put(row, self.idx[x], A.ea[er], f"={EA}{er}")
        for x in biweekly:
            put(55, self.idx[x], A.ea[16] + A.ea[17], f"={EA}16+{EA}17")
        for row, er in sched["first"]:
            for x in dates("first"):
                put(row, self.idx[x], A.ea[er], f"={EA}{er}")
        for x in dates("first"):
            # Non-card part (1 - card share) paid directly on the 1st Friday.
            put(30, self.idx[x], A.ea[43] * (1 - share), f"={EA}43*(1-'Credit Card Payments'!$B$41)")
        for x in dates("second"):
            # Card-charged part shown separately on the 2nd Friday (as agreed with the client): charged in this row,
            # added back by row 96 the same week (Credit Card Payments row 27) and paid inside its card statement
            # via row 94 - so the full monthly accrual is paid once.
            put(30, self.idx[x], A.ea[43] * share, f"={EA}43*'Credit Card Payments'!$B$41")
        for x in dates("second"):
            put(60, self.idx[x], A.ea[22], f"={EA}22")
        for x in dates("health"):
            put(87, self.idx[x], A.ea[37], f"={EA}37")
        GI = "'General Info'!$B$"
        for x in dates("fourth"):
            put(68, self.idx[x], A.gi[29], f"={GI}29")
        for x in dates("third"):
            put(68, self.idx[x], A.gi[30], f"={GI}30")
        for x in dates("first"):
            if x.month in (6, 12):
                put(68, self.idx[x], A.gi[28], f"={GI}28")
        for x in dates("fourth"):
            if x.month == 4:
                put(71, self.idx[x], A.ea[27], f"={EA}27")
        for x in dates("last"):
            put(ROW_LOAN, self.idx[x], A.gi[31], f"={GI}31")
        self._duckbill(f, put)
        # General Info tax schedule: IRS rows 34-37, NJ rows 38-41 (Jun 15 / Sep 15 / Jan 15 / Apr 15)
        for gi_row, (mo, dy) in {34: (6, 15), 35: (9, 15), 36: (1, 15), 37: (4, 15),
                                 38: (6, 15), 39: (9, 15), 40: (1, 15), 41: (4, 15)}.items():
            target_row = 88 if gi_row <= 37 else 89
            for y in {x.year for x in self.fridays}:
                t = date(y, mo, dy)
                w = fri_on_or_before(t)
                if t >= self.run_date and w in self.idx:
                    put(target_row, self.idx[w], A.gi[gi_row], f"={GI}{gi_row}")
        for i in range(n):
            put(25, i, A.ea[40], f"={EA}40")
            put(26, i, A.ea[46], f"={EA}46")
            put(31, i, A.ea[44], f"={EA}44")
            if i >= self.rules.get("reseller_run_rate_start_week", 5) - 1:
                # Assumptions & Rules row 6: run-rate collected week + 4, so from week 5 (weeks 1-4 covered by open reseller invoices)
                put(9, i, A.rd[8], "='Revenue Detail'!$B$8")
            if i > 0:
                put(11, i, A.rd[9] / 52, "='Revenue Detail'!$B$9/52")
                put(12, i, A.rd[10] / 52, "='Revenue Detail'!$B$10/52")
                put(13, i, A.rd[11] / 52, "='Revenue Detail'!$B$11/52")

        self._manual_entries(f, put)

        # revenue + COGS from detail rows
        vals = {r: [0.0] * n for r in range(4, ROW_ENDING + 1)}
        for r in f.revenue:
            if r.week in self.idx:
                vals[revenue_row(r.source)][self.idx[r.week]] += r.amount
        cat_row = {COGS_3100: 18, COGS_3101: 19, COGS_3102: 20}
        for r in f.cogs:
            if r.week in self.idx:
                vals[cat_row[r.category]][self.idx[r.week]] += r.amount
        for row, cells in cfm.items():
            for i, (v, _) in enumerate(cells):
                vals[row][i] += v

        # card roll-forward
        self._card(f, vals, share)

        for tot, rows in TOTAL_ROWS.items():
            for i in range(n):
                vals[tot][i] = sum(vals[r][i] for r in rows)
        for i in range(n):
            vals[35][i] = vals[15][i] - vals[21][i] - vals[33][i]
            vals[4][i] = f.opening_cash if i == 0 else vals[98][i - 1]
            vals[98][i] = (vals[4][i] + vals[15][i] - vals[21][i] - vals[33][i] - vals[48][i] - vals[61][i]
                           - vals[73][i] - vals[84][i] - vals[91][i] - vals[94][i] - vals[95][i] + vals[96][i])
        f.cfm = cfm
        f.values = vals

    def manual_entry_rows(self) -> set[int]:
        """Cash Flow Model rows a manual entry may go to: 9, 11-13, the non-card expense rows, 87-90 and 95.
        Not the detail-driven rows (8 SERVPRO, 10 Amazon, 14 A/R, 18-20 COGS), the card-funded rows (their card add-back
        would cancel the entry), totals, or the card rows 94 / 96."""
        card = {r for _, r in CARD_ROWS}
        rows = {9, 11, 12, 13, ROW_LOAN}
        for tot, rng in TOTAL_ROWS.items():
            if tot in (ROW_TOTAL_REVENUE, ROW_TOTAL_COGS):
                continue
            rows |= {r for r in rng if r not in card}
        return rows

    def _manual_entries(self, f: Forecast, put) -> None:
        """One-off amounts entered by hand in forecast_rules.json ("manual_entries").

        Each entry is written to General Info (MANUAL ENTRIES block) and added to its Cash Flow Model cell by formula
        (='General Info'!$B$<row>), so the figure is visible, labelled and traceable. Entries dated before week 1 expire
        (their cash is already inside the opening balance) and are listed but not applied."""
        allowed = self.manual_entry_rows()
        out = []
        for k, e in enumerate(self.rules.get("manual_entries", []) or []):
            gi_row = MANUAL_ENTRY_FIRST_GI_ROW + k
            row = int(e.get("cfm_row") or 0)
            amt = float(e.get("amount") or 0)
            given = d(e.get("week_ending"))
            wk = fri_on_or_before(given) if given else None
            if row not in allowed:
                status, applied = f"NOT APPLIED - Cash Flow Model row {row} cannot take a manual entry", False
            elif wk is None:
                status, applied = "NOT APPLIED - no week_ending date", False
            elif wk < self.run_date:
                status, applied = (f"EXPIRED - w/e {fmt_md(wk)} is before week 1, so its cash is already in the opening balance. "
                                   "If it is still not posted in Zoho, enter it again for a current week."), False
            elif wk not in self.idx:
                status, applied = f"NOT APPLIED - w/e {fmt_md(wk)} is after the forecast window", False
            else:
                put(row, self.idx[wk], amt, f"='General Info'!$B${gi_row}")
                status, applied = f"Applied: Cash Flow Model row {row}, w/e {fmt_md(wk)}", True
            if not applied:
                f.exceptions.append(f"Manual entry '{e.get('label', '')}' {money(amt)}: {status}.")
            out.append({**e, "gi_row": gi_row, "cfm_row": row, "amount": amt, "week": wk, "applied": applied,
                        "status": status})
        f.manual_entries = out

    # Card transactions in the snapshot run from cycle_history_start (two cycles before the unpaid one) to pulled_to
    # (the pull day). Older snapshots hold the unpaid cycle only.
    def _plat_txns(self, lo: date, hi: date) -> list[dict]:
        plat = self.rules["credit_cards"]["platinum_name_contains"].lower()
        return [t for t in self.s.get("card_transactions", [])
                if plat in (t.get("card") or "").lower() and lo.isoformat() <= str(t.get("date") or "")[:10] <= hi.isoformat()]

    def _card_cycles_back(self) -> list[tuple[date, date]]:
        """(start, close) of the unpaid cycle and the two before it, oldest first."""
        C = self.rules["credit_cards"]
        close = first_open_cycle_close(self.run_date, C["cycle_close_day"], C["statement_due_day"])
        out = []
        for _ in range(3):
            prev = (close.replace(day=1) - timedelta(days=1)).replace(day=C["cycle_close_day"])
            out.append((prev + timedelta(days=1), close))
            close = prev
        return out[::-1]

    @staticmethod
    def _net_charges(txns: list[dict], account: Optional[str] = None) -> float:
        """Charges less refunds (payments to the card excluded), optionally for one expense account."""
        tot = 0.0
        for t in txns:
            if account and account not in (t.get("details") or "").lower():
                continue
            if t.get("type") == "payment":
                continue
            tot += float(t.get("credit") or 0) - (float(t.get("debit") or 0) if t.get("type") == "refund" else 0.0)
        return round(tot, 2)

    def _card_share(self, f: Forecast) -> float:
        C = self.rules["credit_cards"]
        acct = C["outbound_freight_account_name"].lower()
        plat = C["platinum_name_contains"].lower()
        cycles = self._card_cycles_back()
        u_start, u_close = cycles[-1]
        txns = self._plat_txns(u_start, u_close)
        charges = sum(t["credit"] for t in txns)
        plat_bal = next((c["balance"] for c in self.s["card_accounts"] if plat in c["name"].lower()), 0.0)
        # Plausibility: compare the cycle's charges with the balance AT THE CLOSE (live balance less charges since the
        # close plus payments since the close). A statement paid early lowers the live balance but not the cycle.
        later = [t for t in self.s.get("card_transactions", [])
                 if plat in (t.get("card") or "").lower() and str(t.get("date") or "")[:10] > u_close.isoformat()]
        later_pays = sum(float(t.get("debit") or 0) for t in later if t.get("type") == "payment")
        at_close = plat_bal - self._net_charges(later) + later_pays
        if txns and not (0 < charges <= 3 * max(at_close, plat_bal, 1.0)):
            f.exceptions.append(f"Card transaction pull looks wrong (cycle charges {charges:,.2f} vs Platinum balance "
                                f"at the close {at_close:,.2f}) - ignored; outbound freight card share uses the last known "
                                "cycles.")
            txns = []
        self._card_txns_ok = bool(txns)
        cyc = self.s.get("card_cycle", {}) or {}
        hist_start = d(cyc.get("history_start"))
        if txns and hist_start and hist_start <= cycles[0][0]:
            # live: the last three cycles, all measured from this run's card transaction pull
            hist = [{"label": f"Cycle {a.isoformat()} – {b.isoformat()} (live card transaction pull)",
                     "amount": self._net_charges(self._plat_txns(a, b), acct)} for a, b in cycles]
            f.card["share_basis"] = "live"
        else:
            hist = list(C["outbound_freight_card_history"])
            if txns:
                hist.append({"label": f"Cycle {u_start.isoformat()} – {u_close.isoformat()} (live card transaction pull)",
                             "amount": self._net_charges(txns, acct)})
            else:
                hist.append(C["outbound_freight_card_fallback"])
                if not any("Card transaction pull looks wrong" in e for e in f.exceptions):
                    f.exceptions.append("No card transactions returned - outbound freight card share uses the last known cycle.")
            f.exceptions.append("Outbound freight card share: earlier cycles not in this pull - the stored cycle amounts "
                                "(forecast_rules.json) are used for them. Re-fetch Zoho to measure all three cycles live.")
            hist = hist[-3:]
            f.card["share_basis"] = "stored"
        f.card["share_obs"] = hist
        avg = sum(h["amount"] for h in hist) / len(hist)
        f.card["share"] = avg / self.a.ea[43]
        return f.card["share"]

    def _post_close(self, close: date) -> Optional[dict]:
        """Platinum activity posted after the unpaid cycle's close (None when the pull stops at the close)."""
        cyc = self.s.get("card_cycle", {}) or {}
        pulled_to = d(cyc.get("pulled_to"))
        if not pulled_to or pulled_to <= close or not getattr(self, "_card_txns_ok", False):
            return None
        txns = self._plat_txns(close + timedelta(days=1), pulled_to)
        pays = round(sum(float(t.get("debit") or 0) for t in txns if t.get("type") == "payment"), 2)
        return {"from": close + timedelta(days=1), "to": pulled_to, "net": self._net_charges(txns),
                "payments": pays, "count": len(txns)}

    def _card(self, f: Forecast, vals: dict[int, list[float]], share: float) -> None:
        C, n = self.rules["credit_cards"], len(self.fridays)
        block_a = [0.0] * n
        for _, cfm_row in CARD_ROWS:
            for i in range(n):
                block_a[i] += vals[cfm_row][i]
        second_fridays = {nth_friday(x.year, x.month, 2) for x in self.fridays}
        outbound_card = [self.a.ea[43] * share if x in second_fridays else 0.0 for x in self.fridays]
        for i in range(n):
            block_a[i] += outbound_card[i]
        plat = next((c for c in self.s["card_accounts"] if C["platinum_name_contains"].lower() in c["name"].lower()), None)
        corp = next((c for c in self.s["card_accounts"] if C["corp_name_contains"].lower() in c["name"].lower()), None)
        plat_bal = round(plat["balance"], 2) if plat else 0.0
        corp_bill = f.card.get("corp_bill")
        corp_bal = round((corp["balance"] if corp else 0.0) - (corp_bill["balance"] if corp_bill else 0.0), 2)

        cd, dd = C["cycle_close_day"], C["statement_due_day"]
        first_close = first_open_cycle_close(self.run_date, cd, dd)
        post = self._post_close(first_close)
        # First statement = the Platinum balance AT THE CLOSE: live balance less the net charges posted since the close.
        # Those charges are owed on the NEXT statement, together with the CORP residual.
        post_net = post["net"] if post else 0.0
        post_pay = post["payments"] if post else 0.0
        # Still due on the first statement = live balance less the charges since the close (payments made since the
        # close are already out of the live balance). Balance at the close = still due + those payments.
        plat_at_close = round(plat_bal - post_net, 2)
        plat_close_balance = round(plat_at_close + post_pay, 2)
        overpaid = 0.0
        sbills = f.card.get("statement_bills") or []
        bill_due = round(sum(x["balance"] for x in sbills), 2)
        carry = 0.0
        if sbills:
            # The open statement bill is what Amex billed and what is still to be paid in cash. Whatever is left on the
            # card at the close beyond it (book vs statement difference) goes on the next statement with the charges
            # posted since the close: B34 = live balance (less nothing) = charges since the close + that difference.
            carry = round(plat_bal - post_net, 2)
            plat_at_close = bill_due
            if abs(carry) > 0.005:
                f.exceptions.append(f"Platinum: {money(abs(carry))} {'left on the card' if carry > 0 else 'credit on the card'} "
                                    f"at the close beyond the open Amex statement bill - carried to the next statement "
                                    "(check the Zoho card balance against the Amex statement).")
            post_net = round(post_net + carry, 2)
        elif plat_at_close < 0:   # more paid since the close than the statement: the excess reduces the next statement
            overpaid, plat_at_close = round(-plat_at_close, 2), 0.0
            post_net = round(post_net - overpaid, 2)
            f.exceptions.append(f"Platinum: {money(overpaid)} paid since the close beyond the statement - taken off the "
                                "next statement.")
        cycles = []
        prev_close = None
        close = first_close
        for k in range(C["cycles_to_schedule"]):
            due = (close.replace(day=1) + timedelta(days=32)).replace(day=dd)
            lands = fri_on_or_before(due)
            if k == 0 and sbills:
                opening, charges = plat_at_close, 0.0
                due = min(x["due"] for x in sbills)
                lands = self.payment_week(due)
                basis = (f"ACTUAL — open Amex statement bill{'s' if len(sbills) > 1 else ''} "
                         f"{', '.join(x['number'] for x in sbills)} in Zoho A/P, due {fmt_md(due)}"
                         + (f"; {carry:,.2f} left on the card at the close carried to the next statement (B34)"
                            if abs(carry) > 0.005 else ""))
            elif k == 0:
                opening, charges = plat_at_close, 0.0
                basis = ((f"ACTUAL — Platinum balance at the {fmt_md(close)} close {plat_close_balance:,.2f} less "
                          f"{post_pay:,.2f} paid since the close = {plat_at_close:,.2f} still due "
                          f"(live balance {plat_bal:,.2f} less {post_net:,.2f} net charges posted "
                          f"{fmt_md(post['from'])}–{fmt_md(post['to'])})") if post and post_pay > 0.005 else
                         f"ACTUAL — Platinum balance at the {fmt_md(close)} close: live balance {plat_bal:,.2f} less "
                         f"{post_net:,.2f} net charges posted {fmt_md(post['from'])}–{fmt_md(post['to'])}" if post else
                         "Live Platinum balance - charges after the close were not in this pull, so this may include "
                         "next-cycle charges (re-fetch Zoho)")
            else:
                opening = round(corp_bal + post_net, 2) if k == 1 else 0.0
                charges = sum(block_a[i] for i, x in enumerate(self.fridays) if prev_close < x <= close)
                basis = (("CORP residual + Platinum charges already posted after the previous close (actual) + Block A "
                          "charges in cycle") if k == 1 and post else
                         "CORP residual rolled in + Block A charges in cycle" if k == 1
                         else "Block A charges falling in this cycle (SUMIFS over the Block A total row)")
            cycles.append({"close": close, "due": due, "lands": lands, "opening": opening, "charges": charges,
                           "total": opening + charges, "basis": basis})
            prev_close = close
            close = (close.replace(day=1) + timedelta(days=32)).replace(day=cd)
        corp_row = None
        if corp_bill:
            corp_row = {"close": None, "due": corp_bill["due"], "lands": self.payment_week(corp_bill["due"]),
                        "total": corp_bill["balance"], "basis": f"ACTUAL — Zoho A/P bill {corp_bill['number']}"}
        pay = [0.0] * n
        for c in cycles + ([corp_row] if corp_row else []):
            if c["lands"] in self.idx:
                pay[self.idx[c["lands"]]] += c["total"]
        vals[ROW_CC_PAYMENT] = pay
        vals[ROW_CC_DEFERRED] = block_a
        f.card.update({"block_a": block_a, "outbound_card": outbound_card, "platinum": plat, "corp": corp,
                       "platinum_balance": plat_bal, "platinum_at_close": plat_at_close, "post_close": post,
                       "platinum_close_balance": plat_close_balance, "paid_since_close": post_pay,
                       "post_close_net": post_net if post else 0.0, "overpaid_since_close": overpaid,
                       "statement_bill_due": bill_due, "carry_to_next": carry,
                       "corp_residual": corp_bal, "cycles": cycles,
                       "corp_row": corp_row, "itemization": self._itemize(f)})

    def _itemize(self, f: Forecast) -> list[tuple[str, float]]:
        plat = self.rules["credit_cards"]["platinum_name_contains"].lower()
        agg: dict[str, float] = {}
        payments = 0.0
        if not getattr(self, "_card_txns_ok", False):
            f.card["cycle_payments"] = 0.0
            return []
        u_start, u_close = self._card_cycles_back()[-1]
        for t in self._plat_txns(u_start, u_close):
            if t["debit"] and t["type"] in ("bill", "card_payment", "transfer_fund", "payment", "deposit"):
                payments += t["debit"]
                continue
            agg[t["details"]] = agg.get(t["details"], 0.0) + t["credit"] - t["debit"]
        f.card["cycle_payments"] = round(payments, 2)
        return sorted(((k, round(v, 2)) for k, v in agg.items() if abs(v) > 0.004), key=lambda kv: -kv[1])

    # ---------------------------------------------------------------- kpis
    def _kpis(self, f: Forecast) -> None:
        end = f.values[ROW_ENDING]
        lo = min(end)
        lo_i = end.index(lo)
        neg = [x for x, v in zip(self.fridays, end) if v < 0]
        rec = next((self.fridays[i] for i in range(lo_i, len(end)) if end[i] >= 0), None)
        first_neg = neg[0] if neg else None
        f.kpis = {"trough": lo, "trough_week": self.fridays[lo_i], "negative_weeks": neg, "first_negative": first_neg,
                  "recovers": rec, "horizon_end": end[-1],
                  "open_ar_count": sum(1 for i in self.s["invoices"] if i["status"] != "draft" and i["balance"] > 0),
                  "open_ar": round(sum(i["balance"] for i in self.s["invoices"] if i["status"] != "draft"), 2),
                  "draft_count": sum(1 for i in self.s["invoices"] if i["status"] == "draft"),
                  "draft_total": round(sum(i["total"] for i in self.s["invoices"] if i["status"] == "draft"), 2),
                  "ap_count": len(self.s["bills"]),
                  "ap_total": round(sum(b["balance"] for b in self.s["bills"]), 2),
                  "so_count": sum(1 for r in f.revenue if "Sales Order" in r.source),
                  "so_total": round(sum(r.amount for r in f.revenue if "Sales Order" in r.source), 2)}

    def _open_items(self, f: Forecast) -> None:
        # 1) Version 10 open items, word for word (not fixed in this run)
        f.v10_open_items = [dict(x) for x in self.rules.get("v10_open_items", [])]
        # 2) What this run changed vs Version 10, and why - for approval
        ref = self.rules.get("v10_reference", {})
        k = f.kpis
        neg = k["negative_weeks"]
        fixed = []
        if ref:
            fixed.append({"owner": "For approval", "item": (
                f"LOWEST POINT RESTATED vs Version 10: the forecast trough is now {money(k['trough'])} at w/e "
                f"{fmt_md(k['trough_week'])} (Version 10: {money(ref['trough'])} at w/e {fmt_md(d(ref['trough_week']))}); "
                f"negative weeks {len(neg)}" + (f" ({fmt_md(neg[0])} to {fmt_md(neg[-1])})" if neg else "") +
                f" (Version 10: {ref['negative_weeks']}). The rule changes below explain the change; any remaining "
                "difference comes from Zoho data that changed after Version 10 (orders invoiced, drafts re-issued) - "
                "see the difference register.")})
        if f.card.get("share") is not None and any(v for v in f.card.get("outbound_card", [])):
            share_amt = self.a.ea[43] * f.card["share"]
            fixed.append({"owner": "For approval", "item": (
                f"OUTBOUND FREIGHT CARD SHARE ({money(share_amt)}/month) now paid and shown separately: Cash Flow Model row 30 "
                f"carries the non-card {100 * (1 - f.card['share']):.0f}% on the 1st Friday and the card share on the 2nd "
                "Friday; the card share (Credit Card Payments row 27) is added back by row 96 in that same week and paid inside "
                "its card statement (row 94). Version 10 put only the non-card part on its row while still adding the card share "
                f"back, so that share was never paid (forecast {money(share_amt)}/month too high).")})
        if f.duckbill:
            tot = sum(x["amount"] for x in f.duckbill)
            fixed.append({"owner": "For approval", "item": (
                f"DUCKBILL REPAYMENT now forecast on row 95 (Loan Repayments): {len(f.duckbill)} payments, {money(tot)} in "
                f"the window - {money(f.duckbill[0]['amount'])} in w/e {fmt_md(f.duckbill[0]['week'])} "
                f"({f.duckbill[0]['source']}), then General Info B32 on the 1st Friday of each month through Dec 2027 "
                "(client decision 6 Oct 2026). Before: excluded as a non-COGS bill and in no row.")})
        added = [n.lower() for n in self.rules["opening_cash"].get("added_since_v10", [])]
        for c in f.cash_accounts:
            if (c.get("name") or "").strip().lower() in added:
                fixed.append({"owner": "For approval", "item": (
                    f"OPENING CASH now includes {c['name']} ({money(c['balance'])}): Stripe payouts collected but not yet "
                    "in the bank, added on instruction 2026-09-29. Version 10 General Info row 42 counted CHK + PayPal + "
                    "Petty Cash only. Opening cash is now exactly the named accounts - no other Zoho account type is added.")})
        for so_no, cfg in self.rules["sales_orders"].get("parent_orders", {}).items():
            if not isinstance(cfg, dict):
                continue
            row = next((r for r in f.revenue if r.ref == so_no), None)
            if row:
                fixed.append({"owner": "For approval", "item": (
                    f"{so_no} {row.party} now forecast at its uninvoiced remainder {money(row.amount)} in w/e "
                    f"{fmt_md(row.week)} (UNVERIFIED - no ship date): {cfg.get('reason', '')} Version 10 held it for client "
                    "review. SO-05926 and SO-05928 are also forecast normally now.")})
        for item, amt, why in f.restatements:
            if "held for client review" in item:
                continue
            pending = " PENDING CLIENT CONFIRMATION." if "excluded from COGS" in item else ""
            fixed.append({"owner": "For approval", "item": f"{item} ({money(abs(amt))}): {why}.{pending}"})
        for m in f.manual_entries:
            fixed.append({"owner": "Manual entry", "item": (
                f"{m.get('label', '')} {money(m['amount'])} - {m['status']}. Source: {m.get('source', '')}; entered by "
                f"{m.get('entered_by', '')} {m.get('entered_on', '')}. {m.get('note', '')} (General Info row {m['gi_row']})")})
        fixed.extend(dict(x) for x in self.rules.get("resolved_items", []))
        f.fixed_items = fixed
        # 3) Additional items for client review (discussed after Version 10, held orders, engine checks)
        items = [dict(x) for x in self.rules.get("additional_review_items", [])]
        for r in f.held:
            items.append({"owner": "Ralph Markham", "item": f"HELD FOR CLIENT REVIEW — {r.ref} {money(r.amount)}: {r.basis}"})
        v10_text = " ".join(x["item"] for x in f.v10_open_items)
        for r in f.revenue:
            if "UNVERIFIED" in r.basis and r.ref not in v10_text:  # already an open item in Version 10
                items.append({"owner": "Ayushi / Ralph", "item": f"{r.ref} ({money(r.amount)}) has NO shipment date in Zoho; dated from order date and labelled UNVERIFIED (w/e {fmt_md(r.week)})."})
        for r in f.cogs:
            if "UNVERIFIED" in r.basis:
                items.append({"owner": "Ayushi", "item": f"{r.ref} {r.party} ({money(r.amount)}) has no delivery date; dated from the PO date + terms (w/e {fmt_md(r.week)}), UNVERIFIED."})
        for e in f.exceptions:
            items.append({"owner": "Ayushi", "item": e})
        f.open_items = items


def build_forecast(snapshot: dict, prior_snapshot: Optional[dict] = None, rules: Optional[dict] = None) -> Forecast:
    return V10Engine(snapshot, rules=rules, prior_snapshot=prior_snapshot).run()
