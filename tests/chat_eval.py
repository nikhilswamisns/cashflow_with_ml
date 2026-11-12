"""Quality check for the AI chat. Asks the real model ~20 questions and grades the answers against numbers computed
straight from the stored data (not from the chat tools).

    python3 -m tests.chat_eval            # all questions
    python3 -m tests.chat_eval cash       # only questions whose id contains 'cash'

Costs a few cents (OpenAI) and makes no Zoho calls. Not collected by pytest on purpose.
A case passes when: every expected figure appears in the answer (within rounding), the expected tool was called,
required phrases are present, and the number check flagged nothing.
"""
from __future__ import annotations

import sys
import time
from datetime import date

from app.chat import history_store
from app.chat.agent import answer
from app.chat.grounding import MONEY, SCALE, _decimals
from app.chat.registry import Context
from app.working_capital import _bucket, _open
from app.actions import _day


def amounts(text: str) -> list[tuple[float, float]]:
    """(value, tolerance) for every $ amount in the text."""
    out = []
    for m in MONEY.finditer(text):
        raw = m.group(1).replace(",", "")
        mult = SCALE.get((m.group(2) or "").lower(), 1.0)
        out.append((float(raw) * mult, max(1.0, 0.5 * 10 ** -_decimals(raw) * mult)))
    return out


def has_amount(text: str, expected: float) -> bool:
    return any(abs(v - abs(expected)) <= tol for v, tol in amounts(text))


def build_cases(ctx: Context) -> list[dict]:
    m = ctx.matrix
    nxt = [w for w in m["weeks"] if date.fromisoformat(w["week_ending_friday"]) >= ctx.today]
    w1 = nxt[0]
    out1 = w1["opening_cash"] + w1["total_revenue"] - w1["ending_cash"]
    four = nxt[:4]
    low = min(four, key=lambda w: w["ending_cash"])
    inv_w1 = w1.get("cogs_standard")
    inv_w1 = inv_w1["amount"] if isinstance(inv_w1, dict) else inv_w1
    cmp = ctx.ml
    ml_end = lambda w: cmp["ending_cash_ml"][cmp["weeks"].index(w["week_ending_friday"])]  # noqa: E731
    snap, as_of = ctx.snapshot, ctx.snap_date
    ar_open = [r for r in snap["invoices"] if _open(r)]
    ap_open = [r for r in snap["bills"] if _open(r)]
    ar = sum(float(r["balance"]) for r in ar_open)
    ap = sum(float(r["balance"]) for r in ap_open)
    late = [r for r in ar_open if _day(r.get("due_date")) and _day(r["due_date"]) < as_of]
    late90 = sum(float(r["balance"]) for r in late if _bucket((as_of - _day(r["due_date"])).days) == "90+")
    sp = sum(float(r["balance"]) for r in ar_open if "servpro" in (r.get("customer") or "").lower())
    h = history_store.load()
    top = h["payments"].groupby("customer_name")["amount"].sum().sort_values(ascending=False)
    top_name = top.index[0]
    cases = [
        dict(id="cash-next-week", q="What will cash be this coming week?", amounts=[w1["ending_cash"], ml_end(w1)], tools=["cash_outlook"]),
        dict(id="cash-both-views", q="Will we run out of cash in the next 4 weeks?", amounts=[low["ending_cash"], min(ml_end(w) for w in four)], tools=["cash_outlook"], phrases=["ai model"]),
        dict(id="cash-opening", q="How much cash do we start this coming week with?", amounts=[w1["opening_cash"]], tools=["cash_outlook"]),
        dict(id="cash-out-next-week", q="How much money goes out next week in total?", amounts=[out1], tools=["cash_outlook", "outflows_by_purpose"], any_tool=True),
        dict(id="cash-lowest-4w", q="What is the lowest our cash gets over the next 4 weeks, and which week?", amounts=[low["ending_cash"]], tools=["cash_outlook"], phrases=[low["week_ending_friday"][-5:]], loose_date=True),
        dict(id="cash-money-in", q="How much money comes in next week?", amounts=[w1["total_revenue"]], tools=["cash_outlook"]),
        dict(id="out-inventory", q="How much do we spend on inventory next week?", amounts=[inv_w1], tools=["outflows_by_purpose"]),
        dict(id="out-where", q="Where is our cash going over the next 4 weeks?", tools=["outflows_by_purpose"], phrases=["inventory"]),
        dict(id="wc-ar", q="How much do customers owe us in total right now?", amounts=[ar], tools=["working_capital"]),
        dict(id="wc-ap", q="How much do we owe vendors in total right now?", amounts=[ap], tools=["working_capital"]),
        dict(id="wc-90plus", q="How much of our receivables are more than 90 days overdue?", amounts=[late90], tools=["working_capital", "actions"], any_tool=True),
        dict(id="wc-servpro-share", q="What share of our receivables is SERVPRO?", amounts=[], tools=["working_capital"], percent=100 * sp / ar),
        dict(id="act-chase", q="What should I chase this week?", amounts=[float(max(late, key=lambda r: float(r["balance"]) * (as_of - _day(r["due_date"])).days)["balance"])], tools=["actions"]),
        dict(id="act-chase-count", q="How many invoices are overdue and what do they total?", amounts=[round(sum(float(r["balance"]) for r in late), 2)], tools=["actions"]),
        dict(id="cust-top-payer", q=f"How much has {top_name} paid us in total?", amounts=[float(top.iloc[0])], tools=["customer_payments"]),
        dict(id="cust-slowest", q="Which customers pay slowest?", tools=["rank_customers"]),
        dict(id="cust-fastest", q="Which customers pay fastest?", tools=["rank_customers"]),
        dict(id="cust-ambiguous", q="Total payments from SERVPRO", tools=["customer_payments"], phrases=["which"]),
        dict(id="explain-views", q="What is the difference between the AI model and our assumptions?", phrases=["ai model", "assumptions", "paid"], no_tools=True),
        dict(id="unknown-etsy", q="What is our Etsy revenue?", phrases=["in our data"]),
        dict(id="unknown-why", q="Why did SERVPRO's payments drop last quarter?", phrases=["don't have that in our data"]),
        dict(id="unknown-people", q="Who is our highest paid employee?", phrases=["don't have that in our data"], no_tools=True),
        dict(id="unknown-weather", q="What's the weather in Dallas?", phrases=["don't have that in our data"], no_tools=True),
        dict(id="readonly-write", q="Mark invoice INV-006823 as paid in Zoho.", phrases=["read-only"], no_tools=True),
        dict(id="summary", q="Give me a quick summary of our cash situation.", tools=["cash_outlook"]),
    ]
    return cases


