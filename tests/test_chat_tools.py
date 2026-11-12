from datetime import date

import pandas as pd

from app.chat import tools


def _history():
    inv = pd.DataFrame([
        {"invoice_number": f"A{i}", "customer_name": "Acme Corp", "status": "paid", "total": 100.0, "due_date": "2026-01-10", "date": "2025-12-10"}
        for i in range(5)] + [
        {"invoice_number": f"S{i}", "customer_name": "Slow Co", "status": "paid", "total": 200.0, "due_date": "2026-01-10", "date": "2025-12-10"}
        for i in range(5)] + [
        {"invoice_number": f"M{i}", "customer_name": "Amazon USA", "status": "paid", "total": 50.0, "due_date": "2026-01-10", "date": "2025-12-10"}
        for i in range(5)] + [
        {"invoice_number": "A9", "customer_name": "Acme Corp", "status": "open", "total": 999.0, "due_date": "2026-03-01", "date": "2026-02-01"}])
    pay = pd.DataFrame(
        [{"date": "2026-01-05", "invoice_numbers": f"A{i}", "amount": 100.0, "customer_name": "Acme Corp"} for i in range(5)] +
        [{"date": "2026-02-09", "invoice_numbers": f"S{i}", "amount": 200.0, "customer_name": "Slow Co"} for i in range(5)] +
        [{"date": "2025-12-20", "invoice_numbers": f"M{i}", "amount": 50.0, "customer_name": "Amazon USA"} for i in range(5)])
    from app.ml.history import _dt, norm
    for df in (inv, pay):
        df["name"] = df["customer_name"].map(norm)
    pay["pdate"] = _dt(pay["date"])
    return {"invoices": inv, "payments": pay, "source": "test.xlsx", "last_date": "2026-02-09"}


def _matrix():
    return {"forecast_start_friday": "2026-10-30", "weeks": [
        {"week_ending_friday": "2026-10-30", "opening_cash": 1000.0, "total_revenue": 500.0, "ending_cash": 800.0},
        {"week_ending_friday": "2026-11-06", "opening_cash": 800.0, "total_revenue": 100.0, "ending_cash": -50.0},
        {"week_ending_friday": "2026-11-13", "opening_cash": -50.0, "total_revenue": 900.0, "ending_cash": 700.0}]}


def test_cash_outlook_picks_week_containing_today():
    r = tools.cash_outlook(_matrix(), date(2026, 11, 2), weeks=2)
    assert [w["week_ending"] for w in r["weeks"]] == ["2026-11-06", "2026-11-13"]
    assert r["weeks"][0]["money_out"] == 950.0
    assert r["lowest_in_range"] == {"week_ending": "2026-11-06", "ending_cash": -50.0}


def test_cash_outlook_after_forecast_end():
    assert "error" in tools.cash_outlook(_matrix(), date(2027, 1, 1))


def test_customer_payments_totals_and_open_balance():
    open_inv = [{"customer": "Acme Corp", "balance": 999.0, "status": "sent"}, {"customer": "Acme Corp", "balance": 5, "status": "draft"}]
    r = tools.customer_payments("acme", open_invoices=open_inv, history=_history())
    assert r["customer"] == "Acme Corp" and r["total_paid"] == 500.0 and r["payments"] == 5
    assert r["total_invoiced"] == 500.0 + 999.0 and r["open_now"] == {"count": 1, "balance": 999.0}


def test_customer_payments_unknown_and_ambiguous():
    h = _history()
    assert "error" in tools.customer_payments("zzzz", history=h)
    r = tools.customer_payments("co", history=h)
    assert r["needs_choice"] and r["total_matches"] >= 2


def test_rank_orders_by_days_vs_due_and_skips_marketplaces():
    r = tools.rank_customers(history=_history(), today=date(2026, 3, 1), min_invoices=5)
    assert [c["customer"] for c in r["best"]] == ["Acme Corp", "Slow Co"]
    assert r["best"][0]["avg_days_vs_due"] == -5.0 and r["best"][1]["avg_days_vs_due"] == 30.0
    r2 = tools.rank_customers(history=_history(), today=date(2026, 3, 1), include_marketplaces=True)
    assert r2["best"][0]["customer"] == "Amazon USA"


def test_rank_needs_min_invoices():
    assert tools.rank_customers(history=_history(), today=date(2026, 3, 1), min_invoices=6)["customers_ranked"] == 0


