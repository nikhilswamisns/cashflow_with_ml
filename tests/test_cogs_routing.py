import pytest
from datetime import date
from app.transforms.cogs_routing import cogs_category, po_due_date

class FakePO:

    def __init__(self, vendor_name='', reference_number=None, order_status='open', delivery_date=None, date_=None, total=1000, terms=None):
        self.vendor_name = vendor_name
        self.reference_number = reference_number
        self.order_status = order_status
        self.delivery_date = delivery_date
        self.date = date_
        self.total = total
        self.cf_payment_term_formula_unformatted = terms

def test_cogs_ch_robinson_routes_to_freight():
    po = FakePO(vendor_name='C.H. Robinson International, Inc.')
    assert cogs_category(po) == '3101_inbound_freight'

def test_cogs_us_customs_routes_to_duty():
    po = FakePO(vendor_name='US Customs and Border Protection')
    assert cogs_category(po) == '3102_inbound_duty'

def test_cogs_efe_reference_routes_to_freight():
    po = FakePO(vendor_name='Some Other Vendor', reference_number='EFE-2026-001')
    assert cogs_category(po) == '3101_inbound_freight'

def test_cogs_standard_vendor_routes_to_standard():
    po = FakePO(vendor_name='Acme Supplies Inc')
    assert cogs_category(po) == '3100_cogs_standard'

def test_cogs_empty_vendor_routes_to_standard():
    po = FakePO(vendor_name='')
    assert cogs_category(po) == '3100_cogs_standard'

def test_po_due_date_with_delivery_date():
    po = FakePO(delivery_date=date(2026, 6, 30), terms=30)
    assert po_due_date(po) == date(2026, 7, 30)

def test_po_due_date_without_delivery_date():
    po = FakePO(date_=date(2026, 7, 27), terms=30)
    assert po_due_date(po) == date(2026, 8, 26)

def test_po_due_date_default_terms():
    po = FakePO(delivery_date=date(2026, 8, 1), terms=None)
    result = po_due_date(po)
    assert result == date(2026, 8, 31)

def test_po_due_date_delivery_supersedes_po_date():
    po = FakePO(delivery_date=date(2026, 6, 30), date_=date(2026, 5, 1), terms=30)
    assert po_due_date(po) == date(2026, 7, 30)

def test_po_due_date_no_date_raises():
    po = FakePO(delivery_date=None, date_=None)
    with pytest.raises(ValueError, match='neither delivery_date nor date'):
        po_due_date(po)

def test_full_po_00280_regression():
    from app.transforms.date_bucketing import bucket_po_to_week_ending_friday
    po = FakePO(delivery_date=date(2026, 6, 30), terms=30)
    due = po_due_date(po)
    assert due == date(2026, 7, 30)
    week = bucket_po_to_week_ending_friday(due, date(2026, 8, 14))
    assert week == date(2026, 8, 14)

def test_full_po_00294_regression():
    from app.transforms.date_bucketing import bucket_po_to_week_ending_friday
    po = FakePO(date_=date(2026, 7, 27), terms=30)
    due = po_due_date(po)
    assert due == date(2026, 8, 26)
    week = bucket_po_to_week_ending_friday(due, date(2026, 8, 14))
    assert week == date(2026, 8, 21)
