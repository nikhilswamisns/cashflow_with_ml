"""Glue between the v10 engine and the existing API / dashboard / database."""
from __future__ import annotations

import json
from datetime import date
from typing import Optional

from app import db
from app.engine.v10_engine import Forecast, build_forecast, revenue_row

# Cash Flow Model row -> dashboard/matrix field name (same names the UI already uses)
# 1 Oct 2026 layout: row 10 = 1100.3 Amazon; every row from Adjustments down is one below its Version 10 number.
_V10_FIELD = {11: "adjustments", 12: "discount_given", 13: "freight_billed",
              14: "ar_collection", 18: "cogs_standard", 19: "inbound_freight", 20: "inbound_duty", 24: "ops_3pl",
              25: "ops_amazon_fba", 26: "ops_amazon_monthly", 27: "ops_disposal", 28: "ops_misc", 29: "ops_ea_salaries",
              30: "ops_outbound_freight", 31: "ops_seller_fees", 32: "ops_storage", 38: "mkt_web_redesign",
              39: "mkt_promo_items", 40: "mkt_printing", 41: "mkt_misc", 42: "mkt_salaries", 43: "mkt_graphics",
              44: "mkt_amazon_ads_admin", 45: "mkt_seo", 46: "mkt_facebook", 47: "mkt_amazon_ads", 51: "sell_vehicle",
              52: "sell_fuel", 53: "sell_travel", 54: "sell_tradeshow", 55: "sell_salaries", 56: "sell_reimbursements",
              57: "sell_medicare", 58: "sell_gusto_tax", 59: "sell_meals", 60: "sell_commission", 64: "fin_training",
              65: "fin_office_tools", 66: "fin_rent", 67: "fin_legal", 68: "fin_interest", 69: "fin_insurance",
              70: "fin_admin_salaries", 71: "fin_accounting", 72: "fin_bank_fees", 76: "it_zoom", 77: "it_zoho",
              78: "it_shopify", 79: "it_microsoft", 80: "it_godaddy", 81: "it_phone", 82: "it_development",
              83: "it_computer", 87: "nonop_health_ins", 88: "nonop_irs_tax", 89: "nonop_nj_tax", 90: "nonop_owner_draws",
              94: "cc_payment_due", 95: "loan_repayments", 96: "cc_charges_deferred"}
ROW_FIELD = {8: "servpro_corporate", 9: "other_resellers", 10: "amazon", **_V10_FIELD}
TOTAL_FIELD = {4: "opening_cash", 15: "total_revenue", 21: "total_cogs", 33: "total_operations", 35: "gross_profit",
               48: "total_marketing", 61: "total_selling", 73: "total_finance_admin", 84: "total_it",
               91: "total_non_operating", 98: "ending_cash"}
REVENUE_DETAIL_ROWS = {8: ("SERVPRO", "1100.1"), 10: ("Amazon", "1100.3"), 14: ("A/R", "AR")}
COGS_DETAIL_ROWS = {18: "3100", 19: "3101", 20: "3102"}

SNAPSHOT_SOURCE = "zoho_snapshot"

_LAYOUT_CACHE: Optional[list] = None


def cfm_layout() -> list:
    """Row layout of the Cash Flow Model sheet (rows 4-98), read from the template: code, account, row kind."""
    global _LAYOUT_CACHE
    if _LAYOUT_CACHE is None:
        import openpyxl
        from app.engine.v10_engine import TEMPLATE
        ws = openpyxl.load_workbook(TEMPLATE)["Cash Flow Model"]
        out = []
        import json as _json
        from pathlib import Path as _Path
        try:
            hidden = set(_json.loads((_Path(__file__).resolve().parents[1] / "config" / "forecast_rules.json")
                                     .read_text(encoding="utf-8")).get("hidden_cfm_rows", []))
        except Exception:
            hidden = set()
        for r in range(4, 99):
            if r in hidden:
                continue
            a, b = ws.cell(r, 1).value, ws.cell(r, 2).value
            if a is None and b is None:
                continue
            label = str(b if b is not None else a).strip()
            code = str(a).strip() if (a is not None and b is not None) else ""
            fill = ws.cell(r, 2).fill
            rgb = str(fill.fgColor.rgb or "")[-6:].upper() if fill.fill_type == "solid" and fill.fgColor.type == "rgb" else ""
            if r == 4:
                kind = "opening"
            elif r == 98:
                kind = "ending"
            elif r == 35:
                kind = "gross"
            elif rgb in ("1B3A5C", "0D1B2A"):
                kind = "section"
            elif rgb == "2E6DA4":
                kind = "group"
            elif label.lower().startswith("total"):
                kind = "total"
            else:
                kind = "line"
            out.append({"row": r, "code": code, "label": label, "kind": kind,
                        "field": ROW_FIELD.get(r) or TOTAL_FIELD.get(r)})
        _LAYOUT_CACHE = out
    return _LAYOUT_CACHE


