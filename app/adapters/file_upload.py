from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4
import pandas as pd

from app.models.canonical import CanonicalRecord, DataConfidence
from app.models.preflight import CadenceTier


def _parse_decimal(val: Any) -> Decimal:
    if val is None or str(val).strip() == "":
        return Decimal("0")
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))
    cleaned = str(val).replace(",", "").replace("$", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Cannot parse decimal from: {val!r}")


def _parse_date(val: Any) -> Optional[date]:
    if val is None or str(val).strip() == "":
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if " " in s:
        s = s.split(" ")[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y", "%d/%m/%Y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _get_field(row: dict[str, Any], *aliases: str, required: bool = False, source: str = "", row_num: int = 0) -> str:
    lower_map = {str(k).lower().strip(): v for k, v in row.items()}
    for a in aliases:
        a_clean = a.lower().strip()
        if a_clean in lower_map and lower_map[a_clean] is not None:
            s = str(lower_map[a_clean]).strip()
            if s != "" and s.lower() != "nan" and s.lower() != "none":
                return s
    if required:
        raise ValueError(f"[{source}] Row {row_num}: required column not found. Expected one of: {aliases}")
    return ""


def _read_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    ext = Path(filename).suffix.lower()
    bio = io.BytesIO(file_bytes)
    if ext == ".csv":
        try:
            return pd.read_csv(bio, header=0, dtype=str)
        except Exception:
            bio.seek(0)
            return pd.read_csv(bio, header=1, dtype=str)
    
    engine = "xlrd" if ext == ".xls" else "openpyxl"
    df0 = pd.read_excel(bio, engine=engine, header=0, dtype=str)
    cols0 = [str(c).lower().strip() for c in df0.columns]
    key_markers = ["invoice_number", "bill_number", "salesorder_number", "purchaseorder_number", "vendor_name", "customer_name", "date", "status"]
    if any(any(m in c for m in key_markers) for c in cols0):
        return df0
    
    bio.seek(0)
    return pd.read_excel(bio, engine=engine, header=1, dtype=str)


def _read_rows(file_bytes: bytes, filename: str) -> list[dict[str, Any]]:
    df = _read_dataframe(file_bytes, filename)
    df = df.where(pd.notna(df), None)
    return df.to_dict(orient="records")


def detect_source(file_bytes: bytes, filename: str) -> Optional[str]:
    try:
        rows = _read_rows(file_bytes, filename)
        if not rows:
            return None
        sample_keys = " ".join([str(k).lower() for k in rows[0].keys()])
        
        if "invoice_number" in sample_keys or "invoice #" in sample_keys or "invoice id" in sample_keys:
            return "ar_unpaid_invoices"
        if "salesorder_number" in sample_keys or "sales order number" in sample_keys or "salesorder #" in sample_keys:
            return "confirmed_sales_orders"
        if "bill_number" in sample_keys or "bill #" in sample_keys or "bill id" in sample_keys:
            return "partially_paid_bills"
        if "purchaseorder_number" in sample_keys or "purchase order number" in sample_keys or "po #" in sample_keys:
            return "purchase_orders"
        if "item name" in sample_keys or "item_name" in sample_keys:
            return "sales_by_item_6mo"
        if "asin" in sample_keys:
            return "amazon_sales_6mo"
        if "account code" in sample_keys or "account #" in sample_keys:
            return "profit_and_loss"
        if "transaction_details" in sample_keys or "transaction_id" in sample_keys or "ending balance" in sample_keys:
            return "bank_statement"
        
        fn = filename.lower()
        if "invoice" in fn:
            return "ar_unpaid_invoices"
        if "sales" in fn and "order" in fn:
            return "confirmed_sales_orders"
        if "bill" in fn:
            return "partially_paid_bills"
        if "purchase" in fn or "po" in fn:
            return "purchase_orders"
        if "bank" in fn:
            return "bank_statement"
            
        return None
    except Exception:
        return None


def parse_ar_unpaid_invoices(file_bytes: bytes, filename: str, upload_ts: datetime, as_of: date) -> list[CanonicalRecord]:
    rows = _read_rows(file_bytes, filename)
    records = []
    seen_invoices: set[str] = set()
    open_statuses = {"open", "sent", "overdue", "partially_paid", "partially paid"}
    for i, row in enumerate(rows, start=2):
        invoice_number = _get_field(row, "invoice_number", "Invoice Number", "Invoice #", "Invoice ID", "Invoice_Number", required=True, source="ar_unpaid_invoices", row_num=i)
        if invoice_number in seen_invoices:
            continue
        seen_invoices.add(invoice_number)
        customer_name = _get_field(row, "customer_name", "Customer Name", "Customer", "Customer_Name", required=True, source="ar_unpaid_invoices", row_num=i)
        status = _get_field(row, "status", "Invoice Status", "Status", "Invoice_Status", required=True, source="ar_unpaid_invoices", row_num=i)
        status_clean = status.lower().replace(" ", "_")
        if status_clean not in open_statuses:
            continue
        due_date_raw = _get_field(row, "due_date", "Due Date", "DueDate", "Due_Date", "Expected Payment Date", "Invoice Date", required=False, source="ar_unpaid_invoices", row_num=i)
        balance_raw = _get_field(row, "bcy_balance", "balance", "Balance", "Balance Due", "Balance_Due", "Total", required=True, source="ar_unpaid_invoices", row_num=i)
        due_date = _parse_date(due_date_raw) if due_date_raw else None
        balance = _parse_decimal(balance_raw)
        if balance <= 0:
            continue
        ref_num = _get_field(row, "reference_number", "Reference #", "Reference No", "Reference#", "PurchaseOrder")
        records.append(CanonicalRecord(
            source="ar_unpaid_invoices",
            record_type="invoice",
            ingested_at=upload_ts,
            as_of_date=as_of,
            confidence=DataConfidence.VERIFIED_LIVE,
            payload={
                "invoice_number": invoice_number,
                "customer_name": customer_name,
                "status": status_clean,
                "due_date": due_date.isoformat() if due_date else None,
                "balance": str(balance),
                "reference_number": ref_num or None,
            },
            raw_ref=f"row {i} of {filename}"
        ))
    return records


def parse_confirmed_sales_orders(file_bytes: bytes, filename: str, upload_ts: datetime, as_of: date) -> list[CanonicalRecord]:
    rows = _read_rows(file_bytes, filename)
    records = []
    seen_sos: set[str] = set()
    open_statuses = {"confirmed", "open", "partially_invoiced", "partiallyinvoiced"}
    for i, row in enumerate(rows, start=2):
        so_number = _get_field(row, "salesorder_number", "SalesOrder Number", "Sales Order Number", "SO #", "SalesOrder ID", "SalesOrder#", required=False, source="confirmed_sales_orders", row_num=i)
        if not so_number or so_number in seen_sos:
            continue
        seen_sos.add(so_number)
        status = _get_field(row, "status", "Status", "Sales Order Status", "Custom Status", required=True, source="confirmed_sales_orders", row_num=i)
        status_clean = status.lower().replace(" ", "_")
        if status_clean not in open_statuses:
            continue
        customer = _get_field(row, "customer_name", "Customer Name", "Customer", "Customer_Name", required=True, source="confirmed_sales_orders", row_num=i)
        ship_date_r = _get_field(row, "shipment_date", "Expected Shipment Date", "Expected Ship Date", "Expected_Shipment_Date", "Order Date", required=False, source="confirmed_sales_orders", row_num=i)
        total_raw = _get_field(row, "bcy_total", "total", "Total", "Total Amount", "SubTotal", "Item Total", required=True, source="confirmed_sales_orders", row_num=i)
        ship_date = _parse_date(ship_date_r) if ship_date_r else None
        total = _parse_decimal(total_raw)
        if total <= 0:
            continue
        linked_invoice = _get_field(row, "Linked Invoice # (if since invoiced)", "Linked Invoice #", "Invoice Number")
        records.append(CanonicalRecord(
            source="confirmed_sales_orders",
            record_type="sales_order",
            ingested_at=upload_ts,
            as_of_date=as_of,
            confidence=DataConfidence.VERIFIED_LIVE,
            payload={
                "salesorder_number": so_number,
                "customer_name": customer,
                "expected_shipment_date": ship_date.isoformat() if ship_date else None,
                "total": str(total),
                "status": status_clean,
                "linked_invoice_number": linked_invoice or None,
            },
            raw_ref=f"row {i} of {filename}"
        ))
    return records


def parse_purchase_orders(file_bytes: bytes, filename: str, upload_ts: datetime, as_of: date) -> list[CanonicalRecord]:
    rows = _read_rows(file_bytes, filename)
    records = []
    seen_pos: set[str] = set()
    for i, row in enumerate(rows, start=2):
        po_number = _get_field(row, "purchaseorder_number", "Purchase Order Number", "PurchaseOrder Number", "PO #", "Purchase Order ID", "PO#", required=True, source="purchase_orders", row_num=i)
        if po_number in seen_pos:
            continue
        seen_pos.add(po_number)
        po_status = _get_field(row, "order status", "purchase_order_status", "Purchase Order Status", "PO Status", "Status", "Order Status", required=True, source="purchase_orders", row_num=i)
        if po_status.lower() in ("cancelled", "void", "closed"):
            continue
        vendor_name = _get_field(row, "vendor_name", "Vendor Name", "Vendor", "Vendor_Name", required=True, source="purchase_orders", row_num=i)
        po_date_raw = _get_field(row, "date", "Purchase Order Date", "PO Date", "Order Date", "Date", required=True, source="purchase_orders", row_num=i)
        total_raw = _get_field(row, "bcy_total", "total", "Total", "Total Amount", "SubTotal", required=True, source="purchase_orders", row_num=i)
        po_date = _parse_date(po_date_raw)
        delivery_r = _get_field(row, "delivery_date", "Delivery Date", "DeliveryDate", "CF.Estimated Delivery date ( to our warehouse )", "Expected Arrival Date")
        delivery_dt = _parse_date(delivery_r) if delivery_r else None
        total = _parse_decimal(total_raw)
        terms_raw = _get_field(row, "CF.Payment Term(Formula)", "Payment Terms", "Payment Terms (days)")
        terms = None
        if terms_raw:
            try:
                terms_int = int(float(terms_raw))
                if terms_int > 0:
                    terms = terms_int
            except (ValueError, TypeError):
                pass
        ref_num = _get_field(row, "reference_number", "Reference#", "Reference #", "Reference No")
        records.append(CanonicalRecord(
            source="purchase_orders",
            record_type="purchase_order",
            ingested_at=upload_ts,
            as_of_date=as_of,
            confidence=DataConfidence.VERIFIED_LIVE,
            payload={
                "purchaseorder_number": po_number,
                "vendor_name": vendor_name,
                "order_status": po_status.lower(),
                "date": po_date.isoformat() if po_date else None,
                "delivery_date": delivery_dt.isoformat() if delivery_dt else None,
                "total": str(total),
                "cf_payment_term_formula_unformatted": terms,
                "reference_number": ref_num or None,
            },
            raw_ref=f"row {i} of {filename}"
        ))
    return records


def parse_partially_paid_bills(file_bytes: bytes, filename: str, upload_ts: datetime, as_of: date) -> list[CanonicalRecord]:
    rows = _read_rows(file_bytes, filename)
    records = []
    seen_bills: set[str] = set()
    open_statuses = {"open", "overdue", "partially_paid", "partially paid"}
    for i, row in enumerate(rows, start=2):
        bill_num = _get_field(row, "bill_number", "Bill Number", "Bill #", "Bill ID", "Bill#", required=False, source="partially_paid_bills", row_num=i)
        if not bill_num or bill_num in seen_bills:
            continue
        seen_bills.add(bill_num)
        status = _get_field(row, "status", "Bill Status", "Status", required=True, source="partially_paid_bills", row_num=i)
        status_clean = status.lower().replace(" ", "_")
        if status_clean not in open_statuses:
            continue
        linked_po = _get_field(row, "reference_number", "PurchaseOrder", "Purchase Order Number", "Linked PO #", "PO #", "PO Number", required=False, source="partially_paid_bills", row_num=i)
        vendor = _get_field(row, "vendor_name", "Vendor Name", "Vendor", "Vendor_Name", required=True, source="partially_paid_bills", row_num=i)
        balance_r = _get_field(row, "bcy_balance", "balance", "Balance", "Balance Due", "Total", required=True, source="partially_paid_bills", row_num=i)
        due_r = _get_field(row, "due_date", "Due Date", "Bill Due Date", "DueDate", required=True, source="partially_paid_bills", row_num=i)
        balance = _parse_decimal(balance_r)
        if balance <= 0:
            continue
        due_date = _parse_date(due_r)
        records.append(CanonicalRecord(
            source="partially_paid_bills",
            record_type="bill",
            ingested_at=upload_ts,
            as_of_date=as_of,
            confidence=DataConfidence.VERIFIED_LIVE,
            payload={
                "bill_number": bill_num,
                "linked_po": linked_po or None,
                "vendor": vendor,
                "balance_due": str(balance),
                "due_date": due_date.isoformat() if due_date else None,
                "status": status_clean,
            },
            raw_ref=f"row {i} of {filename}"
        ))
    return records


def parse_sales_by_item_6mo(file_bytes: bytes, filename: str, upload_ts: datetime, as_of: date) -> list[CanonicalRecord]:
    rows = _read_rows(file_bytes, filename)
    records = []
    period_start_r = _get_field(rows[0], "Period Start", "Start Date") if rows else ""
    period_end_r = _get_field(rows[0], "Period End", "End Date") if rows else ""
    for i, row in enumerate(rows, start=2):
        item_name = _get_field(row, "item_name", "Item Name", "Item", "Item_Name", required=True, source="sales_by_item_6mo", row_num=i)
        if "SERVPRO" in item_name.upper():
            continue
        volume_raw = _get_field(row, "volume", "$ Volume", "Volume", "Sales $", "Total", required=True, source="sales_by_item_6mo", row_num=i)
        volume = _parse_decimal(volume_raw)
        qty = _get_field(row, "qty", "Qty", "Quantity")
        records.append(CanonicalRecord(
            source="sales_by_item_6mo",
            record_type="sales_by_item",
            ingested_at=upload_ts,
            as_of_date=as_of,
            confidence=DataConfidence.PERIODIC_ESTIMATE,
            payload={"item_name": item_name, "volume": str(volume), "qty": qty or None, "period_start": period_start_r or None, "period_end": period_end_r or None},
            raw_ref=f"row {i} of {filename}"
        ))
    return records


def parse_amazon_sales_6mo(file_bytes: bytes, filename: str, upload_ts: datetime, as_of: date) -> list[CanonicalRecord]:
    rows = _read_rows(file_bytes, filename)
    records = []
    for i, row in enumerate(rows, start=2):
        date_raw = _get_field(row, "date", "Date", "Sale Date", required=True, source="amazon_sales_6mo", row_num=i)
        sales_raw = _get_field(row, "sales", "Sales $", "Sales", "Amount", required=True, source="amazon_sales_6mo", row_num=i)
        sale_date = _parse_date(date_raw)
        sales = _parse_decimal(sales_raw)
        asin = _get_field(row, "asin", "ASIN")
        units = _get_field(row, "units", "Units", "Quantity", "Units Ordered")
        records.append(CanonicalRecord(
            source="amazon_sales_6mo",
            record_type="amazon_sale",
            ingested_at=upload_ts,
            as_of_date=as_of,
            confidence=DataConfidence.PERIODIC_ESTIMATE,
            payload={"asin": asin or None, "sales": str(sales), "units": units or None, "date": sale_date.isoformat() if sale_date else None},
            raw_ref=f"row {i} of {filename}"
        ))
    return records


def parse_profit_and_loss(file_bytes: bytes, filename: str, upload_ts: datetime, as_of: date) -> list[CanonicalRecord]:
    rows = _read_rows(file_bytes, filename)
    if not rows:
        return []
    sample_keys = list(rows[0].keys())
    code_keys = {"Account Code", "AccountCode", "Account #", "Account"}
    name_keys = {"Account Name", "AccountName", "Description", "Name"}
    month_cols = [k for k in sample_keys if k not in code_keys and k not in name_keys]
    records = []
    for i, row in enumerate(rows, start=2):
        acct_code = _get_field(row, "Account Code", "AccountCode", "Account #", "Account", required=True, source="profit_and_loss", row_num=i)
        acct_name = _get_field(row, "Account Name", "AccountName", "Description", "Name", required=True, source="profit_and_loss", row_num=i)
        monthly_amounts: dict[str, str] = {}
        for mc in month_cols:
            raw = row.get(mc)
            if raw is not None and str(raw).strip():
                try:
                    monthly_amounts[mc] = str(_parse_decimal(raw))
                except Exception:
                    pass
        records.append(CanonicalRecord(
            source="profit_and_loss",
            record_type="pl_line",
            ingested_at=upload_ts,
            as_of_date=as_of,
            confidence=DataConfidence.PERIODIC_ESTIMATE,
            payload={"account_code": acct_code, "account_name": acct_name, "monthly_amounts": monthly_amounts},
            raw_ref=f"row {i} of {filename}"
        ))
    return records


def parse_credit_card_statement(file_bytes: bytes, filename: str, upload_ts: datetime, as_of: date) -> list[CanonicalRecord]:
    rows = _read_rows(file_bytes, filename)
    records = []
    for i, row in enumerate(rows, start=2):
        vendor = _get_field(row, "Vendor / Description", "Vendor", "Description", required=True, source="credit_card_statement", row_num=i)
        category = _get_field(row, "Statement Category", "Category", required=True, source="credit_card_statement", row_num=i)
        amount_r = _get_field(row, "Amount", "Total", required=True, source="credit_card_statement", row_num=i)
        cycle_r = _get_field(row, "Statement Cycle End Date", "Cycle End Date", "Date", required=True, source="credit_card_statement", row_num=i)
        amount = _parse_decimal(amount_r)
        cycle_end = _parse_date(cycle_r)
        records.append(CanonicalRecord(
            source="credit_card_statement",
            record_type="cc_line",
            ingested_at=upload_ts,
            as_of_date=as_of,
            confidence=DataConfidence.VERIFIED_LIVE,
            payload={"vendor": vendor, "statement_category": category, "amount": str(amount), "statement_cycle_end": cycle_end.isoformat() if cycle_end else None},
            raw_ref=f"row {i} of {filename}"
        ))
    return records


def parse_bank_statement(file_bytes: bytes, filename: str, upload_ts: datetime, as_of: date) -> list[CanonicalRecord]:
    rows = _read_rows(file_bytes, filename)
    records = []
    for i, row in enumerate(rows, start=2):
        date_r = _get_field(row, "date", "Date", "Transaction Date")
        desc = _get_field(row, "transaction_details", "description", "Description", "Payee", "Vendor")
        net_amt_r = _get_field(row, "net_amount", "net amount", "Summary Amt.", "Amount", "Total")
        d_date = _parse_date(date_r) if date_r else None
        try:
            amt = _parse_decimal(net_amt_r) if net_amt_r else Decimal("0")
        except Exception:
            amt = Decimal("0")
        records.append(CanonicalRecord(
            source="bank_statement",
            record_type="bank_txn",
            ingested_at=upload_ts,
            as_of_date=as_of,
            confidence=DataConfidence.VERIFIED_LIVE,
            payload={"date": d_date.isoformat() if d_date else None, "description": desc, "amount": str(amt)},
            raw_ref=f"row {i} of {filename}"
        ))
    return records


SOURCE_REGISTRY: dict[str, dict] = {
    "ar_unpaid_invoices": {"parser": parse_ar_unpaid_invoices, "cadence": CadenceTier.LIVE, "blocking": True},
    "confirmed_sales_orders": {"parser": parse_confirmed_sales_orders, "cadence": CadenceTier.PERIODIC, "blocking": False},
    "purchase_orders": {"parser": parse_purchase_orders, "cadence": CadenceTier.LIVE, "blocking": True},
    "partially_paid_bills": {"parser": parse_partially_paid_bills, "cadence": CadenceTier.LIVE, "blocking": False},
    "sales_by_item_6mo": {"parser": parse_sales_by_item_6mo, "cadence": CadenceTier.PERIODIC, "blocking": False},
    "amazon_sales_6mo": {"parser": parse_amazon_sales_6mo, "cadence": CadenceTier.PERIODIC, "blocking": False},
    "profit_and_loss": {"parser": parse_profit_and_loss, "cadence": CadenceTier.PERIODIC, "blocking": False},
    "credit_card_statement": {"parser": parse_credit_card_statement, "cadence": CadenceTier.PERIODIC, "blocking": False},
    "bank_statement": {"parser": parse_bank_statement, "cadence": CadenceTier.LIVE, "blocking": False},
}


def parse_source(source_name: str, file_bytes: bytes, filename: str, as_of: Optional[date] = None) -> list[CanonicalRecord]:
    if source_name not in SOURCE_REGISTRY:
        raise ValueError(f"Unknown source '{source_name}'. Valid sources: {list(SOURCE_REGISTRY.keys())}")
    entry = SOURCE_REGISTRY[source_name]
    upload_ts = datetime.now(timezone.utc)
    effective_date = as_of or upload_ts.date()
    return entry["parser"](file_bytes, filename, upload_ts, effective_date)
