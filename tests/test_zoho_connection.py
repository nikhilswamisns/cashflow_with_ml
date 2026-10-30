from __future__ import annotations
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
import requests
from zoho.auth import ZohoAuth, ZohoAuthError
from zoho.client import (
    ZohoAPIError,
    ZohoClient,
    ZohoPermissionError,
    ZohoRateLimitError,
    ZohoValidationError,
)
from zoho.fetch import fetch_bills, fetch_invoices, fetch_organizations
from zoho.push import push_bills, push_invoices
from zoho.transformer import (
    transform_bill_row,
    transform_invoice_row,
    transform_purchase_order_row,
    transform_sales_order_row,
    transform_vendor_row,
)

def test_auth_config_validation():
    auth = ZohoAuth(client_id='', client_secret='', refresh_token='')
    with pytest.raises(ZohoAuthError, match='ZOHO_CLIENT_ID is missing'):
        auth.validate_configuration()

    auth2 = ZohoAuth(client_id='1000.TEST', client_secret='', refresh_token='')
    with pytest.raises(ZohoAuthError, match='ZOHO_CLIENT_SECRET is missing'):
        auth2.validate_configuration()

    auth3 = ZohoAuth(client_id='1000.TEST', client_secret='secret123', refresh_token='')
    with pytest.raises(ZohoAuthError, match='ZOHO_REFRESH_TOKEN is missing'):
        auth3.validate_configuration(require_refresh_token=True)

@patch('requests.post')
def test_auth_refresh_access_token(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        'access_token': '1000.sample_access_token',
        'expires_in_sec': 3600,
        'api_domain': 'https://www.zohoapis.com',
        'token_type': 'Bearer',
    }
    mock_post.return_value = mock_resp

    auth = ZohoAuth(
        client_id='1000.TEST',
        client_secret='secret123',
        refresh_token='1000.refreshtoken',
    )
    token = auth.get_access_token()
    assert token == '1000.sample_access_token'
    assert auth._access_token == '1000.sample_access_token'
    assert auth._token_expiry is not None

    token2 = auth.get_access_token(force_refresh=False)
    assert token2 == '1000.sample_access_token'
    assert mock_post.call_count == 1

@patch('requests.post')
def test_auth_exchange_grant_token(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        'access_token': '1000.sample_access_token',
        'refresh_token': '1000.new_refresh_token',
        'expires_in_sec': 3600,
    }
    mock_post.return_value = mock_resp

    auth = ZohoAuth(client_id='1000.TEST', client_secret='secret123')
    res = auth.exchange_grant_token('1000.grant_code')
    assert res['refresh_token'] == '1000.new_refresh_token'
    assert auth.refresh_token == '1000.new_refresh_token'

@patch('requests.request')
def test_client_request_headers_and_params(mock_req):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        'code': 0,
        'message': 'success',
        'invoices': [{'invoice_id': 'inv_1', 'invoice_number': 'INV-001'}],
    }
    mock_req.return_value = mock_resp

    auth = ZohoAuth(client_id='1000.TEST', client_secret='secret123', refresh_token='1000.ref')
    auth._access_token = 'mock_valid_token'
    from datetime import datetime, timedelta, timezone
    auth._token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    client = ZohoClient(auth=auth, org_id='888999')
    resp = client.get('invoices', params={'status': 'unpaid'})

    mock_req.assert_called_once()
    kwargs = mock_req.call_args.kwargs
    assert kwargs['headers']['Authorization'] == 'Zoho-oauthtoken mock_valid_token'
    assert kwargs['params']['organization_id'] == '888999'
    assert kwargs['params']['status'] == 'unpaid'
    assert resp['code'] == 0

@patch('requests.request')
def test_client_401_auto_refresh(mock_req):
    resp_401 = MagicMock()
    resp_401.status_code = 401
    resp_401.text = 'Unauthorized'

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {'code': 0, 'invoices': []}

    mock_req.side_effect = [resp_401, resp_200]

    auth = ZohoAuth(client_id='1000.TEST', client_secret='secret123', refresh_token='1000.ref')
    auth._access_token = 'initial_token'
    from datetime import datetime, timedelta, timezone
    auth._token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    auth._refresh_access_token = MagicMock(return_value='new_mock_token')

    client = ZohoClient(auth=auth, org_id='888999')
    res = client.get('invoices')
    assert res['code'] == 0
    assert auth._refresh_access_token.call_count == 1

