"""Small charts for chat answers. Built from the tool results, never from the model's text, so a chart can only show
numbers the tools returned. Returns None when a result has nothing worth drawing.

Spec: {"kind": "doughnut" | "bar", "title": str, "labels": [str], "values": [float], "signed": bool?,
       "series": [str, str]?, "values2": [float]?}   series/values2 draw a second bar per label (our assumptions vs the AI model)
"""
from __future__ import annotations

from datetime import date


def _short(d: str) -> str:
    return date.fromisoformat(d).strftime("%b %-d")


def chart_for(tool: str, result: dict) -> dict | None:
    if not isinstance(result, dict) or result.get("error"):
        return None
    if tool == "outflows_by_purpose":
        tot = {k: v for k, v in (result.get("totals_over_range") or {}).items() if v and v > 0}
        n = len(result.get("weeks") or [])
        if len(tot) < 2:
            return None
        return {"kind": "doughnut", "title": f"Where cash goes, next {n} week{'s' if n != 1 else ''}",
                "labels": list(tot), "values": list(tot.values())}
    if tool == "cash_outlook":
        weeks = result.get("weeks") or []
        if len(weeks) < 2:
            return None
        spec = {"kind": "bar", "title": "Forecast ending cash by week", "signed": True,
                "labels": [_short(w["week_ending"]) for w in weeks], "values": [w["ending_cash"] for w in weeks]}
        if all("ending_cash_ml" in w for w in weeks):
            spec.update(title="Ending cash by week: our assumptions vs the AI model", signed=False,
                        series=["Our assumptions", "AI model"], values2=[w["ending_cash_ml"] for w in weeks])
        return spec
    if tool == "working_capital":
        b = ((result.get("ar") or {}).get("buckets")) or []
        if not any(x["amount"] for x in b):
            return None
        return {"kind": "bar", "title": "Customers owe us, by days overdue",
                "labels": [x["label"] for x in b], "values": [x["amount"] for x in b]}
    return None
