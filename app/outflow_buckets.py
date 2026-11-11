"""Groups the forecast's outflow lines into a few buckets for the "Where cash goes" chart.

Edit BUCKETS to move a line from one bucket to another. Anything not listed (and the credit card timing difference)
lands in "Other", so the buckets always add up to the week's total outflow used by the dashboard.
"""

# bucket name -> forecast week fields that belong to it (field names as in the stored run's weeks)
BUCKETS: dict[str, list[str]] = {
    "Inventory": ["cogs_standard"],
    "Freight & duty": ["inbound_freight", "inbound_duty"],
    "Payroll": ["ops_ea_salaries", "mkt_salaries", "sell_salaries", "fin_admin_salaries", "sell_gusto_tax",
                "sell_medicare", "sell_commission", "nonop_health_ins"],
    "Marketing & ads": ["mkt_web_redesign", "mkt_promo_items", "mkt_printing", "mkt_misc", "mkt_graphics",
                        "mkt_amazon_ads_admin", "mkt_seo", "mkt_facebook", "mkt_amazon_ads", "sell_tradeshow"],
    "Fulfilment & Amazon": ["ops_3pl", "ops_amazon_fba", "ops_amazon_monthly", "ops_disposal", "ops_outbound_freight",
                            "ops_seller_fees", "ops_storage"],
    "Loans & interest": ["loan_repayments", "fin_interest"],
}
OTHER = "Other"


def _amount(week: dict, field: str) -> float:
    v = week.get(field)
    if isinstance(v, dict):
        return float(v.get("amount") or 0.0)
    return float(v) if isinstance(v, (int, float)) else 0.0


def outflow_buckets(week: dict, total_outflow: float) -> dict[str, float]:
    """Amount per bucket for one week; Other is whatever is left of total_outflow, so the buckets sum to it."""
    out = {name: round(sum(_amount(week, f) for f in fields), 2) for name, fields in BUCKETS.items()}
    out[OTHER] = round(total_outflow - sum(out.values()), 2)
    return out
