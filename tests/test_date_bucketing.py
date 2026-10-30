import pytest
from datetime import date, timedelta
from app.transforms.date_bucketing import bucket_ar_to_week_ending_friday, bucket_po_to_week_ending_friday, next_friday, prev_friday

def test_ar_and_po_functions_are_mirror_images():
    base_friday = date(2026, 8, 14)
    ar_result = bucket_ar_to_week_ending_friday(base_friday, base_friday)
    po_result = bucket_po_to_week_ending_friday(base_friday, base_friday)
    assert ar_result == base_friday, 'AR: Friday due_date should return the same Friday'
    assert po_result == base_friday, 'PO: Friday due_date should return the same Friday'
    for offset in range(1, 7):
        non_friday = base_friday + timedelta(days=offset)
        ar_week = bucket_ar_to_week_ending_friday(non_friday, date(2020, 1, 3))
        po_week = bucket_po_to_week_ending_friday(non_friday, date(2020, 1, 3))
        assert ar_week >= non_friday, f'AR (cash IN) bucketed BEFORE due_date for offset={offset}: due={non_friday}, ar_week={ar_week}'
        assert po_week <= non_friday, f'PO (cash OUT) bucketed AFTER due_date for offset={offset}: due={non_friday}, po_week={po_week}'
        assert ar_week.weekday() == 4, f'AR result is not a Friday: {ar_week}'
        assert po_week.weekday() == 4, f'PO result is not a Friday: {po_week}'
        assert ar_week != po_week, f'AR and PO should differ for non-Friday due_dates (offset={offset}): due={non_friday}, ar={ar_week}, po={po_week}'

def test_po_00280_delivery_date_known():
    from app.transforms.cogs_routing import po_due_date
    from datetime import date

    class FakePO:
        delivery_date = date(2026, 6, 30)
        date = None
        cf_payment_term_formula_unformatted = 30
    due = po_due_date(FakePO())
    assert due == date(2026, 7, 30), f'Expected 2026-07-30, got {due}'
    forecast_start = date(2026, 8, 14)
    week = bucket_po_to_week_ending_friday(due, forecast_start)
    assert week == date(2026, 8, 14), f'PO-00280: expected clamp to 2026-08-14 (forecast start), got {week}'

def test_po_00294_undated_po_fallback():
    from app.transforms.cogs_routing import po_due_date
    from datetime import date

    class FakePO:
        delivery_date = None
        date = date(2026, 7, 27)
        cf_payment_term_formula_unformatted = 30
    due = po_due_date(FakePO())
    assert due == date(2026, 8, 26), f'Expected 2026-08-26, got {due}'
    forecast_start = date(2026, 8, 14)
    week = bucket_po_to_week_ending_friday(due, forecast_start)
    assert week == date(2026, 8, 21), f'PO-00294: expected 2026-08-21 (Friday on or before 08-26 which is Wed), got {week}'

def test_ar_overdue_clamps_to_week_1():
    forecast_start = date(2026, 8, 14)
    overdue_date = date(2026, 7, 1)
    result = bucket_ar_to_week_ending_friday(overdue_date, forecast_start)
    assert result == forecast_start, f'Overdue AR should clamp to forecast_start={forecast_start}, got {result}'

def test_po_overdue_clamps_to_week_1():
    forecast_start = date(2026, 8, 14)
    overdue_date = date(2026, 7, 15)
    result = bucket_po_to_week_ending_friday(overdue_date, forecast_start)
    assert result == forecast_start, f'Overdue PO should clamp to forecast_start={forecast_start}, got {result}'

@pytest.mark.parametrize('weekday_name,due_date,ar_expected,po_expected', [('Friday', date(2026, 8, 14), date(2026, 8, 14), date(2026, 8, 14)), ('Saturday', date(2026, 8, 15), date(2026, 8, 21), date(2026, 8, 14)), ('Sunday', date(2026, 8, 16), date(2026, 8, 21), date(2026, 8, 14)), ('Monday', date(2026, 8, 17), date(2026, 8, 21), date(2026, 8, 14)), ('Tuesday', date(2026, 8, 18), date(2026, 8, 21), date(2026, 8, 14)), ('Wednesday', date(2026, 8, 19), date(2026, 8, 21), date(2026, 8, 14)), ('Thursday', date(2026, 8, 20), date(2026, 8, 21), date(2026, 8, 14))])
def test_all_weekdays(weekday_name, due_date, ar_expected, po_expected):
    forecast_start = date(2026, 8, 14)
    ar_result = bucket_ar_to_week_ending_friday(due_date, forecast_start)
    po_result = bucket_po_to_week_ending_friday(due_date, forecast_start)
    assert ar_result == ar_expected, f'AR ({weekday_name}): expected {ar_expected}, got {ar_result}'
    assert po_result == po_expected, f'PO ({weekday_name}): expected {po_expected}, got {po_result}'
