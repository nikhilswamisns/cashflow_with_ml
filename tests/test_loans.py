"""Loans and credit lines: validation, headroom, and the comparison with what the forecast already carries."""
import pytest

from app import loans
from app.output import json_api

ASSUMPTIONS = {"monthly_last_friday_expenses": {"loan_repayments": 13333.0},
               "monthly_third_friday_expenses": {"interest": 250.0},
               "monthly_fourth_friday_expenses": {"interest": 1000.0, "rent": 5000.0},
               "annual_fourth_friday_expenses": [{"amount": 3000.0}]}


def row(**kw):
    return {"name": "Amex line", "type": "credit_line", "limit": 50000, "drawn": 20000, "rate_pct": 12,
            "monthly_repayment": 1500, **kw}


def test_validate_cleans_and_rounds():
    out = loans.validate({"facilities": [row(name="  Amex line  ", limit="50000.005")]})
    f = out["facilities"][0]
    assert f["name"] == "Amex line" and f["limit"] == 50000.0


@pytest.mark.parametrize("bad", [
    {"facilities": [row(name="")]},
    {"facilities": [row(type="mortgage")]},
    {"facilities": [row(limit=-1)]},
    {"facilities": [row(rate_pct=150)]},
    {"facilities": [row(limit="abc")]},
    {"facilities": "no"},
    {},
])
def test_validate_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        loans.validate(bad)


def test_headroom_interest_and_totals():
    cfg = loans.validate({"facilities": [row(), row(name="Over", limit=1000, drawn=1500),
                                         row(name="Term", type="term_loan", limit=0, drawn=60000, rate_pct=6, monthly_repayment=2000)]})
    s = loans.summarize(cfg, ASSUMPTIONS)
    a, over, term = s["facilities"]
    assert a["headroom"] == 30000 and a["monthly_interest"] == 200.0          # 20000 x 12% / 12
    assert over["headroom"] == -500 and over["over_limit"] is True
    assert term["headroom"] is None and term["monthly_interest"] == 300.0     # a term loan has no headroom
    assert (s["credit_lines"], s["limit"], s["drawn"], s["headroom"]) == (2, 51000, 21500, 29500)
    assert s["entered_repayments_per_month"] == 5000 and s["entered_interest_per_month"] == 200 + 15 + 300


def test_in_forecast_reads_the_fixed_monthly_lines_only():
    assert loans.in_forecast(ASSUMPTIONS) == {"repayments_per_month": 13333.0, "interest_per_month": 1250.0}
    assert loans.in_forecast({}) == {"repayments_per_month": 0.0, "interest_per_month": 0.0}


def test_endpoints_save_and_read_back(tmp_path, monkeypatch):
    monkeypatch.setattr(json_api, "CONFIG_DIR", tmp_path)
    (tmp_path / "assumptions.json").write_text('{"monthly_last_friday_expenses": {"loan_repayments": 100}}')
    assert json_api.get_loans()["facilities"] == []                    # nothing entered yet
    saved = json_api.put_loans({"facilities": [row()]})
    assert saved["headroom"] == 30000 and saved["in_forecast"]["repayments_per_month"] == 100
    assert json_api.get_loans()["facilities"][0]["name"] == "Amex line"
    with pytest.raises(Exception) as e:
        json_api.put_loans({"facilities": [row(limit=-5)]})
    assert getattr(e.value, "status_code", None) == 422
    assert json_api.get_loans()["facilities"][0]["limit"] == 50000      # a bad save changes nothing
