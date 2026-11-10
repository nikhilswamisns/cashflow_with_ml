"""Loans and credit lines, entered by hand (Zoho does not hold the terms). Display only: nothing here changes the cash forecast.

The forecast already carries loan payments as fixed monthly lines in app/config/assumptions.json (loan repayments on the
last Friday, interest on the 3rd and 4th Fridays), so `summarize` shows those next to the entered facilities. That makes a
double count visible instead of adding to it.
"""
import math

TYPES = ("credit_line", "term_loan")
MAX_FACILITIES = 50


def _num(v, field: str, lo: float = 0.0, hi: float = 1e12) -> float:
    try:
        x = float(v if v not in (None, "") else 0)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number")
    if not math.isfinite(x) or x < lo or x > hi:
        raise ValueError(f"{field} must be between {lo:g} and {hi:g}")
    return round(x, 2)


def validate(body) -> dict:
    """Clean what the page sends. Raises ValueError with a plain message."""
    rows = body.get("facilities") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise ValueError("facilities must be a list")
    if len(rows) > MAX_FACILITIES:
        raise ValueError(f"at most {MAX_FACILITIES} loans or credit lines")
    out = []
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            raise ValueError(f"row {i} is not a loan")
        name = str(r.get("name") or "").strip()
        if not name or len(name) > 80:
            raise ValueError(f"row {i}: give it a name (up to 80 characters)")
        kind = r.get("type")
        if kind not in TYPES:
            raise ValueError(f"row {i}: type must be credit_line or term_loan")
        out.append({"name": name, "type": kind,
                    "limit": _num(r.get("limit"), f"row {i}: limit"),
                    "drawn": _num(r.get("drawn"), f"row {i}: drawn"),
                    "rate_pct": _num(r.get("rate_pct"), f"row {i}: rate", hi=100),
                    "monthly_repayment": _num(r.get("monthly_repayment"), f"row {i}: monthly repayment")})
    return {"facilities": out}


def in_forecast(assumptions: dict) -> dict:
    """Monthly loan repayments and interest the cash forecast already carries (fixed lines in assumptions.json)."""
    rep = intr = 0.0
    for key, group in assumptions.items():
        if key.startswith("monthly_") and key.endswith("_expenses") and isinstance(group, dict):
            rep += float(group.get("loan_repayments") or 0)
            intr += float(group.get("interest") or 0)
    return {"repayments_per_month": round(rep, 2), "interest_per_month": round(intr, 2)}


def summarize(cfg: dict, assumptions: dict) -> dict:
    rows = []
    for f in cfg.get("facilities", []):
        credit = f["type"] == "credit_line"
        rows.append({**f, "headroom": round(f["limit"] - f["drawn"], 2) if credit else None,
                     "over_limit": credit and f["drawn"] > f["limit"],
                     "monthly_interest": round(f["drawn"] * f["rate_pct"] / 100 / 12, 2)})
    lines = [r for r in rows if r["type"] == "credit_line"]
    return {"facilities": rows,
            "credit_lines": len(lines),
            "limit": round(sum(r["limit"] for r in lines), 2),
            "drawn": round(sum(r["drawn"] for r in lines), 2),
            "headroom": round(sum(r["headroom"] for r in lines), 2),
            "entered_repayments_per_month": round(sum(r["monthly_repayment"] for r in rows), 2),
            "entered_interest_per_month": round(sum(r["monthly_interest"] for r in rows), 2),
            "in_forecast": in_forecast(assumptions),
            "note": "Display only. The cash forecast already carries its own fixed loan repayment and interest lines."}