def forecast_to_matrix_dict(f: Forecast) -> dict:
    weeks = []
    for i, wk in enumerate(f.fridays):
        w: dict = {"week_ending_friday": wk.isoformat()}
        for row, name in ROW_FIELD.items():
            items = []
            if row in REVENUE_DETAIL_ROWS:
                _, code = REVENUE_DETAIL_ROWS[row]
                items = [{"amount": x.amount, "label": x.source, "raw_ref": f"{x.source} {x.ref} ({x.party})",
                          "coa_code": code, "confidence": "verified_live"}
                         for x in f.revenue if x.week == wk and revenue_row(x.source) == row]
            if row in COGS_DETAIL_ROWS:
                cat = COGS_DETAIL_ROWS[row]
                items = [{"amount": x.amount, "label": x.category, "raw_ref": f"{x.source} {x.ref} ({x.party})",
                          "coa_code": cat, "confidence": "verified_live"}
                         for x in f.cogs if x.week == wk and cat in x.category]
            w[name] = {"amount": round(f.values[row][i], 2), "confidence": None, "line_items": items}
        for row, name in TOTAL_FIELD.items():
            w[name] = round(f.values[row][i], 2)
        weeks.append(w)
    return {"forecast_start_friday": f.run_date.isoformat(), "window_weeks": len(f.fridays), "weeks": weeks,
            "engine": "v10", "kpis": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in f.kpis.items()
                                      if k != "negative_weeks"},
            "negative_weeks": [x.isoformat() for x in f.kpis["negative_weeks"]],
            "open_items": f.v10_open_items + f.fixed_items + f.open_items, "restatements": [list(r) for r in f.restatements],
            "layout": [dict(x, values=([] if x["kind"] in ("section", "group") else [round(v, 2) for v in f.values[x["row"]]]))
                       for x in cfm_layout()]}


def get_run_snapshot(run_id: str) -> Optional[dict]:
    for u in db.get_uploads_for_run(run_id):
        if u["source_name"] == SNAPSHOT_SOURCE and u["records_json"]:
            return json.loads(u["records_json"])[0]
    return None


def get_prior_snapshot(run_id: str) -> Optional[dict]:
    """Snapshot of the prior FORECAST: the most recent other run, created before this one, whose week 1 is earlier
    than this run's week 1. A re-fetch for the same week 1 is not a prior forecast (it would show nothing paid)."""
    run = db.get_run(run_id)
    mine = get_run_snapshot(run_id) or {}
    week1 = str(mine.get("run_date") or "")
    for r in db.list_runs():
        if r["run_id"] != run_id and r["created_at"] < run["created_at"]:
            snap = get_run_snapshot(r["run_id"])
            if snap and (not week1 or str(snap.get("run_date") or "") < week1):
                return snap
    return None


def forecast_for_run(run_id: str) -> Optional[Forecast]:
    snap = get_run_snapshot(run_id)
    if snap is None:
        return None
    run = db.get_run(run_id)
    snap = dict(snap)
    override = run.get("opening_cash_amount")
    if override not in (None, "", "0") and run.get("opening_cash_date"):
        # A manual opening-cash override was posted for this run: show it as the manual adjustment line
        # (Zoho cash stays visible in General Info B42, the difference goes to B43).
        snap["_opening_override"] = {"amount": float(override), "as_of": run["opening_cash_date"]}
    f = build_forecast(snap, prior_snapshot=get_prior_snapshot(run_id))
    ov = snap.get("_opening_override")
    if ov and abs(ov["amount"] - f.opening_cash) > 0.005:
        from app.engine.v10_engine import V10Engine
        rules = json.loads(json.dumps(f.rules))
        rules["opening_cash"]["manual_adjustments"] = [{
            "label": "Bank balance entered - difference vs Zoho cash",
            "amount": round(ov["amount"] - f.zoho_cash, 2), "entered_by": "UI (Opening Cash)", "as_of": ov["as_of"],
            "note": f"Opening cash set to {ov['amount']:,.2f}; Zoho cash {f.zoho_cash:,.2f}; difference shown here."}]
        f = V10Engine(snap, rules=rules, prior_snapshot=get_prior_snapshot(run_id)).run()
    return f


