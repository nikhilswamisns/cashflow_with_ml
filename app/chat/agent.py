"""The chat loop: question -> model -> tool calls -> answer, streamed. OpenAI Chat Completions over httpx; the key comes
from .env (OPENAI_API_KEY) and is never logged. `post(payload)` yields OpenAI stream chunks and is injectable so tests
run without the network.

events() yields {"type": "tool", "tool": name}  a tool is being read
                {"type": "delta", "text": str}  next piece of the answer
                {"type": "chart", "chart": spec}  a small chart built from a tool result
                {"type": "check", "unverified": [str]}  figures in the answer that match no tool result (only sent when there are some)
                {"type": "done", "tools_used": [...], "run_date": str|None}
                {"type": "error", "message": str}
"""
from __future__ import annotations

import json
import os
from typing import Iterator

import dotenv
import httpx

from app.chat.registry import NO_DATA
from app.chat.charts import chart_for

# where the same numbers are already drawn on the dashboard, so an answer can point at the chart
LINKS = {
    "cash_outlook": {"label": "See the Cash position chart", "to": "/"},
    "outflows_by_purpose": {"label": "See the Where cash goes chart", "to": "/"},
    "working_capital": {"label": "Open Working capital", "to": "/working-capital"},
    "actions": {"label": "Open Actions", "to": "/actions"},
}
from app.chat.grounding import figures_in, unverified
from app.chat.registry import SPECS, Context, result_text, run_tool

URL = "https://api.openai.com/v1/chat/completions"
MAX_STEPS = 6
MAX_HISTORY = 12

SYSTEM = """You are the cash flow advisor inside a company's weekly cash forecast dashboard.
Answer only from the tools. Call them to get numbers; never guess or use outside knowledge of the company.
Rules:
- Use plain words and dollar amounts with commas. Be short: lead with the answer, then 2-4 supporting points.
- Every new question about our data needs a fresh tool call in this turn, even when it looks like an earlier answer. Never reuse customer
  names or amounts from earlier replies as if they answered a different question.
- Do not add a "source" or "used" line; the interface handles that.
- If a tool returns an error or the data is missing, say "not found in our data" and what is needed. Do not invent.
- If a customer name matches several customers, list a few and ask which one.
- Payroll lines in the forecast are assumptions, not Zoho actuals; say so when you quote payroll.
- Whenever you give a cash balance, give both views: "our assumptions" (ending_cash) and "the AI model" (ending_cash_ml), e.g.
  "According to our assumptions, cash ends the week at $X. According to the AI model, which learns from how each customer has
  paid in the past, it is $Y." Lead with our assumptions. If the AI model is not in the tool result, give our assumptions only
  and say the AI model is not available right now. Do not blend them or pick one as "right"; if they differ a lot, say so in one sentence.
- For "lowest", "run out" or "will we go negative" questions, give the lowest week for each view (lowest_in_range for our assumptions,
  lowest_in_range_ml for the AI model), with the week and the amount.
- If asked how the two views differ (call no_data_needed, then answer in words): our assumptions assume each open invoice and bill is paid on
  its expected date; the AI model moves that date for each customer or vendor based on how they have actually paid in the past, and
  also gives a likely range. Neither is a guarantee.
- Use only those two names. Never say "ML", "machine learning", "rules", "standard timing", "timing rules" or "percentile";
  say "likely range" for the AI model's range.
- When a list is cut short (a tool gives "not_shown" or a count bigger than the items), say so plainly, for example "the top 10 of 12 overdue invoices; the other 2 total $1,503".
- Copy dollar amounts exactly as the tools give them. Never truncate, re-round or estimate them, and do not add figures together
  yourself: no "about $X" for a combined amount. Use a total only if a tool field gives it (for example `total`, `count`).
- You are read-only. If asked to change, mark, send, pay or delete anything, start with exactly "I'm read-only, so I can't change
  Zoho or the forecast." then offer to show the related data (for example the invoice's customer and balance).
- What you can answer: the cash forecast by week, where cash goes by purpose, receivables and payables aging with DSO/DPO
  and concentration, overdue invoices and bills to act on, what one customer has paid, and which customers pay fastest or slowest.
- For anything outside that (other systems, causes or reasons the data does not hold, predictions beyond the forecast,
  people, anything not in the tools, and reasons for why something changed or trends over past quarters), start with exactly "I don't have that in our data." then say in one line what you can answer instead.
  Never fill the gap with a guess or general knowledge.
Dates are Fridays that end forecast weeks. Today is {today}.
{freshness}"""


