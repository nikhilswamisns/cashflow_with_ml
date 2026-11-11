from app.outflow_buckets import BUCKETS, OTHER, outflow_buckets


def test_buckets_sum_to_total_with_remainder_in_other():
    week = {"cogs_standard": {"amount": 100.0}, "ops_ea_salaries": 20.0, "mkt_amazon_ads": {"amount": 5.0}, "fin_rent": 10.0}
    b = outflow_buckets(week, 140.0)
    assert b["Inventory"] == 100.0 and b["Payroll"] == 20.0 and b["Marketing & ads"] == 5.0
    assert b[OTHER] == 15.0  # rent is not mapped, so it falls into Other
    assert round(sum(b.values()), 2) == 140.0


def test_no_field_in_two_buckets():
    fields = [f for fs in BUCKETS.values() for f in fs]
    assert len(fields) == len(set(fields))
