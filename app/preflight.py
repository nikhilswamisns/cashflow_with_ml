from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Any
from app.config.loader import load_assumptions
from app.models.preflight import CadenceTier, InputRequirement, PreflightResult

def _build_source_inventory() -> list[InputRequirement]:
    cfg = load_assumptions()
    thresholds = cfg.staleness_thresholds_days
    return [InputRequirement(source_name='opening_cash', cadence_tier=CadenceTier.MANUAL, blocking=True, last_provided_at=None, staleness_threshold_days=thresholds.get('opening_cash', 1), description='Opening Cash Position — sum of CHK + PayPal + Petty Cash', feeds=['Opening Cash Position (week 1)']), InputRequirement(source_name='ar_unpaid_invoices', cadence_tier=CadenceTier.LIVE, blocking=True, last_provided_at=None, staleness_threshold_days=thresholds.get('ar_unpaid_invoices', 7), description='A/R Unpaid Invoices export', feeds=['A/R Collection (row 13)', 'SERVPRO Corporate Net-45 (row 8)']), InputRequirement(source_name='confirmed_sales_orders', cadence_tier=CadenceTier.PERIODIC, blocking=False, last_provided_at=None, staleness_threshold_days=thresholds.get('confirmed_sales_orders', 7), description='Confirmed Sales Orders export', feeds=['SERVPRO Corporate Net-45 (row 8) — SO-based estimate']), InputRequirement(source_name='purchase_orders', cadence_tier=CadenceTier.LIVE, blocking=True, last_provided_at=None, staleness_threshold_days=thresholds.get('purchase_orders', 7), description='Purchase Orders export', feeds=['COGS (row 17)', 'Inbound Freight (row 18)', 'Inbound Duty (row 19)']), InputRequirement(source_name='partially_paid_bills', cadence_tier=CadenceTier.LIVE, blocking=False, last_provided_at=None, staleness_threshold_days=thresholds.get('partially_paid_bills', 7), description='Partially Paid Bills export — optional, closes the Bills Gap (Section 4.6)', feeds=['COGS rows — true balance and due date for closed POs']), InputRequirement(source_name='sales_by_item_6mo', cadence_tier=CadenceTier.PERIODIC, blocking=False, last_provided_at=None, staleness_threshold_days=thresholds.get('sales_by_item_6mo', 35), description='Sales by Item (6-month) export', feeds=['Other Resellers weekly run-rate (row 9)']), InputRequirement(source_name='amazon_sales_6mo', cadence_tier=CadenceTier.PERIODIC, blocking=False, last_provided_at=None, staleness_threshold_days=thresholds.get('amazon_sales_6mo', 35), description='Amazon Sales (6-month) export', feeds=['Amazon FBA Fees (row 24)', 'Amazon Seller Fees (row 30)', 'Amazon Advertising (row 39)']), InputRequirement(source_name='profit_and_loss', cadence_tier=CadenceTier.PERIODIC, blocking=False, last_provided_at=None, staleness_threshold_days=thresholds.get('profit_and_loss', 35), description='Profit & Loss export (trailing 12 months, by account code)', feeds=['All Avg last 6/12 mo expense lines in every section']), InputRequirement(source_name='credit_card_statement', cadence_tier=CadenceTier.PERIODIC, blocking=False, last_provided_at=None, staleness_threshold_days=thresholds.get('credit_card_statement', 35), description='Credit Card Statement (current closed cycle)', feeds=['CC-driven expense rows — 15th-of-month payment timing'])]

def run_preflight(upload_timestamps: dict[str, datetime], as_of: date, is_first_run: bool=True) -> PreflightResult:
    inventory = _build_source_inventory()
    now = datetime.now(timezone.utc)
    missing_blocking: list[InputRequirement] = []
    missing_optional: list[InputRequirement] = []
    stale: list[InputRequirement] = []
    for req in inventory:
        if req.source_name == 'opening_cash' and (not is_first_run):
            continue
        last_ts = upload_timestamps.get(req.source_name)
        req.last_provided_at = last_ts
        if last_ts is None:
            if req.blocking and (req.source_name != 'opening_cash' or is_first_run):
                missing_blocking.append(req)
            else:
                missing_optional.append(req)
        else:
            delta_days = (now - last_ts).days
            if delta_days > req.staleness_threshold_days:
                stale.append(req)
    return PreflightResult(missing_blocking=missing_blocking, missing_optional=missing_optional, stale=stale)