def _freshness(ctx: Context) -> str:
    """One line telling the model how old the forecast data is, so it can say so when it matters."""
    if not ctx.run:
        return "There is no forecast run yet."
    try:
        synced = ctx.snap_date  # the day the open items were read from Zoho
    except Exception:
        return ""  # unknown age: say nothing rather than break the chat
    age = (ctx.today - synced).days
    line = f"The data comes from the Zoho sync of {synced.isoformat()} ({age} days ago)."
    if age >= 3:
        line += " That is not recent: say 'as of the " + synced.strftime("%b %-d") + " sync' in the first sentence of any answer that uses it."
    return line


def _default_post(payload: dict, key: str) -> Iterator[dict]:
    with httpx.stream("POST", URL, json={**payload, "stream": True}, headers={"Authorization": f"Bearer {key}"}, timeout=60) as r:
        if r.status_code >= 400:
            r.read()
            r.raise_for_status()
        for line in r.iter_lines():
            if line.startswith("data: ") and line[6:].strip() != "[DONE]":
                yield json.loads(line[6:])


def events(question: str, history: list[dict] | None = None, ctx: Context | None = None, post=None) -> Iterator[dict]:
    dotenv.load_dotenv()  # the key lives in the project .env
    key = os.environ.get("OPENAI_API_KEY", "")
    if post is None:
        if not key or key == "open-ai-key":
            yield {"type": "error", "message": "OPENAI_API_KEY is not set on this server."}
            return
        post = lambda p: _default_post(p, key)  # noqa: E731
    ctx = ctx or Context()
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    msgs = [{"role": "system", "content": SYSTEM.format(today=ctx.today.isoformat(), freshness=_freshness(ctx))}]
    msgs += [{"role": m["role"], "content": str(m["content"])} for m in (history or [])[-MAX_HISTORY:] if m.get("role") in ("user", "assistant")]
    earlier = [v for m in msgs[1:] if m["role"] == "assistant" for v in figures_in(m["content"])]
    msgs.append({"role": "user", "content": question})
    spec = [{"type": "function", "function": s} for s in SPECS]
    used: list[dict] = []
    results: list[dict] = []
    shown: set[str] = set()
    linked: set[str] = set()
    answer_text = ""
    for _ in range(MAX_STEPS):
        text, calls = "", {}
        # the first step of every turn must pick a tool (a data tool, or no_data_needed), so an answer can never come from memory
        req = {"model": model, "messages": msgs, "tools": spec, "temperature": 0, **({} if used else {"tool_choice": "required"})}
        for ch in post(req):
            if not ch.get("choices"):
                continue
            d = ch["choices"][0].get("delta") or {}
            if d.get("content"):
                text += d["content"]
                answer_text += d["content"]
                yield {"type": "delta", "text": d["content"]}
            for tc in d.get("tool_calls") or []:
                c = calls.setdefault(tc.get("index", 0), {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                c["id"] = tc.get("id") or c["id"]
                f = tc.get("function") or {}
                c["function"]["name"] += f.get("name") or ""
                c["function"]["arguments"] += f.get("arguments") or ""
        if not calls:
            bad = unverified(answer_text, results, earlier)
            if bad:
                yield {"type": "check", "unverified": bad}
            yield {"type": "done", "tools_used": used, "run_date": (ctx.run or {}).get("run_date")}
            return
        msgs.append({"role": "assistant", "content": text or None, "tool_calls": [calls[i] for i in sorted(calls)]})
        for i in sorted(calls):
            c = calls[i]
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"]["arguments"] or "{}")
            except ValueError:
                args = {}
            used.append({"tool": name, "args": args})
            if name != NO_DATA:
                yield {"type": "tool", "tool": name}
            res = run_tool(name, args, ctx)
            results.append(res)
            chart = chart_for(name, res)
            if chart and chart["title"] not in shown:
                shown.add(chart["title"])
                yield {"type": "chart", "chart": chart}
            link = LINKS.get(name)
            if link and "error" not in res and link["to"] not in linked:
                linked.add(link["to"])
                yield {"type": "link", **link}
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": result_text(res)})
    yield {"type": "delta", "text": "I could not finish that within the step limit. Try a narrower question."}
    yield {"type": "done", "tools_used": used, "run_date": (ctx.run or {}).get("run_date")}


def answer(question: str, history: list[dict] | None = None, ctx: Context | None = None, post=None) -> dict:
    """Non-streaming form for scripts and tests: the full answer plus the tools used."""
    text, out, bad = "", {}, []
    for e in events(question, history, ctx, post):
        if e["type"] == "check":
            bad = e["unverified"]
        if e["type"] == "delta":
            text += e["text"]
        elif e["type"] == "error":
            return {"error": e["message"]}
        elif e["type"] == "done":
            out = e
    return {"answer": text, "tools_used": out.get("tools_used", []), "run_date": out.get("run_date"), "unverified": bad}
