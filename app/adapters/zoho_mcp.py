from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Optional
from app.models.canonical import CanonicalRecord, DataConfidence
from app.models.preflight import CadenceTier
from zoho.client import ZohoClient
from zoho.fetch import (
    fetch_bills,
    fetch_invoices,
    fetch_purchase_orders,
    fetch_sales_orders,
)

class ZohoMCPAdapter:

    def __init__(self, source_name: str, cadence_tier: CadenceTier, client: Optional[ZohoClient] = None):
        self.source_name = source_name
        self.cadence_tier = cadence_tier
        self.client = client or ZohoClient()
        self._last_fetched: Optional[datetime] = None

    def fetch(self, as_of: date) -> list[CanonicalRecord]:
        now = datetime.now(timezone.utc)
        records: list[CanonicalRecord] = []

        if self.source_name == 'ar_unpaid_invoices':
            inv_list = fetch_invoices(self.client, params={'status': 'unpaid'})
            for inv in inv_list:
                records.append(
                    CanonicalRecord(
                        source='ar_unpaid_invoices',
                        record_type='invoice',
                        ingested_at=now,
                        as_of_date=as_of,
                        confidence=DataConfidence.VERIFIED_LIVE,
                        payload={
                            'invoice_number': inv.get('invoice_number'),
                            'customer_name': inv.get('customer_name'),
                            'status': str(inv.get('status', '')).lower().replace(' ', '_'),
                            'due_date': inv.get('due_date'),
                            'balance': str(inv.get('balance', inv.get('total', '0'))),
                            'reference_number': inv.get('reference_number'),
                        },
                        raw_ref=f"Zoho Books Invoice ID {inv.get('invoice_id', 'N/A')}",
                    )
                )

        elif self.source_name == 'confirmed_sales_orders':
            so_list = fetch_sales_orders(self.client, params={'status': 'confirmed'})
            for so in so_list:
                records.append(
                    CanonicalRecord(
                        source='confirmed_sales_orders',
                        record_type='sales_order',
                        ingested_at=now,
                        as_of_date=as_of,
                        confidence=DataConfidence.VERIFIED_LIVE,
                        payload={
                            'sales_order_number': so.get('salesorder_number'),
                            'customer_name': so.get('customer_name'),
                            'status': str(so.get('status', '')).lower().replace(' ', '_'),
                            'expected_shipment_date': so.get('shipment_date') or so.get('expected_shipment_date'),
                            'total': str(so.get('total', '0')),
                        },
                        raw_ref=f"Zoho Books SalesOrder ID {so.get('salesorder_id', 'N/A')}",
                    )
                )

        elif self.source_name == 'open_purchase_orders':
            po_list = fetch_purchase_orders(self.client, params={'status': 'open'})
            for po in po_list:
                records.append(
                    CanonicalRecord(
                        source='open_purchase_orders',
                        record_type='purchase_order',
                        ingested_at=now,
                        as_of_date=as_of,
                        confidence=DataConfidence.VERIFIED_LIVE,
                        payload={
                            'po_number': po.get('purchaseorder_number'),
                            'vendor_name': po.get('vendor_name'),
                            'status': str(po.get('status', '')).lower().replace(' ', '_'),
                            'delivery_date': po.get('delivery_date'),
                            'delivery_terms': po.get('delivery_terms', ''),
                            'total': str(po.get('total', '0')),
                            'balance': str(po.get('balance', po.get('total', '0'))),
                        },
                        raw_ref=f"Zoho Books PurchaseOrder ID {po.get('purchaseorder_id', 'N/A')}",
                    )
                )

        elif self.source_name == 'ap_unpaid_bills':
            bill_list = fetch_bills(self.client, params={'status': 'unpaid'})
            for b in bill_list:
                records.append(
                    CanonicalRecord(
                        source='ap_unpaid_bills',
                        record_type='bill',
                        ingested_at=now,
                        as_of_date=as_of,
                        confidence=DataConfidence.VERIFIED_LIVE,
                        payload={
                            'bill_number': b.get('bill_number'),
                            'vendor_name': b.get('vendor_name'),
                            'status': str(b.get('status', '')).lower().replace(' ', '_'),
                            'due_date': b.get('due_date'),
                            'balance': str(b.get('balance', b.get('total', '0'))),
                            'account': b.get('account_name') or 'Cost of Goods Sold',
                        },
                        raw_ref=f"Zoho Books Bill ID {b.get('bill_id', 'N/A')}",
                    )
                )

        self._last_fetched = now
        return records

    def last_updated(self) -> datetime | None:
        return self._last_fetched

    def is_stale(self, as_of: date) -> bool:
        if self._last_fetched is None:
            return True
        delta = (datetime.now(timezone.utc).date() - self._last_fetched.date()).days
        return delta > self.cadence_tier.staleness_threshold_days
