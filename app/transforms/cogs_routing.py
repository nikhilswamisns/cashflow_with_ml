from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from app.config.loader import load_freight_duty, load_assumptions

@dataclass
class PurchaseOrderFields:
    vendor_name: str
    order_status: str
    date: date | None
    delivery_date: date | None
    total: float | str
    cf_payment_term_formula_unformatted: int | None = None
    reference_number: str | None = None

def cogs_category(po: Any) -> str:
    cfg = load_freight_duty()
    if isinstance(po, dict):
        vendor_name = (po.get('vendor_name') or '').strip()
        reference = po.get('reference_number') or ''
    else:
        vendor_name = (getattr(po, 'vendor_name', None) or '').strip()
        reference = getattr(po, 'reference_number', None) or ''
    if vendor_name in cfg.duty_vendors_exact:
        return '3102_inbound_duty'
    if vendor_name in cfg.freight_vendors_exact:
        return '3101_inbound_freight'
    for substring in cfg.freight_reference_substrings:
        if substring in reference:
            return '3101_inbound_freight'
    return '3100_cogs_standard'

def po_due_date(po: Any) -> date:
    from app.models.canonical import safe_parse_date
    cfg = load_assumptions()
    default_terms = cfg.po_default_payment_terms_days
    delivery_date = None
    po_date = None
    if isinstance(po, dict):
        delivery_raw = po.get('delivery_date')
        po_date_raw = po.get('date')
        if delivery_raw:
            delivery_date = safe_parse_date(delivery_raw)
        if po_date_raw:
            po_date = safe_parse_date(po_date_raw)
    else:
        if hasattr(po, 'delivery_date') and po.delivery_date:
            delivery_date = safe_parse_date(po.delivery_date)
        if hasattr(po, 'date') and po.date:
            po_date = safe_parse_date(po.date)
    base_date = delivery_date if delivery_date and (po_date is None or delivery_date >= po_date) else po_date
    if base_date is None:
        raise ValueError('PO has neither delivery_date nor date — cannot compute due date. This should never happen; both fields are required in the schema.')
    vendor_name = (po.get('vendor_name', '') if isinstance(po, dict) else getattr(po, 'vendor_name', '') or '').strip()
    terms_days = None
    if isinstance(po, dict):
        terms_days = po.get('cf_payment_term_formula_unformatted')
    elif hasattr(po, 'cf_payment_term_formula_unformatted'):
        terms_days = po.cf_payment_term_formula_unformatted
    if (terms_days is None or str(terms_days).strip() == '' or str(terms_days).strip() == 'None') and vendor_name in cfg.vendor_payment_terms_days:
        terms_days = cfg.vendor_payment_terms_days[vendor_name]
    else:
        try:
            terms_days = int(terms_days) if terms_days is not None and str(terms_days).strip() != '' else default_terms
        except (ValueError, TypeError):
            terms_days = default_terms
    return base_date + timedelta(days=terms_days)