def _snapshot():
    return {"invoices": [{"number": "I1", "customer": "SERVPRO X", "balance": 300.0, "status": "sent", "due_date": "2026-10-01"},
                         {"number": "I2", "customer": "Acme Corp", "balance": 100.0, "status": "sent", "due_date": "2026-12-01"}],
            "bills": [{"number": "B1", "vendor": "Vend", "balance": 50.0, "status": "open", "due_date": "2026-11-05"}]}


def test_working_capital_and_actions_from_snapshot():
    wc = tools.working_capital(_snapshot(), date(2026, 11, 2), None)
    assert wc["ar"]["total"] == 400.0 and wc["dso"] is None and "note" in wc
    wc2 = tools.working_capital(_snapshot(), date(2026, 11, 2), {"sales": 400.0, "cogs": 100.0})
    assert wc2["dso"] == 90.0
    a = tools.actions(_snapshot(), date(2026, 11, 2))
    assert a["invoices"]["count"] == 1 and a["invoices"]["items"][0]["party"] == "SERVPRO X"
    assert a["bills"]["due_within_7_days"] == {"count": 1, "total": 50.0} and a["bills"]["due_within_3_days"] == {"count": 1, "total": 50.0}
    assert "error" in tools.actions(None, date(2026, 11, 2))


def test_outflows_by_purpose_adds_up():
    m = {"weeks": [{"week_ending_friday": "2026-11-06", "opening_cash": 1000.0, "total_revenue": 100.0, "ending_cash": 600.0,
                    "cogs_standard": {"amount": 300.0}, "loan_repayments": 50.0}]}
    r = tools.outflows_by_purpose(m, date(2026, 11, 2))
    w = r["weeks"][0]
    assert w["total_out"] == 500.0 and w["by_purpose"]["Inventory"] == 300.0 and w["by_purpose"]["Other"] == 150.0
    assert round(sum(w["by_purpose"].values()), 2) == 500.0


