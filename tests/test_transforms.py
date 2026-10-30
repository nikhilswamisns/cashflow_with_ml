import pytest
from datetime import date
from decimal import Decimal
from app.models.canonical import DataConfidence
from app.models.matrix import LineItem, WeeklyMatrix
from app.engine.matrix_builder import build_matrix
from app.engine.validation_gate import ValidationGate
from app.transforms.date_bucketing import weekly_fridays

def _make_empty_week_items(fridays: list) -> dict:
    return {f: [] for f in fridays}

def test_recursion_opening_equals_prior_ending():
    start = date(2026, 8, 14)
    items = _make_empty_week_items(weekly_fridays(start, 4))
    matrix = build_matrix(items, Decimal('50000'), start, window_weeks=4)
    for i in range(1, len(matrix.weeks)):
        prev_ending = matrix.weeks[i - 1].ending_cash
        cur_opening = matrix.weeks[i].opening_cash
        assert cur_opening == prev_ending, f'Week {i + 1}: Opening={cur_opening} ≠ prev Ending={prev_ending}'

def test_opening_cash_week1_is_manual_entry():
    start = date(2026, 8, 14)
    amount = Decimal('151783.37')
    items = _make_empty_week_items(weekly_fridays(start, 3))
    matrix = build_matrix(items, amount, start, window_weeks=3)
    assert matrix.weeks[0].opening_cash == amount

def test_empty_matrix_ending_cash_equals_opening():
    start = date(2026, 8, 14)
    amount = Decimal('43986.09')
    items = _make_empty_week_items(weekly_fridays(start, 2))
    matrix = build_matrix(items, amount, start, window_weeks=2)
    for ws in matrix.weeks:
        assert ws.ending_cash == amount

def test_corrected_gross_profit_formula():
    start = date(2026, 8, 14)
    items = _make_empty_week_items(weekly_fridays(start, 2))
    items[start].append(LineItem(amount=Decimal('10000'), confidence=DataConfidence.VERIFIED_LIVE, coa_code='AR', label='A/R Collection'))
    items[start].append(LineItem(amount=Decimal('4000'), confidence=DataConfidence.VERIFIED_LIVE, coa_code='3100', label='COGS'))
    matrix = build_matrix(items, Decimal('0'), start, window_weeks=2)
    week1 = matrix.weeks[0]
    week2 = matrix.weeks[1]
    assert week1.gross_profit == Decimal('10000') - Decimal('4000') - Decimal('0')
    assert week2.gross_profit == Decimal('0')

def test_validation_gate_passes_clean_matrix():
    start = date(2026, 8, 14)
    items = _make_empty_week_items(weekly_fridays(start, 3))
    matrix = build_matrix(items, Decimal('100000'), start, window_weeks=3)
    gate = ValidationGate()
    result = gate.run(matrix)
    recursion_check = next((c for c in result.checks if c.name == 'recursion_integrity'))
    assert recursion_check.passed

def test_validation_gate_catches_broken_recursion():
    start = date(2026, 8, 14)
    items = _make_empty_week_items(weekly_fridays(start, 3))
    matrix = build_matrix(items, Decimal('100000'), start, window_weeks=3)
    matrix.weeks[1].opening_cash = Decimal('999999')
    gate = ValidationGate()
    result = gate.run(matrix)
    recursion_check = next((c for c in result.checks if c.name == 'recursion_integrity'))
    assert not recursion_check.passed
    assert len(recursion_check.details) >= 1

def test_cc_bridge_15th_of_next_month():
    from app.transforms.cc_bridge import cc_expense_cash_out_week
    cycle_end = date(2026, 9, 30)
    forecast_start = date(2026, 8, 14)
    result = cc_expense_cash_out_week(cycle_end, forecast_start)
    assert result == date(2026, 10, 9)

def test_cc_bridge_is_po_direction():
    from app.transforms.cc_bridge import cc_expense_cash_out_week
    from app.transforms.date_bucketing import bucket_ar_to_week_ending_friday, bucket_po_to_week_ending_friday
    cycle_end = date(2026, 9, 30)
    forecast_start = date(2026, 8, 14)
    payment_due = date(2026, 10, 15)
    cc_result = cc_expense_cash_out_week(cycle_end, forecast_start)
    po_result = bucket_po_to_week_ending_friday(payment_due, forecast_start)
    assert cc_result == po_result

def test_bills_gap_open_po_no_bill_verified_live():
    from app.transforms.bills_gap import cogs_amount_and_date

    class FakePO:
        purchaseorder_number = 'PO-001'
        order_status = 'open'
        total = 5000
        delivery_date = date(2026, 8, 1)
        date = date(2026, 7, 1)
        cf_payment_term_formula_unformatted = 30
        reference_number = None
        vendor_name = 'Acme'
    result = cogs_amount_and_date(FakePO(), {}, '3100', 'COGS')
    assert result is not None
    assert result.confidence == DataConfidence.VERIFIED_LIVE

def test_bills_gap_closed_po_no_bill_estimate():
    from app.transforms.bills_gap import cogs_amount_and_date

    class FakePO:
        purchaseorder_number = 'PO-002'
        order_status = 'closed'
        total = 8000
        delivery_date = date(2026, 7, 15)
        date = date(2026, 6, 1)
        cf_payment_term_formula_unformatted = 30
        reference_number = None
        vendor_name = 'Acme'
    result = cogs_amount_and_date(FakePO(), {}, '3100', 'COGS')
    assert result is not None
    assert result.confidence == DataConfidence.ESTIMATE_BILLS_GAP

def test_bills_gap_closed_po_with_bill_verified():
    from app.transforms.bills_gap import cogs_amount_and_date, BillRecord

    class FakePO:
        purchaseorder_number = 'PO-003'
        order_status = 'closed'
        total = 8000
        delivery_date = date(2026, 7, 15)
        date = date(2026, 6, 1)
        cf_payment_term_formula_unformatted = 30
        reference_number = None
        vendor_name = 'Acme'
    bills = {'PO-003': BillRecord(linked_po='PO-003', balance_due=Decimal('6500'), due_date=date(2026, 8, 10), status='partially_paid')}
    result = cogs_amount_and_date(FakePO(), bills, '3100', 'COGS')
    assert result is not None
    assert result.confidence == DataConfidence.VERIFIED_LIVE
    assert result.amount == Decimal('6500')

def test_cancelled_po_returns_none():
    from app.transforms.bills_gap import cogs_amount_and_date

    class FakePO:
        purchaseorder_number = 'PO-004'
        order_status = 'cancelled'
        total = 1000
        delivery_date = None
        date = date(2026, 7, 1)
        cf_payment_term_formula_unformatted = 30
        reference_number = None
        vendor_name = 'Acme'
    result = cogs_amount_and_date(FakePO(), {}, '3100', 'COGS')
    assert result is None
