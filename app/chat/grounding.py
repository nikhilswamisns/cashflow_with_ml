"""Checks that the figures in an answer came from the tool results.

The model writes the dollar amounts itself, so after each answer we read every $ amount, percentage and decimal "days"
figure out of the text and look for it in the numbers the tools returned (within rounding). Figures that match nothing (or a sum of two tool figures)
are returned so the UI can warn instead of presenting them as fact. Counts, dates and years are not checked.
"""
from __future__ import annotations

import re

MONEY = re.compile(r"(?<![\w])\$\s?(\d[\d,]*(?:\.\d+)?)\s*(thousand|million|k|m)?\b", re.I)
PERCENT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?%")
DAYS = re.compile(r"(?<![\w.])(\d+\.\d+)\s+days?\b", re.I)
SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6}


def tool_numbers(results: list) -> list[float]:
    """Every number found anywhere in the tool results (absolute values)."""
    out: list[float] = []

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            out.append(abs(float(x)))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    walk(results)
    return out


def _decimals(s: str) -> int:
    return len(s.split(".")[1]) if "." in s else 0


def _close(x: float, tol: float, pool: list[float]) -> bool:
    return any(abs(v - x) <= tol + 0.0051 for v in pool)


def _close_or_sum(x: float, tol: float, pool: list[float]) -> bool:
    """A quoted amount is grounded if it matches a tool figure, or the sum of two of them (e.g. two invoices for one customer)."""
    if _close(x, tol, pool):
        return True
    small = [v for v in pool if v <= x + tol]
    have = set(small)
    return any(abs((x - v) - w) <= 2 * tol + 0.0101 for v in small for w in have if w <= x - v + tol + 0.01)


def figures_in(text: str) -> list[float]:
    """Dollar amounts, percents and day counts written in `text` (used for what earlier answers already said)."""
    out = [float(m.group(1).replace(",", "")) * SCALE.get((m.group(2) or "").lower(), 1.0) for m in MONEY.finditer(text)]
    out += [float(m.group(1)) for m in PERCENT.finditer(text)] + [float(m.group(1)) for m in DAYS.finditer(text)]
    return out


def unverified(text: str, results: list, earlier: list[float] | None = None) -> list[str]:
    """Figures quoted in `text` that match no number in `results` (or in `earlier`, figures from replies already given in
    this conversation, which came from tools in their own turn), as written in the text."""
    pool = tool_numbers(results) + [abs(v) for v in (earlier or [])]
    bad: list[str] = []
    for m in MONEY.finditer(text):
        raw = m.group(1).replace(",", "")
        mult = SCALE.get((m.group(2) or "").lower(), 1.0)
        x = float(raw) * mult
        tol = 0.5 * 10 ** -_decimals(raw) * mult
        if not _close_or_sum(x, tol, pool):
            bad.append(m.group(0).strip().rstrip(",."))
    for m in PERCENT.finditer(text):
        x = float(m.group(1))
        tol = 0.5 * 10 ** -_decimals(m.group(1))
        if not (_close(x, tol, pool) or _close(x, tol, [v * 100 for v in pool])):
            bad.append(m.group(0).strip())
    for m in DAYS.finditer(text):
        if not _close(float(m.group(1)), 0.05, pool):
            bad.append(m.group(0).strip())
    return list(dict.fromkeys(bad))
