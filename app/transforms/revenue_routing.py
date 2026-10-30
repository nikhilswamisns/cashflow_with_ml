from __future__ import annotations
from datetime import date, timedelta
from typing import Any
from app.config.loader import load_corporate_accounts, load_assumptions

def is_servpro_corporate(customer_name: str) -> bool:
    if not customer_name:
        return False
    name_clean = customer_name.strip()
    corporate_list = load_corporate_accounts()
    if name_clean in corporate_list:
        return True
    norm = name_clean.lower().replace('-', ' ').replace('_', ' ')
    norm = ' '.join(norm.split())
    for acct in corporate_list:
        acct_norm = ' '.join(acct.strip().lower().replace('-', ' ').replace('_', ' ').split())
        if norm == acct_norm:
            return True
    return False

def servpro_corporate_cash_in_date(expected_shipment_date: date) -> date:
    cfg = load_assumptions()
    return expected_shipment_date + timedelta(days=cfg.servpro_corporate_net_days)

def route_sales_order(so: Any) -> dict:
    customer = ''
    if hasattr(so, 'customer_name'):
        customer = so.customer_name or ''
    elif isinstance(so, dict):
        customer = so.get('customer_name', '') or ''
    if is_servpro_corporate(customer):
        from app.models.canonical import safe_parse_date
        linked_invoice_due = None
        if isinstance(so, dict):
            linked_invoice_due = so.get('linked_invoice_due_date')
        elif hasattr(so, 'linked_invoice_due_date'):
            linked_invoice_due = so.linked_invoice_due_date
        if linked_invoice_due:
            linked_invoice_due = safe_parse_date(linked_invoice_due)
            return {'row': '1100.1', 'cash_in_date': linked_invoice_due, 'note': 'SERVPRO Corporate — invoice due_date supersedes SO estimate'}
        else:
            ship_date = None
            if isinstance(so, dict):
                sd = so.get('expected_shipment_date')
                if sd:
                    ship_date = safe_parse_date(sd)
            elif hasattr(so, 'expected_shipment_date'):
                ship_date = safe_parse_date(so.expected_shipment_date) if so.expected_shipment_date else None
            if ship_date is None:
                raise ValueError(f'SERVPRO Corporate SO has no expected_shipment_date and no linked invoice. Cannot compute cash-in date.')
            return {'row': '1100.1', 'cash_in_date': servpro_corporate_cash_in_date(ship_date), 'note': 'SERVPRO Corporate — Net-45 from expected_shipment_date'}
    else:
        return {'row': 'AR', 'cash_in_date': None, 'note': 'Standard A/R — bucketed from invoice due_date'}
