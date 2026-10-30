from __future__ import annotations
import logging
from typing import Any, Optional, Union
import pandas as pd
from zoho.client import ZohoClient

logger = logging.getLogger('zoho.fetch')

def _fetch_all_pages(
    client: ZohoClient,
    endpoint: str,
    list_key: str,
    params: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    all_records: list[dict[str, Any]] = []
    page = 1
    req_params = dict(params or {})
    req_params['per_page'] = req_params.get('per_page', 200)

    while True:
        req_params['page'] = page
        response = client.get(endpoint, params=req_params)
        records = response.get(list_key, [])
        all_records.extend(records)

        page_context = response.get('page_context', {})
        has_more = page_context.get('has_more_page', False)
        if not has_more or len(records) == 0:
            break
        page += 1

    logger.info('Fetched %d records from %s across %d page(s)', len(all_records), endpoint, page)
    return all_records

def _format_result(records: list[dict[str, Any]], as_df: bool) -> Union[list[dict[str, Any]], pd.DataFrame]:
    if as_df:
        return pd.DataFrame(records)
    return records

def fetch_invoices(
    client: ZohoClient,
    as_df: bool = False,
    params: Optional[dict[str, Any]] = None,
) -> Union[list[dict[str, Any]], pd.DataFrame]:
    records = _fetch_all_pages(client, 'invoices', 'invoices', params=params)
    return _format_result(records, as_df)

def fetch_bills(
    client: ZohoClient,
    as_df: bool = False,
    params: Optional[dict[str, Any]] = None,
) -> Union[list[dict[str, Any]], pd.DataFrame]:
    records = _fetch_all_pages(client, 'bills', 'bills', params=params)
    return _format_result(records, as_df)

def fetch_sales_orders(
    client: ZohoClient,
    as_df: bool = False,
    params: Optional[dict[str, Any]] = None,
) -> Union[list[dict[str, Any]], pd.DataFrame]:
    records = _fetch_all_pages(client, 'salesorders', 'salesorders', params=params)
    return _format_result(records, as_df)

def fetch_purchase_orders(
    client: ZohoClient,
    as_df: bool = False,
    params: Optional[dict[str, Any]] = None,
) -> Union[list[dict[str, Any]], pd.DataFrame]:
    records = _fetch_all_pages(client, 'purchaseorders', 'purchaseorders', params=params)
    return _format_result(records, as_df)

def fetch_contacts(
    client: ZohoClient,
    as_df: bool = False,
    params: Optional[dict[str, Any]] = None,
) -> Union[list[dict[str, Any]], pd.DataFrame]:
    records = _fetch_all_pages(client, 'contacts', 'contacts', params=params)
    return _format_result(records, as_df)

def fetch_items(
    client: ZohoClient,
    as_df: bool = False,
    params: Optional[dict[str, Any]] = None,
) -> Union[list[dict[str, Any]], pd.DataFrame]:
    records = _fetch_all_pages(client, 'items', 'items', params=params)
    return _format_result(records, as_df)

def fetch_chart_of_accounts(
    client: ZohoClient,
    as_df: bool = False,
    params: Optional[dict[str, Any]] = None,
) -> Union[list[dict[str, Any]], pd.DataFrame]:
    records = _fetch_all_pages(client, 'chartofaccounts', 'chartofaccounts', params=params)
    return _format_result(records, as_df)

def fetch_organizations(client: ZohoClient) -> list[dict[str, Any]]:
    return client.get_organizations()
