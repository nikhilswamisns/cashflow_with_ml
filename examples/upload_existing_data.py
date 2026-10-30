import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from zoho.auth import ZohoAuth
from zoho.client import ZohoClient
from zoho.push import push_bills, push_contacts, push_invoices
from zoho.transformer import (
    excel_to_records,
    transform_bill_row,
    transform_invoice_row,
    transform_vendor_row,
)

def upload_local_files(dry_run: bool = True):
    base_dir = Path(__file__).parent.parent / 'Files 14th Aug'
    if not base_dir.exists():
        print(f'Directory {base_dir} not found.')
        return

    inv_file = base_dir / 'Invoice (2).xlsx'
    bill_file = base_dir / 'Bill (1).xlsx'
    vendor_file = base_dir / 'Vendors (1).xlsx'

    client = None
    if not dry_run:
        auth = ZohoAuth()
        auth.validate_configuration()
        client = ZohoClient(auth=auth)

    if inv_file.exists():
        rows = excel_to_records(str(inv_file))
        print(f'Loaded {len(rows)} raw invoice rows from {inv_file.name}.')
        transformed = [transform_invoice_row(r) for r in rows[:5]]
        print(f'Sample transformed invoice payload:\n{transformed[0]}')
        if not dry_run and client:
            print(f'Uploading {len(transformed)} invoices to Zoho Books...')
            push_invoices(client, transformed)

    if bill_file.exists():
        rows = excel_to_records(str(bill_file))
        print(f'\nLoaded {len(rows)} raw bill rows from {bill_file.name}.')
        transformed = [transform_bill_row(r) for r in rows[:5]]
        print(f'Sample transformed bill payload:\n{transformed[0]}')
        if not dry_run and client:
            print(f'Uploading {len(transformed)} bills to Zoho Books...')
            push_bills(client, transformed)

    if vendor_file.exists():
        rows = excel_to_records(str(vendor_file))
        print(f'\nLoaded {len(rows)} raw vendor rows from {vendor_file.name}.')
        transformed = [transform_vendor_row(r) for r in rows[:5]]
        print(f'Sample transformed vendor payload:\n{transformed[0]}')
        if not dry_run and client:
            print(f'Uploading {len(transformed)} contacts to Zoho Books...')
            push_contacts(client, transformed)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Execute live push to Zoho Books')
    args = parser.parse_args()
    upload_local_files(dry_run=not args.live)
