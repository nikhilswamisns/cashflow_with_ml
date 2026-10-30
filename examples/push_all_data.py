from __future__ import annotations
import json
import logging
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')

sys.path.insert(0, str(Path(__file__).parent.parent))

from zoho.client import ZohoClient, ZohoAPIError, ZohoValidationError, ZohoRateLimitError
from zoho.fetch import fetch_invoices, fetch_bills, fetch_sales_orders, fetch_purchase_orders, fetch_contacts
from zoho.transformer import (
    load_invoices, load_bills, load_sales_orders, load_purchase_orders, load_vendors
)

logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(name)s: %(message)s')

FILES = Path(__file__).parent.parent / 'Files 14th Aug'
PROGRESS_FILE = Path(__file__).parent / 'upload_progress.json'

RATE_LIMIT_SLEEP = 0.65

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except Exception:
            return {}
    return {}

def save_progress(progress: dict):
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))

def sleep_for_rate():
    time.sleep(RATE_LIMIT_SLEEP)

def build_contact_cache(client: ZohoClient) -> dict[str, str]:
    print('  Building contact cache from Zoho...', flush=True)
    contacts = fetch_contacts(client)
    cache = {}
    for c in contacts:
        name = (c.get('contact_name') or '').strip()
        cid = c.get('contact_id', '')
        if name and cid:
            cache[name.lower()] = str(cid)
    print(f'  Cached {len(cache)} contacts.', flush=True)
    return cache

def ensure_contact(client: ZohoClient, name: str, contact_type: str, cache: dict) -> str | None:
    if not name:
        return None
    key = name.strip().lower()
    if key in cache:
        return cache[key]
    try:
        resp = client.post('contacts', json_data={'contact_name': name, 'contact_type': contact_type})
        cid = resp.get('contact', {}).get('contact_id', '')
        if cid:
            cache[key] = str(cid)
            return str(cid)
        sleep_for_rate()
    except (ZohoValidationError, ZohoAPIError) as e:
        try:
            found = fetch_contacts(client, params={'contact_name': name})
            for c in found:
                if c.get('contact_name', '').strip().lower() == key:
                    cid = str(c.get('contact_id', ''))
                    if cid:
                        cache[key] = cid
                        return cid
        except Exception:
            pass
    return None

def push_entity(
    client: ZohoClient,
    label: str,
    endpoint: str,
    response_key: str,
    records: list[dict],
    existing: set[str],
    num_field: str,
    contact_field: str | None,
    contact_type: str | None,
    contact_id_field: str | None,
    contact_cache: dict,
    progress: dict,
) -> tuple[int, int, int]:
    pushed = 0
    skipped = 0
    failed = 0
    done_set: set[str] = set(progress.get(label, []))

    to_push = [r for r in records if r.get(num_field) not in existing and r.get(num_field) not in done_set]
    total = len(to_push)

    print(f'\n[{label.upper()}] {len(existing)} already in Zoho | {total} missing records queued to push', flush=True)

    for i, record in enumerate(to_push, 1):
        num = record.get(num_field, f'record-{i}')

        if contact_field and contact_id_field and contact_type:
            cname = record.get(contact_field, '').strip()
            if cname and contact_id_field not in record:
                cid = ensure_contact(client, cname, contact_type, contact_cache)
                if cid:
                    record = dict(record)
                    record[contact_id_field] = cid

        retry = 0
        while retry < 5:
            try:
                resp = client.post(endpoint, json_data=record, params={'ignore_auto_number_generation': 'true'})
                pushed += 1
                done_set.add(num)
                if i % 10 == 0 or i == total:
                    progress[label] = list(done_set)
                    save_progress(progress)
                    pct = round(i / total * 100)
                    print(f'  [{label}] {i}/{total} ({pct}%) pushed | latest: {num}', flush=True)
                sleep_for_rate()
                break
            except ZohoRateLimitError:
                wait = 60 + (retry * 30)
                print(f'  Rate limited. Sleeping {wait}s...', flush=True)
                time.sleep(wait)
                retry += 1
            except ZohoValidationError as e:
                if 'already exists' in str(e).lower():
                    skipped += 1
                    done_set.add(num)
                else:
                    failed += 1
                    print(f'  [{label}] Validation error on {num}: {e}', flush=True)
                break
            except (ZohoAPIError, Exception) as e:
                retry += 1
                if retry < 5:
                    time.sleep(2.0 * retry)
                    continue
                failed += 1
                print(f'  [{label}] Error on {num}: {e}', flush=True)
                break

    progress[label] = list(done_set)
    save_progress(progress)
    print(f'  [{label}] Finished: pushed={pushed}, skipped/existing={skipped}, failed={failed}', flush=True)
    return pushed, skipped, failed

