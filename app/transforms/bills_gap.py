from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from app.models.canonical import DataConfidence
from app.models.matrix import LineItem
from app.transforms.cogs_routing import po_due_date

@dataclass
class BillRecord:
    linked_po: str
    balance_due: Decimal
    due_date: date
    status: str

def cogs_amount_and_date(po: Any, bills_by_po_number: dict[str, BillRecord], coa_code: str, label: str) -> LineItem | None:
    po_number = None
    if hasattr(po, 'purchaseorder_number'):
        po_number = po.purchaseorder_number
    elif isinstance(po, dict):
        po_number = po.get('purchaseorder_number')
    po_status = ''
    if hasattr(po, 'order_status'):
        po_status = po.order_status or ''
    elif isinstance(po, dict):
        po_status = po.get('order_status', '') or ''
    po_status = po_status.lower()
    if po_status == 'cancelled':
        return None
    po_total = Decimal('0')
    if hasattr(po, 'total'):
        po_total = Decimal(str(po.total or 0))
    elif isinstance(po, dict):
        po_total = Decimal(str(po.get('total', 0) or 0))
    try:
        computed_due = po_due_date(po)
    except ValueError:
        computed_due = None
    raw_ref = None
    if hasattr(po, 'purchaseorder_number'):
        raw_ref = f'PO {po_number}'
    elif isinstance(po, dict):
        raw_ref = f"PO {po.get('purchaseorder_number', 'unknown')}"
    matching_bill = bills_by_po_number.get(po_number or '')
    if matching_bill is not None:
        return LineItem(amount=matching_bill.balance_due, confidence=DataConfidence.VERIFIED_LIVE, coa_code=coa_code, label=label, raw_ref=f'{raw_ref} (superseded by bill record)')
    if po_status in ('open', 'draft'):
        return LineItem(amount=po_total, confidence=DataConfidence.VERIFIED_LIVE, coa_code=coa_code, label=label, raw_ref=raw_ref)
    return LineItem(amount=po_total, confidence=DataConfidence.ESTIMATE_BILLS_GAP, coa_code=coa_code, label=label, raw_ref=f'{raw_ref} (closed PO — no bill on file, Bills Gap)')

def build_bills_index(bill_records: list[Any]) -> dict[str, BillRecord]:
    index: dict[str, BillRecord] = {}
    for record in bill_records:
        payload = record.payload if hasattr(record, 'payload') else record
        linked_po = payload.get('linked_po', '')
        if not linked_po:
            continue
        balance_raw = payload.get('balance_due', '0')
        due_raw = payload.get('due_date')
        status = payload.get('status', '')
        from app.models.canonical import safe_parse_date
        index[linked_po] = BillRecord(linked_po=linked_po, balance_due=Decimal(str(balance_raw or 0)), due_date=safe_parse_date(due_raw), status=status)
    return index
