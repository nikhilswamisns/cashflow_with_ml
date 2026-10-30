import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from zoho.auth import ZohoAuth
from zoho.client import ZohoClient
from zoho.fetch import fetch_bills, fetch_invoices
from zoho.push import push_bills, push_invoices

def run_end_to_end_example():
    auth = ZohoAuth()
    try:
        auth.validate_configuration()
    except Exception as e:
        print(f'Configuration check: {e}')
        print('Please set ZOHO_REFRESH_TOKEN and ZOHO_ORG_ID in .env to run live API calls.')
        return

    client = ZohoClient(auth=auth)

    sample_invoice = {
        'customer_name': 'SERVPRO Corporate',
        'date': '2026-08-25',
        'due_date': '2026-09-08',
        'line_items': [
            {
                'name': 'Dehumidifier Units',
                'description': 'Commercial restoration equipment',
                'rate': 42185.80,
                'quantity': 1,
            }
        ],
    }

    print('1. Pushing sample invoice to Zoho Books...')
    try:
        created_invoices = push_invoices(client, sample_invoice)
        print(f'Successfully created {len(created_invoices)} invoice(s).')
    except Exception as e:
        print(f'Push invoice note/error: {e}')

    print('\n2. Fetching invoices back from Zoho Books as Pandas DataFrame...')
    try:
        df_invoices = fetch_invoices(client, as_df=True)
        print(f'Retrieved {len(df_invoices)} invoice record(s) from Zoho Books:')
        print(df_invoices[['invoice_number', 'customer_name', 'total', 'status', 'due_date']])
    except Exception as e:
        print(f'Fetch invoice error: {e}')

if __name__ == '__main__':
    run_end_to_end_example()
