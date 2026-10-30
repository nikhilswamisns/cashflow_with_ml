from __future__ import annotations
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
import pandas as pd


def _s(val: Any) -> str:
    if val is None:
        return ''
    s = str(val).strip()
    return '' if s.lower() in ('nan', 'none', '') else s


def _num(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float, Decimal)):
        return 0.0 if str(val) in ('nan', 'inf') else float(val)
    cleaned = str(val).replace(',', '').replace('$', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _date(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.strftime('%Y-%m-%d')
    s = str(val).strip()
    if s.lower() in ('nan', 'none', ''):
        return None
    if ' ' in s:
        s = s.split(' ')[0]
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def sanitize_doc_num(num: str, max_len: int = 16) -> str:
    if not num:
        return ''
    s = re.sub(r'[\s_]+', '-', num.strip())
    s = re.sub(r'[^a-zA-Z0-9\-/]', '', s)
    return s[:max_len]


def load_invoices(path: str) -> list[dict[str, Any]]:
    df = pd.read_excel(path, dtype=str)
    df = df.where(pd.notna(df), None)
    today = datetime.now().strftime('%Y-%m-%d')
    results = []
    for raw_num, grp in df.groupby('Invoice Number', dropna=True):
        first = grp.iloc[0]
        inv_date = _date(first.get('Invoice Date')) or today
        due_date = _date(first.get('Due Date')) or inv_date
        customer = _s(first.get('Customer Name'))
        if not customer:
            continue
        line_items = []
        for _, row in grp.iterrows():
            item_name = _s(row.get('Item Name')) or 'Invoice Line Item'
            qty = _num(row.get('Quantity')) or 1.0
            rate = _num(row.get('Item Price')) or _num(row.get('Total'))
            if rate == 0.0:
                rate = _num(row.get('Item Total'))
            line_items.append({'name': item_name, 'rate': rate, 'quantity': qty})
        if not line_items:
            continue
        clean_num = sanitize_doc_num(_s(raw_num))
        ref = _s(first.get('PurchaseOrder')) or _s(raw_num) if clean_num != _s(raw_num) else None
        results.append({
            'customer_name': customer,
            'invoice_number': clean_num,
            'date': inv_date,
            'due_date': due_date,
            'reference_number': ref,
            'line_items': line_items,
        })
    return results


def load_bills(path: str) -> list[dict[str, Any]]:
    df = pd.read_excel(path, dtype=str)
    df = df.where(pd.notna(df), None)
    today = datetime.now().strftime('%Y-%m-%d')
    results = []
    for raw_num, grp in df.groupby('Bill Number', dropna=True):
        first = grp.iloc[0]
        bill_date = _date(first.get('Bill Date')) or today
        due_date = _date(first.get('Due Date')) or bill_date
        vendor = _s(first.get('Vendor Name'))
        if not vendor:
            continue
        line_items = []
        for _, row in grp.iterrows():
            item_name = _s(row.get('Item Name')) or _s(row.get('Description')) or 'Bill Line Item'
            account = _s(row.get('Account')) or 'Cost of Goods Sold'
            qty = _num(row.get('Quantity')) or 1.0
            rate = _num(row.get('Rate')) or _num(row.get('Item Price'))
            if rate == 0.0:
                rate = _num(row.get('Item Total'))
            line_items.append({'account_name': account, 'description': item_name, 'rate': rate, 'quantity': qty})
        if not line_items:
            continue
        clean_num = sanitize_doc_num(_s(raw_num))
        results.append({
            'vendor_name': vendor,
            'bill_number': clean_num,
            'date': bill_date,
            'due_date': due_date,
            'line_items': line_items,
        })
    return results


def load_sales_orders(path: str) -> list[dict[str, Any]]:
    df = pd.read_excel(path, dtype=str)
    df = df.where(pd.notna(df), None)
    today = datetime.now().strftime('%Y-%m-%d')
    results = []
    for raw_num, grp in df.groupby('SalesOrder Number', dropna=True):
        first = grp.iloc[0]
        so_date = _date(first.get('Order Date')) or today
        ship_date = _date(first.get('Expected Shipment Date')) or so_date
        customer = _s(first.get('Customer Name'))
        if not customer:
            continue
        line_items = []
        for _, row in grp.iterrows():
            item_name = _s(row.get('Item Name')) or 'Sales Order Item'
            qty = _num(row.get('QuantityOrdered')) or 1.0
            rate = _num(row.get('Item Price'))
            if rate == 0.0:
                rate = _num(row.get('Item Total'))
            line_items.append({'name': item_name, 'rate': rate, 'quantity': qty})
        if not line_items:
            continue
        clean_num = sanitize_doc_num(_s(raw_num))
        ref = _s(first.get('Reference#')) or (_s(raw_num) if clean_num != _s(raw_num) else None)
        results.append({
            'customer_name': customer,
            'salesorder_number': clean_num,
            'date': so_date,
            'shipment_date': ship_date,
            'reference_number': ref,
            'line_items': line_items,
        })
    return results


def load_purchase_orders(path: str) -> list[dict[str, Any]]:
    df = pd.read_excel(path, dtype=str)
    df = df.where(pd.notna(df), None)
    today = datetime.now().strftime('%Y-%m-%d')
    results = []
    for raw_num, grp in df.groupby('Purchase Order Number', dropna=True):
        first = grp.iloc[0]
        po_date = _date(first.get('Purchase Order Date')) or today
        del_date = _date(first.get('Delivery Date')) or po_date
        vendor = _s(first.get('Vendor Name'))
        if not vendor:
            continue
        line_items = []
        for _, row in grp.iterrows():
            item_name = _s(row.get('Item Name')) or 'Purchase Order Item'
            account = _s(row.get('Account')) or None
            qty = _num(row.get('QuantityOrdered')) or 1.0
            rate = _num(row.get('Item Price'))
            if rate == 0.0:
                rate = _num(row.get('Item Total'))
            entry = {'name': item_name, 'rate': rate, 'quantity': qty}
            if account:
                entry['account_name'] = account
            line_items.append(entry)
        if not line_items:
            continue
        clean_num = sanitize_doc_num(_s(raw_num))
        results.append({
            'vendor_name': vendor,
            'purchaseorder_number': clean_num,
            'date': po_date,
            'delivery_date': del_date,
            'line_items': line_items,
        })
    return results


def load_vendors(path: str) -> list[dict[str, Any]]:
    df = pd.read_excel(path, dtype=str)
    df = df.where(pd.notna(df), None)
    results = []
    seen = set()
    for _, row in df.iterrows():
        name = _s(row.get('Contact Name')) or _s(row.get('Display Name')) or _s(row.get('Company Name'))
        if not name or name in seen:
            continue
        seen.add(name)
        status = _s(row.get('Status'))
        results.append({
            'contact_name': name,
            'company_name': _s(row.get('Company Name')) or None,
            'contact_type': 'vendor',
            'email': _s(row.get('EmailID')) or None,
            'phone': _s(row.get('Phone')) or None,
            'status': 'active' if status.lower() == 'active' else 'inactive',
            'billing_address': {
                'address': _s(row.get('Billing Address')) or None,
                'city': _s(row.get('Billing City')) or None,
                'state': _s(row.get('Billing State')) or None,
                'zip': _s(row.get('Billing Code')) or None,
                'country': _s(row.get('Billing Country')) or None,
            },
        })
    return results


def transform_invoice_row(row: dict[str, Any]) -> dict[str, Any]:
    amount = _num(row.get('Balance') or row.get('Amount') or 0)
    return {
        'customer_name': _s(row.get('Customer Name')),
        'invoice_number': _s(row.get('Invoice Number')),
        'date': _date(row.get('Invoice Date')) or _date(row.get('Date')),
        'due_date': _date(row.get('Due Date')),
        'line_items': [{'description': 'Invoice charge', 'rate': amount, 'quantity': 1}],
    }


def transform_bill_row(row: dict[str, Any]) -> dict[str, Any]:
    amount = _num(row.get('Balance') or row.get('Amount') or 0)
    return {
        'vendor_name': _s(row.get('Vendor Name')),
        'bill_number': _s(row.get('Bill Number')),
        'date': _date(row.get('Bill Date')) or _date(row.get('Date')),
        'due_date': _date(row.get('Due Date')),
        'account_name': _s(row.get('Account') or 'Cost of Goods Sold'),
        'line_items': [{'description': 'Bill charge', 'rate': amount, 'quantity': 1}],
    }


def transform_sales_order_row(row: dict[str, Any]) -> dict[str, Any]:
    amount = _num(row.get('Amount') or row.get('Total') or 0)
    return {
        'customer_name': _s(row.get('Customer Name')),
        'salesorder_number': _s(row.get('SalesOrder Number') or row.get('Sales Order Number')),
        'date': _date(row.get('Date') or row.get('Order Date')),
        'shipment_date': _date(row.get('Expected Shipment Date') or row.get('Shipment Date')),
        'line_items': [{'description': 'Sales order item', 'rate': amount, 'quantity': 1}],
    }


def transform_purchase_order_row(row: dict[str, Any]) -> dict[str, Any]:
    amount = _num(row.get('Amount') or row.get('Total') or 0)
    return {
        'vendor_name': _s(row.get('Vendor Name')),
        'purchaseorder_number': _s(row.get('PurchaseOrder Number') or row.get('Purchase Order Number')),
        'date': _date(row.get('Date') or row.get('Order Date')),
        'delivery_date': _date(row.get('Delivery Date') or row.get('Expected Delivery Date')),
        'line_items': [{'description': 'Purchase order item', 'rate': amount, 'quantity': 1}],
    }


def transform_vendor_row(row: dict[str, Any]) -> dict[str, Any]:
    name = _s(row.get('Vendor Name') or row.get('Contact Name') or row.get('Display Name'))
    return {
        'contact_name': name,
        'contact_type': 'vendor',
        'email': _s(row.get('Email') or row.get('EmailID')),
        'phone': _s(row.get('Phone')),
    }