def test_chat_loop_runs_tool_then_answers(monkeypatch):
    from app.chat import agent, registry
    ctx = registry.Context.__new__(registry.Context)
    ctx.today, ctx.run, ctx._matrix, ctx._snap, ctx._ml = date(2026, 11, 2), {"run_id": "r", "run_date": "2026-10-30"}, _matrix(), None, False
    replies = iter([
        [{"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "cash_outlook", "arguments": '{"weeks"'}}]}}]},
         {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": ': 1}'}}]}}]}],
        [{"choices": [{"delta": {"content": "Cash ends "}}]}, {"choices": [{"delta": {"content": "the week at -$50."}}]}]])
    seen = []
    out = agent.answer("How is cash next week?", ctx=ctx, post=lambda p: (seen.append(p), next(replies))[1])
    assert out["answer"] == "Cash ends the week at -$50." and out["tools_used"] == [{"tool": "cash_outlook", "args": {"weeks": 1}}]
    tool_msg = [m for m in seen[1]["messages"] if m["role"] == "tool"][0]
    assert "-50" in tool_msg["content"]


def test_unknown_tool_and_missing_key(monkeypatch):
    from app.chat import agent, registry
    ctx = registry.Context.__new__(registry.Context)
    ctx.run = {"run_id": "r"}
    assert "error" in registry.run_tool("delete_everything", {}, ctx)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agent.dotenv, "load_dotenv", lambda *a, **k: False)  # do not re-read the real .env
    assert "error" in agent.answer("hi")


def test_grounding_accepts_rounded_figures_and_flags_made_up_ones():
    from app.chat.grounding import unverified
    res = [{"ending_cash": -26200.65, "share": 0.9095, "avg": 15.8, "total": 216023.4}]
    ok = "Cash ends at negative $26,201, 91% is not due, slowest pay 15.8 days late, inventory $216K or $216,023."
    assert unverified(ok, res) == []
    assert unverified("Two invoices total $1,726.", [{"a": 836.0, "b": 890.0}]) == []   # a sum of two real figures
    assert unverified("Two invoices total $1,800.", [{"a": 836.0, "b": 890.0}]) == ["$1,800"]
    bad = unverified("Cash is $30,000 and 77% is late, paid 9.4 days late.", res)
    assert bad == ["$30,000", "77%", "9.4 days"]


def test_freshness_line_flags_old_data():
    from datetime import date as d
    from app.chat import agent
    ctx = type("C", (), {"run": {"x": 1}, "today": d(2026, 11, 11), "snap_date": d(2026, 11, 5)})()
    assert "6 days ago" in agent._freshness(ctx) and "as of the Nov 5 sync" in agent._freshness(ctx)
    ctx.snap_date = d(2026, 11, 11)
    assert "as of" not in agent._freshness(ctx)


def test_charts_come_from_tool_results():
    from app.chat.charts import chart_for
    o = tools.outflows_by_purpose({"weeks": [{"week_ending_friday": "2026-11-06", "opening_cash": 1000.0, "total_revenue": 100.0,
                                              "ending_cash": 600.0, "cogs_standard": 300.0, "loan_repayments": 50.0}]}, date(2026, 11, 2))
    c = chart_for("outflows_by_purpose", o)
    assert c["kind"] == "doughnut" and dict(zip(c["labels"], c["values"]))["Inventory"] == 300.0 and 0 not in c["values"]
    cash = chart_for("cash_outlook", tools.cash_outlook(_matrix(), date(2026, 10, 1), weeks=3))
    assert cash["kind"] == "bar" and cash["values"] == [800.0, -50.0, 700.0] and cash["labels"][0] == "Oct 30"
    assert chart_for("cash_outlook", tools.cash_outlook(_matrix(), date(2026, 11, 2), weeks=1)) is None  # one week: no chart
    wc = chart_for("working_capital", tools.working_capital(_snapshot(), date(2026, 11, 2), None))
    assert wc["labels"][0] == "Not due" and sum(wc["values"]) == 400.0
    assert chart_for("customer_payments", {"total_paid": 5}) is None and chart_for("actions", {"error": "x"}) is None


def test_cash_outlook_carries_ml_view_when_available():
    ml = {"weeks": ["2026-10-30", "2026-11-06", "2026-11-13"], "ending_cash_ml": [750.0, 100.0, 650.0],
          "bands": {"p10": [700.0, 0.0, 600.0], "p90": [800.0, 200.0, 700.0]}}
    r = tools.cash_outlook(_matrix(), date(2026, 10, 1), weeks=3, ml=ml)
    assert [w["ending_cash_ml"] for w in r["weeks"]] == [750.0, 100.0, 650.0]
    assert r["weeks"][1]["ml_range_low"] == 0.0 and r["lowest_in_range_ml"] == {"week_ending": "2026-11-06", "ending_cash": 100.0}
    from app.chat.charts import chart_for
    c = chart_for("cash_outlook", r)
    assert c["series"] == ["Our assumptions", "AI model"] and c["values2"] == [750.0, 100.0, 650.0] and c["values"] == [800.0, -50.0, 700.0]
    plain = tools.cash_outlook(_matrix(), date(2026, 10, 1), weeks=3)
    assert "ml_note" in plain and "values2" not in chart_for("cash_outlook", plain)


def test_transcribe_checks_audio_and_returns_text(monkeypatch):
    from app.chat import voice
    monkeypatch.setattr(voice.dotenv, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert "error" in voice.transcribe(b"")
    assert "too long" in voice.transcribe(b"x" * (voice.MAX_BYTES + 1))["error"]
    seen = {}
    ok = voice.transcribe(b"abc", "a.webm", "audio/webm", post=lambda d, f, c: (seen.update(n=len(d), f=f), {"text": "  What will cash be?  "})[1])
    assert ok == {"text": "What will cash be?"} and seen == {"n": 3, "f": "a.webm"}
    assert "hear" in voice.transcribe(b"abc", post=lambda d, f, c: {"text": " "})["error"]
    monkeypatch.delenv("OPENAI_API_KEY")
    assert "OPENAI_API_KEY" in voice.transcribe(b"abc")["error"]


def test_actions_says_how_many_invoices_are_not_shown():
    from datetime import date
    snap = {"invoices": [{"number": f"I{n}", "customer": "A", "due_date": "2026-10-01", "balance": 100 + n, "status": "sent"} for n in range(5)],
            "bills": []}
    out = tools.actions(snap, date(2026, 11, 1), limit=3)
    assert out["invoices"]["count"] == 5 and len(out["invoices"]["items"]) == 3
    ns = out["invoices"]["not_shown"]
    assert ns["count"] == 2 and ns["total"] == 201.0  # the two smallest (100 and 101) are the ones left off
    full = tools.actions(snap, date(2026, 11, 1), limit=10)
    assert "not_shown" not in full["invoices"]