def main():
    print('=== ZOHO BOOKS — UPLOAD ALL SYSTEM DATA ===\n', flush=True)
    client = ZohoClient()
    progress = load_progress()

    print('Step 1/5 — Loading local Excel files...', flush=True)
    local_vendors = load_vendors(str(FILES / 'Vendors (1).xlsx'))
    local_invoices = load_invoices(str(FILES / 'Invoice (2).xlsx'))
    local_bills = load_bills(str(FILES / 'Bill (1).xlsx'))
    local_sos = load_sales_orders(str(FILES / 'Sales_Order (1).xlsx'))
    local_pos = load_purchase_orders(str(FILES / 'Purchase_Order (2).xlsx'))
    print(f'  Loaded: {len(local_vendors)} vendors, {len(local_invoices)} invoices, '
          f'{len(local_bills)} bills, {len(local_sos)} SOs, {len(local_pos)} POs\n', flush=True)

    print('Step 2/5 — Fetching existing Zoho records (deduplication)...', flush=True)
    zoho_invoices = fetch_invoices(client)
    zoho_bills = fetch_bills(client)
    zoho_sos = fetch_sales_orders(client)
    zoho_pos = fetch_purchase_orders(client)

    existing_inv = {r.get('invoice_number', '').strip() for r in zoho_invoices if r.get('invoice_number')}
    existing_bill = {r.get('bill_number', '').strip() for r in zoho_bills if r.get('bill_number')}
    existing_so = {r.get('salesorder_number', '').strip() for r in zoho_sos if r.get('salesorder_number')}
    existing_po = {r.get('purchaseorder_number', '').strip() for r in zoho_pos if r.get('purchaseorder_number')}

    print(f'  In Zoho currently — Invoices: {len(existing_inv)}, Bills: {len(existing_bill)}, '
          f'SOs: {len(existing_so)}, POs: {len(existing_po)}\n', flush=True)

    print('Step 3/5 — Building contact cache...', flush=True)
    contact_cache = build_contact_cache(client)

    print('\nStep 4/5 — Uploading missing vendors...', flush=True)
    existing_contacts = set(contact_cache.keys())
    v_pushed = v_failed = 0
    for v in local_vendors:
        name = v.get('contact_name', '').strip()
        if not name or name.lower() in existing_contacts:
            continue
        try:
            resp = client.post('contacts', json_data=v)
            cid = resp.get('contact', {}).get('contact_id', '')
            if cid:
                contact_cache[name.lower()] = str(cid)
            v_pushed += 1
            sleep_for_rate()
        except (ZohoValidationError, ZohoAPIError):
            v_failed += 1
    print(f'  Vendors — pushed: {v_pushed}, failed: {v_failed}\n', flush=True)

    print('Step 5/5 — Uploading missing Invoices, Bills, Sales Orders, Purchase Orders...', flush=True)
    results = {}

    try:
        p, s, f = push_entity(
            client, 'invoices', 'invoices', 'invoice', local_invoices,
            existing_inv, 'invoice_number', 'customer_name', 'customer', 'customer_id',
            contact_cache, progress
        )
        results['invoices'] = (p, s, f)
    except Exception as e:
        print(f'Error processing invoices: {e}', flush=True)

    try:
        p, s, f = push_entity(
            client, 'bills', 'bills', 'bill', local_bills,
            existing_bill, 'bill_number', 'vendor_name', 'vendor', 'vendor_id',
            contact_cache, progress
        )
        results['bills'] = (p, s, f)
    except Exception as e:
        print(f'Error processing bills: {e}', flush=True)

    try:
        p, s, f = push_entity(
            client, 'salesorders', 'salesorders', 'salesorder', local_sos,
            existing_so, 'salesorder_number', 'customer_name', 'customer', 'customer_id',
            contact_cache, progress
        )
        results['salesorders'] = (p, s, f)
    except Exception as e:
        print(f'Error processing sales orders: {e}', flush=True)

    try:
        p, s, f = push_entity(
            client, 'purchaseorders', 'purchaseorders', 'purchaseorder', local_pos,
            existing_po, 'purchaseorder_number', 'vendor_name', 'vendor', 'vendor_id',
            contact_cache, progress
        )
        results['purchaseorders'] = (p, s, f)
    except Exception as e:
        print(f'Error processing purchase orders: {e}', flush=True)

    print('\n=== ALL SYSTEM DATA UPLOADED SUCCESSFULLY ===', flush=True)
    print(f'{"Entity":<20} {"Pushed":>8} {"Skipped":>10} {"Failed":>8}', flush=True)
    print('-' * 50, flush=True)
    for entity, (p, s, f) in results.items():
        print(f'{entity:<20} {p:>8} {s:>10} {f:>8}', flush=True)
    print('\nDone!', flush=True)

if __name__ == '__main__':
    main()
