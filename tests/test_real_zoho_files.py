import os
import pytest
from datetime import date
from pathlib import Path
from app.adapters.file_upload import parse_source
from app.models.canonical import DataConfidence
FOLDER = Path('/Users/ankitkumar/Desktop/cashflow-2/Files 14th Aug')

@pytest.mark.skipif(not FOLDER.exists(), reason='Files 14th Aug directory not present')
def test_parse_real_invoices():
    path = FOLDER / 'Invoice (2).xlsx'
    with open(path, 'rb') as f:
        content = f.read()
    records = parse_source('ar_unpaid_invoices', content, path.name, as_of=date(2026, 8, 14))
    assert len(records) > 0
    inv_nums = [r.payload['invoice_number'] for r in records]
    assert len(inv_nums) == len(set(inv_nums))
    assert all((r.confidence == DataConfidence.VERIFIED_LIVE for r in records))

@pytest.mark.skipif(not FOLDER.exists(), reason='Files 14th Aug directory not present')
def test_parse_real_purchase_orders():
    path = FOLDER / 'Purchase_Order (2).xlsx'
    with open(path, 'rb') as f:
        content = f.read()
    records = parse_source('purchase_orders', content, path.name, as_of=date(2026, 8, 14))
    assert len(records) > 0
    po_nums = [r.payload['purchaseorder_number'] for r in records]
    assert len(po_nums) == len(set(po_nums))
    assert all((r.confidence == DataConfidence.VERIFIED_LIVE for r in records))

@pytest.mark.skipif(not FOLDER.exists(), reason='Files 14th Aug directory not present')
def test_parse_real_sales_orders():
    path = FOLDER / 'Sales_Order (1).xlsx'
    with open(path, 'rb') as f:
        content = f.read()
    records = parse_source('confirmed_sales_orders', content, path.name, as_of=date(2026, 8, 14))
    assert len(records) > 0
    so_nums = [r.payload['salesorder_number'] for r in records]
    assert len(so_nums) == len(set(so_nums))
    assert all((r.confidence == DataConfidence.VERIFIED_LIVE for r in records))

@pytest.mark.skipif(not FOLDER.exists(), reason='Files 14th Aug directory not present')
def test_parse_real_bills():
    path = FOLDER / 'Bill (1).xlsx'
    with open(path, 'rb') as f:
        content = f.read()
    records = parse_source('partially_paid_bills', content, path.name, as_of=date(2026, 8, 14))
    assert len(records) > 0
    bill_nums = [r.payload['bill_number'] for r in records]
    assert len(bill_nums) == len(set(bill_nums))
    assert all((r.confidence == DataConfidence.VERIFIED_LIVE for r in records))