@patch('requests.request')
def test_client_error_handling(mock_req):
    resp_403 = MagicMock()
    resp_403.status_code = 403
    resp_403.text = 'Invalid Scope'
    mock_req.return_value = resp_403

    auth = ZohoAuth(client_id='1000.TEST', client_secret='secret123', refresh_token='1000.ref')
    auth._access_token = 'token'
    from datetime import datetime, timedelta, timezone
    auth._token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    client = ZohoClient(auth=auth, org_id='888999')
    with pytest.raises(ZohoPermissionError):
        client.get('invoices')

    resp_err = MagicMock()
    resp_err.status_code = 200
    resp_err.json.return_value = {'code': 1000, 'message': 'Validation failed'}
    mock_req.return_value = resp_err

    with pytest.raises(ZohoValidationError):
        client.post('invoices', json_data={})

@patch('requests.request')
def test_fetch_invoices_pagination_and_df(mock_req):
    resp_p1 = MagicMock()
    resp_p1.status_code = 200
    resp_p1.json.return_value = {
        'code': 0,
        'page_context': {'page': 1, 'has_more_page': True},
        'invoices': [{'invoice_number': 'INV-1', 'total': 100.0}],
    }

    resp_p2 = MagicMock()
    resp_p2.status_code = 200
    resp_p2.json.return_value = {
        'code': 0,
        'page_context': {'page': 2, 'has_more_page': False},
        'invoices': [{'invoice_number': 'INV-2', 'total': 200.0}],
    }

    mock_req.side_effect = [resp_p1, resp_p2]

    auth = ZohoAuth(client_id='1000.TEST', client_secret='secret123', refresh_token='1000.ref')
    auth._access_token = 'token'
    from datetime import datetime, timedelta, timezone
    auth._token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    client = ZohoClient(auth=auth, org_id='888999')
    df = fetch_invoices(client, as_df=True)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df['invoice_number']) == ['INV-1', 'INV-2']

@patch('requests.request')
def test_push_operations(mock_req):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        'code': 0,
        'invoice': {'invoice_id': '101', 'invoice_number': 'INV-999'},
    }
    mock_req.return_value = mock_resp

    auth = ZohoAuth(client_id='1000.TEST', client_secret='secret123', refresh_token='1000.ref')
    auth._access_token = 'token'
    from datetime import datetime, timedelta, timezone
    auth._token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    client = ZohoClient(auth=auth, org_id='888999')
    res = push_invoices(client, {'customer_name': 'Test Client', 'total': 500.0})
    assert len(res) == 1
    assert res[0]['invoice_id'] == '101'

def test_transformers():
    inv_row = {
        'Customer Name': 'SERVPRO',
        'Invoice Number': 'INV-0099',
        'Invoice Date': '2026-08-14',
        'Due Date': '2026-08-28',
        'Balance': '$1,500.50',
    }
    inv_payload = transform_invoice_row(inv_row)
    assert inv_payload['customer_name'] == 'SERVPRO'
    assert inv_payload['invoice_number'] == 'INV-0099'
    assert inv_payload['line_items'][0]['rate'] == 1500.50

    bill_row = {
        'Vendor Name': 'East Coast Warehousing',
        'Bill Number': 'BILL-100',
        'Bill Date': '2026-08-10',
        'Balance': '2,400.00',
        'Account': 'Inbound Freight',
    }
    bill_payload = transform_bill_row(bill_row)
    assert bill_payload['vendor_name'] == 'East Coast Warehousing'
    assert bill_payload['line_items'][0]['rate'] == 2400.00

    so_row = {
        'Customer Name': 'Amazon',
        'SalesOrder Number': 'SO-101',
        'Amount': '12500',
    }
    so_payload = transform_sales_order_row(so_row)
    assert so_payload['customer_name'] == 'Amazon'
    assert so_payload['line_items'][0]['rate'] == 12500.0

    po_row = {
        'Vendor Name': 'Supplier Inc',
        'PurchaseOrder Number': 'PO-501',
        'Amount': '8900.25',
    }
    po_payload = transform_purchase_order_row(po_row)
    assert po_payload['vendor_name'] == 'Supplier Inc'
    assert po_payload['line_items'][0]['rate'] == 8900.25

    vend_row = {
        'Vendor Name': 'FedEx Express',
        'Email': 'billing@fedex.com',
    }
    vend_payload = transform_vendor_row(vend_row)
    assert vend_payload['contact_name'] == 'FedEx Express'
    assert vend_payload['email'] == 'billing@fedex.com'