# ------------------------------------------------------------------ refresh pull ("Changes Since Run")
REFRESH_SOURCE = "zoho_refresh"


def get_run_refresh(run_id: str) -> Optional[tuple[dict, str]]:
    """Latest refresh snapshot saved with the run, and when it was saved (UTC ISO)."""
    for u in db.get_uploads_for_run(run_id):   # newest first
        if u["source_name"] == REFRESH_SOURCE and u["records_json"]:
            return json.loads(u["records_json"])[0], u["uploaded_at"]
    return None


def refresh_forecast_for_run(run_id: str, base: Optional[Forecast] = None) -> Optional[Forecast]:
    """Forecast built from the run's latest refresh pull: same week 1, same rules, same manual adjustments.

    An opening-cash override (bank balance entered for the run) is carried as the same adjustment amount, so a
    change in Zoho cash between the two pulls still shows."""
    got = get_run_refresh(run_id)
    if got is None:
        return None
    snap = dict(got[0])
    base = base or forecast_for_run(run_id)
    if base is not None:
        snap["run_date"] = base.run_date.isoformat()
    f = build_forecast(snap, prior_snapshot=get_prior_snapshot(run_id))
    if base is not None and abs(base.opening_cash - base.zoho_cash - (f.opening_cash - f.zoho_cash)) > 0.005:
        from app.engine.v10_engine import V10Engine
        rules = json.loads(json.dumps(f.rules))
        rules["opening_cash"]["manual_adjustments"] = [dict(a) for a in base.manual_adjustments]
        f = V10Engine(snap, rules=rules, prior_snapshot=get_prior_snapshot(run_id)).run()
    return f


def comparison_for_run(run_id: str, base: Optional[Forecast] = None):
    """(Comparison, refresh Forecast) for the run's latest refresh, or None when the run has no refresh."""
    from app.engine.compare import compare, rules_changed_note
    from app.output.zoho_archive import find_run_folder
    got = get_run_refresh(run_id)
    if got is None:
        return None
    base = base or forecast_for_run(run_id)
    if base is None:
        return None
    ref = refresh_forecast_for_run(run_id, base)
    folder = find_run_folder(run_id)
    note = rules_changed_note(folder / "forecast_rules.json" if folder else None)
    return compare(get_run_snapshot(run_id), got[0], base, ref, note), ref


def diff_matrix_dict(run_matrix: dict, ref_matrix: dict, comp) -> dict:
    """Matrix in the same shape as forecast_to_matrix_dict, holding refresh minus run, with drill-down items."""
    out = json.loads(json.dumps(run_matrix))
    ref_rows = {x["row"]: x for x in ref_matrix["layout"]}
    for x in out["layout"]:
        if x["values"]:
            rv = ref_rows.get(x["row"], {}).get("values") or [0.0] * len(x["values"])
            x["values"] = [round(b - a, 2) for a, b in zip(x["values"], rv)]
    row_of = {v: k for k, v in {**ROW_FIELD, **TOTAL_FIELD}.items()}
    for i, (w, wr) in enumerate(zip(out["weeks"], ref_matrix["weeks"])):
        for name in list(w):
            if name == "week_ending_friday":
                continue
            a, b = w[name], wr.get(name)
            if isinstance(a, dict):
                amt = round(float((b or {}).get("amount") or 0) - float(a.get("amount") or 0), 2)
                items = comp.cell_items.get((row_of.get(name), i), []) if comp is not None else []
                w[name] = {"amount": amt, "confidence": None, "line_items": items}
            elif isinstance(a, (int, float)):
                w[name] = round(float(b or 0) - float(a), 2)
    out["view"] = "diff"
    return out
