"""Build a forecast snapshot from Zoho Books EXPORT files (offline testing / fallback).

Produces the same normalized dict as zoho.snapshot.pull_snapshot(), so the engine
and the Excel exporter run the identical code path as a live sync.

Usage:
    python tools/snapshot_from_exports.py <exports_folder> <run_date YYYY-MM-DD> <out.json>

Files expected in the folder (standard Zoho export names):
    AR_Aging_Details_By_Invoice_Due_Date.xlsx   unpaid invoices (sent/overdue/partially_paid)
    Invoice.csv                                  draft invoices + their sales order links
    Sales_Order.xlsx                             sales orders with line quantities
    Purchase_Order.csv                           purchase orders with line quantities + payment terms
    AP_Aging_Details_By_Bill_Date.xlsx           unpaid bills
    Bill.csv                                     bill line accounts
    Balance_Sheet.xlsx                           cash + credit card balances at the run date
    Account_Transactions.xlsx                    card account activity (last statement cycle)
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from zoho.snapshot import last_card_cycle  # noqa: E402


def _d(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "nan", "NaT"):
        return None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip().split(" ")[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _n(v):
    try:
        f = float(v)
        return 0.0 if pd.isna(f) else f
    except (TypeError, ValueError):
        return 0.0


def _terms_days(label, days):
    if isinstance(label, str) and "receipt" in label.lower():
        return 0
    try:
        return int(float(days))
    except (TypeError, ValueError):
        return None


def build(folder: Path, run_date: date, card_close_day: int = 26) -> dict:
    # ---- invoices: unpaid from AR aging, drafts from Invoice.csv
    ar = pd.read_excel(folder / "AR_Aging_Details_By_Invoice_Due_Date.xlsx", header=1)
    ar = ar[ar["entity"] == "invoice"]
    invoices = [{
        "number": r.transaction_number, "customer": r.customer_name, "status": str(r.status).lower(),
        "date": _d(r.date), "due_date": _d(r.due_date), "total": _n(r.amount), "balance": _n(r.balance),
        "salesorder_number": None,
    } for r in ar.itertuples()]
    inv = pd.read_csv(folder / "Invoice.csv", low_memory=False)
    so_link = inv.dropna(subset=["Sales Order Number"]).drop_duplicates("Invoice Number").set_index("Invoice Number")["Sales Order Number"].to_dict()
    for inv_row in invoices:
        inv_row["salesorder_number"] = so_link.get(inv_row["number"])
    drafts = inv[inv["Invoice Status"].str.lower() == "draft"].drop_duplicates("Invoice Number")
    for r in drafts.to_dict("records"):
        invoices.append({
            "number": r["Invoice Number"], "customer": r["Customer Name"], "status": "draft",
            "date": _d(r["Invoice Date"]), "due_date": _d(r["Due Date"]),
            "total": _n(r["Total"]), "balance": _n(r["Total"]), "salesorder_number": so_link.get(r["Invoice Number"]),
        })

    # ---- sales orders
    inv_by_so = (inv[~inv["Invoice Status"].str.lower().isin(["void"])]
                 .dropna(subset=["Sales Order Number"]).drop_duplicates("Invoice Number")
                 .groupby("Sales Order Number")["Total"].sum().to_dict())
    so = pd.read_excel(folder / "Sales_Order.xlsx")
    so["Status"] = so["Status"].astype(str).str.lower()
    keep = so[so["Status"].isin(["confirmed", "open", "draft", "partially_invoiced"])]
    sales_orders = []
    for num, g in keep.groupby("SalesOrder Number"):
        f = g.iloc[0]
        total = _n(f["Total"])
        full = open_ = 0.0
        for li in g.to_dict("records"):
            qty = _n(li["QuantityOrdered"])
            if qty <= 0:
                continue
            lt = _n(li.get("Item Total")) or qty * _n(li.get("Item Price"))
            done = _n(li.get("QuantityInvoiced")) + _n(li.get("QuantityCancelled"))
            full += lt
            open_ += lt * max(qty - done, 0) / qty
        uninv = round(total * open_ / full, 2) if full else total
        if num in inv_by_so:  # same basis as Zoho total_invoiced_amount (sum of linked invoice totals)
            uninv = round(total - float(inv_by_so[num]), 2)
        sales_orders.append({
            "number": num, "customer": f["Customer Name"], "status": f["Status"], "date": _d(f["Order Date"]),
            "shipment_date": _d(f["Expected Shipment Date"]), "payment_terms_days": None,
            "total": total, "invoiced": round(total - uninv, 2), "uninvoiced": uninv,
        })

    # ---- purchase orders
    po = pd.read_csv(folder / "Purchase_Order.csv", low_memory=False)
    po["st"] = po["Purchase Order Status"].astype(str).str.lower().str.replace(" ", "_")
    po = po[po["st"].isin(["issued", "open", "draft", "partially_billed"])]
    purchase_orders = []
    for num, g in po.groupby("Purchase Order Number"):
        f = g.iloc[0]
        total = _n(f["Total"])
        full = open_ = 0.0
        for li in g.to_dict("records"):
            qty = _n(li["QuantityOrdered"])
            if qty <= 0:
                continue
            lt = _n(li.get("Item Total")) or qty * _n(li.get("Item Price"))
            done = _n(li.get("QuantityBilled")) + _n(li.get("QuantityCancelled"))
            full += lt
            open_ += lt * max(qty - done, 0) / qty
        purchase_orders.append({
            "number": num, "vendor": f["Vendor Name"], "status": f["st"], "date": _d(f["Purchase Order Date"]),
            "delivery_date": _d(f["Delivery Date"]), "total": total,
            "unbilled": round(total * open_ / full, 2) if full else total,
            "payment_terms_days": _terms_days(f["Payment Terms Label"], f["Payment Terms"]),
            "payment_terms_label": f["Payment Terms Label"],
            "cf_payment_term": str(f["CF.Payment Term(Formula)"]).strip("'") if pd.notna(f["CF.Payment Term(Formula)"]) else None,
            "accounts": sorted({str(a) for a in g["Account"].dropna()}),
            "ordered_qty": float(sum(_n(x) for x in g["QuantityOrdered"])),
            "received_qty": float(sum(_n(x) for x in g["QuantityReceived"])),
        })

    # ---- bills
    ap = pd.read_excel(folder / "AP_Aging_Details_By_Bill_Date.xlsx", header=1)
    ap = ap[ap["entity"] == "bill"]
    bl = pd.read_csv(folder / "Bill.csv", low_memory=False)
    acct = bl.groupby("Bill Number")["Account"].apply(lambda s: sorted({str(a) for a in s.dropna()})).to_dict()
    bills = [{
        "number": r.transaction_number, "vendor": r.vendor_name, "status": str(r.status).lower(),
        "date": _d(r.date), "due_date": _d(r.due_date), "total": _n(r.amount), "balance": _n(r.balance),
        "reference": None, "accounts": acct.get(r.transaction_number, []),
    } for r in ap.itertuples()]

    # ---- cash + card balances from the balance sheet
    bs = pd.read_excel(folder / "Balance_Sheet.xlsx", header=None)
    cash, cards = [], []
    for r in bs.itertuples(index=False):
        name = str(r[0]).strip()
        val = r[2]
        if not isinstance(val, (int, float)) or pd.isna(val) or name.startswith("Total"):
            continue
        if name in ("BUSINESS FUNDAMENTALS CHK", "PayPal", "Petty Cash", "Stripe Clearing"):
            cash.append({"account_id": None, "name": name, "type": "bank" if "CHK" in name else "cash", "balance": float(val)})
        if "Card" in name or "7747" in name:
            cards.append({"account_id": None, "name": name, "type": "credit_card", "balance": float(val)})
    if not any(c["name"] == "Petty Cash" for c in cash):
        cash.append({"account_id": None, "name": "Petty Cash", "type": "cash", "balance": 0.0})

    # ---- card transactions for the cycle
    start, close = last_card_cycle(run_date, card_close_day)
    at = pd.read_excel(folder / "Account_Transactions.xlsx", header=1) if (folder / "Account_Transactions.xlsx").exists() else None
    card_txns = []
    if at is not None:
        at["date"] = pd.to_datetime(at["date"], errors="coerce")
        cc = at[(at["account_type"] == "credit_card") & (at["date"] >= pd.Timestamp(start)) & (at["date"] <= pd.Timestamp(close))]
        for r in cc.itertuples():
            card_txns.append({"card": r.account_name, "date": r.date.strftime("%Y-%m-%d"), "type": str(r.transaction_type),
                              "details": str(r.transaction_details), "debit": _n(r.debit), "credit": _n(r.credit)})

    return {
        "source": f"zoho_exports:{folder.name}",
        "run_date": run_date.isoformat(),
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "cash_accounts": cash,
        "card_accounts": cards,
        "card_cycle": {"start": start.isoformat(), "close": close.isoformat()},
        "card_transactions": card_txns,
        "invoices": invoices,
        "sales_orders": sales_orders,
        "purchase_orders": purchase_orders,
        "bills": bills,
    }


if __name__ == "__main__":
    folder, rd, out = Path(sys.argv[1]), date.fromisoformat(sys.argv[2]), Path(sys.argv[3])
    snap = build(folder, rd)
    out.write_text(json.dumps(snap, indent=1, default=str))
    print({k: len(v) for k, v in snap.items() if isinstance(v, list)})
