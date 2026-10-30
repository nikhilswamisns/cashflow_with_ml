from __future__ import annotations
import logging
from typing import Any, Optional, Union
from zoho.client import ZohoClient

logger = logging.getLogger('zoho.push')

def _ensure_list(records: Union[dict[str, Any], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    if isinstance(records, dict):
        return [records]
    return list(records)

def _ensure_contact_id(client: ZohoClient, name: str, contact_type: str) -> Optional[str]:
    if not name:
        return None
    try:
        from zoho.fetch import fetch_contacts
        contacts = fetch_contacts(client, params={'contact_name': name})
        for c in contacts:
            if c.get('contact_name', '').strip().lower() == name.strip().lower():
                return c.get('contact_id')
        created = push_contacts(client, {'contact_name': name, 'contact_type': contact_type})
        if created:
            return created[0].get('contact_id')
    except Exception as e:
        logger.warning('Could not resolve or create contact %s: %e', name, e)
    return None

def push_invoices(client: ZohoClient, invoices: Union[dict[str, Any], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    items = _ensure_list(invoices)
    results = []
    for inv in items:
        inv_payload = dict(inv)
        if 'customer_id' not in inv_payload and 'customer_name' in inv_payload:
            c_id = _ensure_contact_id(client, inv_payload['customer_name'], 'customer')
            if c_id:
                inv_payload['customer_id'] = c_id
        resp = client.post('invoices', json_data=inv_payload, params={'ignore_auto_number_generation': 'true'})
        created = resp.get('invoice', resp)
        results.append(created)
        logger.info('Pushed invoice: %s', created.get('invoice_number', 'N/A'))
    return results

def push_bills(client: ZohoClient, bills: Union[dict[str, Any], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    items = _ensure_list(bills)
    results = []
    for bill in items:
        bill_payload = dict(bill)
        if 'vendor_id' not in bill_payload and 'vendor_name' in bill_payload:
            v_id = _ensure_contact_id(client, bill_payload['vendor_name'], 'vendor')
            if v_id:
                bill_payload['vendor_id'] = v_id
        resp = client.post('bills', json_data=bill_payload, params={'ignore_auto_number_generation': 'true'})
        created = resp.get('bill', resp)
        results.append(created)
        logger.info('Pushed bill: %s', created.get('bill_number', 'N/A'))
    return results

def push_sales_orders(client: ZohoClient, sales_orders: Union[dict[str, Any], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    items = _ensure_list(sales_orders)
    results = []
    for so in items:
        so_payload = dict(so)
        if 'customer_id' not in so_payload and 'customer_name' in so_payload:
            c_id = _ensure_contact_id(client, so_payload['customer_name'], 'customer')
            if c_id:
                so_payload['customer_id'] = c_id
        resp = client.post('salesorders', json_data=so_payload, params={'ignore_auto_number_generation': 'true'})
        created = resp.get('salesorder', resp)
        results.append(created)
        logger.info('Pushed sales order: %s', created.get('salesorder_number', 'N/A'))
    return results

def push_purchase_orders(client: ZohoClient, purchase_orders: Union[dict[str, Any], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    items = _ensure_list(purchase_orders)
    results = []
    for po in items:
        po_payload = dict(po)
        if 'vendor_id' not in po_payload and 'vendor_name' in po_payload:
            v_id = _ensure_contact_id(client, po_payload['vendor_name'], 'vendor')
            if v_id:
                po_payload['vendor_id'] = v_id
        resp = client.post('purchaseorders', json_data=po_payload, params={'ignore_auto_number_generation': 'true'})
        created = resp.get('purchaseorder', resp)
        results.append(created)
        logger.info('Pushed purchase order: %s', created.get('purchaseorder_number', 'N/A'))
    return results

def push_contacts(client: ZohoClient, contacts: Union[dict[str, Any], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    items = _ensure_list(contacts)
    results = []
    for contact in items:
        resp = client.post('contacts', json_data=contact)
        created = resp.get('contact', resp)
        results.append(created)
        logger.info('Pushed contact: %s', created.get('contact_name', 'N/A'))
    return results

def push_items(client: ZohoClient, items: Union[dict[str, Any], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    record_list = _ensure_list(items)
    results = []
    for it in record_list:
        resp = client.post('items', json_data=it)
        created = resp.get('item', resp)
        results.append(created)
        logger.info('Pushed item: %s', created.get('name', 'N/A'))
    return results
