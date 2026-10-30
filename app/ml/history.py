"""Turn the Zoho history workbook (tools/export_history.py) into three training tables.

Each table has one row per *finished* document and the same columns, so one model class serves all three:

  kind   party            base_date        known_date   paid_on            y (target, days)
  inv    customer         invoice due      invoice date last payment date  paid_on - due_date
  so     customer         shipment date    order date   last invoice paid  paid_on - shipment_date
  bill   vendor           bill due date    bill date    last vendor pay    paid_on - due_date

Only rows that are really finished (status paid + a payment date found) are used.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

SERVPRO_WORDS = ("servpro",)
AMAZON_WORDS = ("amazon",)
Y_MIN, Y_MAX = -60, 150          # days; anything outside is a data error / write-off, not a timing pattern


def norm(name) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip().lower())


def is_servpro(name) -> int:
    return int(any(w in norm(name) for w in SERVPRO_WORDS))


def is_amazon(name) -> int:
    n = norm(name)
    return int(any(w in n for w in AMAZON_WORDS) and not is_servpro(name))


def _dt(s):
    return pd.to_datetime(s, errors="coerce")


def _explode_docs(df: pd.DataFrame, col: str) -> pd.DataFrame:
    out = df.assign(doc=df[col].astype(str).str.split(",")).explode("doc")
    out["doc"] = out["doc"].str.strip()
    return out[out["doc"].ne("") & out["doc"].ne("None") & out["doc"].ne("nan")]


def load_history(path: Union[str, Path]) -> dict[str, pd.DataFrame]:
    """Read the sheets we need.  Missing sheets give an empty frame (that model is then simply not trained)."""
    xl = pd.ExcelFile(path)
    want = ["invoices", "customer payments", "sales orders", "bills", "vendor payments"]
    return {s: (xl.parse(s) if s in xl.sheet_names else pd.DataFrame()) for s in want}


def _finish(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    df = df.dropna(subset=["party", "base_date", "known_date", "paid_on"]).copy()
    df["y"] = (df["paid_on"] - df["base_date"]).dt.days
    df = df[(df["y"] >= Y_MIN) & (df["y"] <= Y_MAX)]
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0).abs()
    df["kind"] = kind
    return df.sort_values("paid_on").reset_index(drop=True)


def invoice_table(h: dict) -> pd.DataFrame:
    inv, pay = h["invoices"], h["customer payments"]
    if inv.empty or pay.empty:
        return pd.DataFrame()
    pay = pay.assign(pdate=_dt(pay["date"]))
    last = _explode_docs(pay, "invoice_numbers").groupby("doc")["pdate"].max().rename("paid_on")
    m = inv[inv["status"].eq("paid")].merge(last, left_on="invoice_number", right_index=True)
    t = pd.DataFrame({
        "key": m["invoice_number"], "party": m["customer_name"].map(norm), "amount": m["total"],
        "base_date": _dt(m["due_date"]), "known_date": _dt(m["date"]), "paid_on": m["paid_on"]})
    t["terms"] = (t["base_date"] - t["known_date"]).dt.days
    return _finish(t, "inv")


def sales_order_table(h: dict) -> pd.DataFrame:
    inv, pay, so = h["invoices"], h["customer payments"], h["sales orders"]
    if inv.empty or pay.empty or so.empty:
        return pd.DataFrame()
    pay = pay.assign(pdate=_dt(pay["date"]))
    last = _explode_docs(pay, "invoice_numbers").groupby("doc")["pdate"].max().rename("paid_on")
    paid_inv = inv[inv["status"].eq("paid")].merge(last, left_on="invoice_number", right_index=True)
    per_so = paid_inv.groupby("reference_number")["paid_on"].max().rename("paid_on")      # last invoice of the SO
    m = so.assign(ship=_dt(so["shipment_date"])).merge(per_so, left_on="salesorder_number", right_index=True)
    t = pd.DataFrame({
        "key": m["salesorder_number"], "party": m["customer_name"].map(norm), "amount": m["total"],
        "base_date": m["ship"], "known_date": _dt(m["date"]), "paid_on": m["paid_on"]})
    t["terms"] = np.nan
    return _finish(t, "so")


def bill_table(h: dict) -> pd.DataFrame:
    bills, vp = h["bills"], h["vendor payments"]
    if bills.empty or vp.empty:
        return pd.DataFrame()
    vp = vp.assign(pdate=_dt(vp["date"]))
    last = _explode_docs(vp, "bill_numbers").groupby("doc")["pdate"].max().rename("paid_on")
    m = bills[bills["status"].eq("paid")].merge(last, left_on="bill_number", right_index=True)
    t = pd.DataFrame({
        "key": m["bill_number"], "party": m["vendor_name"].map(norm), "amount": m["total"],
        "base_date": _dt(m["due_date"]), "known_date": _dt(m["date"]), "paid_on": m["paid_on"]})
    t["terms"] = (t["base_date"] - t["known_date"]).dt.days
    return _finish(t, "bill")


def build_tables(path: Union[str, Path]) -> dict[str, pd.DataFrame]:
    h = load_history(path)
    return {"inv": invoice_table(h), "so": sales_order_table(h), "bill": bill_table(h)}