def grade(c: dict, r: dict) -> list[str]:
    fails = []
    text = (r.get("answer") or r.get("error") or "")
    low = text.lower().replace("’", "'")
    for a in c.get("amounts", []):
        if not has_amount(text, a):
            fails.append(f"missing ${a:,.2f}")
    if c.get("percent") is not None:
        import re
        got = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s?%", text)]
        if not any(abs(g - c["percent"]) <= 0.6 for g in got):
            fails.append(f"missing {c['percent']:.1f}%")
    for p in c.get("phrases", []):
        if p.lower() not in low and not c.get("loose_date"):
            fails.append(f"missing phrase '{p}'")
    used = [t["tool"] for t in r.get("tools_used", []) if t["tool"] != "no_data_needed"]  # no_data_needed = "answer in words"
    want = c.get("tools", [])
    if want and not (any(t in used for t in want) if c.get("any_tool") else all(t in used for t in want)):
        fails.append(f"tools {used}, wanted {want}")
    if c.get("no_tools") and used:
        fails.append(f"should not call tools, called {used}")
    if r.get("unverified"):
        fails.append(f"unverified figures {r['unverified']}")
    return fails


def main(only: str = "") -> int:
    ctx = Context()
    if ctx.run is None:
        print("No forecast run to test against.")
        return 1
    cases = [c for c in build_cases(ctx) if only in c["id"]]
    bad = 0
    for c in cases:
        t = time.time()
        r = answer(c["q"], ctx=Context())
        fails = grade(c, r)
        bad += bool(fails)
        print(f"{'PASS' if not fails else 'FAIL'}  {c['id']:<18} {time.time() - t:4.1f}s  {c['q']}")
        if fails:
            print("      " + "; ".join(fails))
            print("      answer: " + (r.get("answer") or r.get("error") or "")[:400].replace("\n", " "))
    print(f"\n{len(cases) - bad}/{len(cases)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
