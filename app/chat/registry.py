"""Tool list for the chat: JSON schemas the model sees, plus a runner that binds each tool to the latest forecast run.

Provider-neutral: SPECS is plain JSON schema, run_tool() takes a name and a dict. Everything is read-only.
"""
from __future__ import annotations

import json
import logging
from datetime import date

from app import db
from app.chat import tools

logger = logging.getLogger(__name__)

NO_DATA = "no_data_needed"
SPECS = [
    {"name": NO_DATA, "description": "Call this, and nothing else, only when the question needs no figures from our data: explaining how our assumptions and the AI model differ, greetings, questions about reasons or causes (why something changed), trends over past quarters or years, anything outside our data, or a request to change something. Then answer in words with no new numbers.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "cash_outlook", "description": "Forecast cash balance for the coming week(s): opening cash, money in, money out, ending cash according to our assumptions AND according to the AI model (plus its likely range), and the lowest week.",
     "parameters": {"type": "object", "properties": {"weeks": {"type": "integer", "description": "How many forecast weeks from this week (1-13)."}}}},
    {"name": "outflows_by_purpose", "description": "Where forecast cash goes each week: inventory, freight, payroll (assumed), marketing, fulfilment, loans, other.",
     "parameters": {"type": "object", "properties": {"weeks": {"type": "integer", "description": "How many weeks (1-13). Default 4."}}}},
    {"name": "customer_payments", "description": "What one customer has paid us in total, first/last payment, total invoiced, and what they owe now.",
     "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Customer name or part of it."}}, "required": ["name"]}},
    {"name": "rank_customers", "description": "Customers ranked by how fast they pay (average days after the due date; negative = early). Also lists the slowest.",
     "parameters": {"type": "object", "properties": {"months": {"type": "integer"}, "top": {"type": "integer"}, "min_invoices": {"type": "integer"},
                                                      "include_marketplaces": {"type": "boolean"}}}},
    {"name": "working_capital", "description": "Receivables and payables aging (not due, 0-30, 31-60, 61-90, 90+), DSO, DPO and customer concentration (e.g. SERVPRO share).",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "actions", "description": "Overdue invoices to chase and bills to pay in the next 14 days, biggest first.",
     "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Items per list (1-25). Default 10."}}}},
]



def rules_matrix(run_id: str) -> dict | None:
    """The run's matrix timed by our assumptions only. When the app has the AI model switched on in its settings, the saved
    matrix is already AI-timed, so rebuild it with the AI model off (the same way the AI-model comparison does)."""
    from app.output.json_api import get_matrix
    try:
        import copy
        from app.engine.v10_engine import V10Engine
        from app.output.v10_adapter import forecast_for_run, forecast_to_matrix_dict, get_prior_snapshot, get_run_snapshot
        base = forecast_for_run(run_id)
        if base is not None and (base.rules.get("ml") or {}).get("enabled"):
            rules = copy.deepcopy(base.rules)
            rules["ml"]["enabled"] = False
            rules["opening_cash"]["manual_adjustments"] = [dict(x) for x in base.manual_adjustments]
            snap = get_run_snapshot(run_id)
            return forecast_to_matrix_dict(V10Engine(snap, rules=rules, prior_snapshot=get_prior_snapshot(run_id)).run())
    except Exception:
        logger.warning("Could not rebuild the assumptions-only matrix for run %s", run_id, exc_info=True)
    return get_matrix(run_id)


class Context:
    """The latest executed run, loaded once per question."""

    def __init__(self, today: date | None = None):
        self.today = today or date.today()
        self.run = next((r for r in (db.get_run(x["run_id"]) for x in db.list_runs()) if r and r.get("matrix_json")), None)
        self._matrix = self._snap = self._ml = None

    @property
    def matrix(self) -> dict | None:
        if self._matrix is None and self.run:
            self._matrix = rules_matrix(self.run["run_id"])
        return self._matrix

    @property
    def ml(self) -> dict | None:
        """Rules-vs-ML comparison for the run (same call the dashboard makes, cached). None when it cannot be built."""
        if self._ml is None and self.run:
            try:
                from app.ml.api import ml_compare
                self._ml = ml_compare(self.run["run_id"])
            except Exception:
                logger.warning("ML comparison unavailable for chat", exc_info=True)
                self._ml = False
        return self._ml or None

    @property
    def snapshot(self) -> dict | None:
        if self._snap is None and self.run:
            from app.output.v10_adapter import get_run_snapshot
            self._snap = get_run_snapshot(self.run["run_id"])
        return self._snap

    @property
    def snap_date(self) -> date:
        from app.actions import snapshot_date
        return snapshot_date(self.snapshot or {}, self.run)


def run_tool(name: str, args: dict, ctx: Context) -> dict:
    try:
        if name not in {s["name"] for s in SPECS}:
            return {"error": f"Unknown tool {name}"}
        if name == NO_DATA:
            return {"note": "No data is needed for this. Do not state any new dollar amounts, percentages or day counts."}
        if ctx.run is None:
            return {"error": "No forecast run exists yet. Run a Sync from Zoho first."}
        if name == "cash_outlook":
            return tools.cash_outlook(ctx.matrix, ctx.today, int(args.get("weeks") or 1), ctx.run.get("run_date"), ml=ctx.ml)
        if name == "outflows_by_purpose":
            return tools.outflows_by_purpose(ctx.matrix, ctx.today, int(args.get("weeks") or 4))
        if name == "customer_payments":
            return tools.customer_payments(str(args.get("name") or ""), (ctx.snapshot or {}).get("invoices"))
        if name == "rank_customers":
            kw = {k: args[k] for k in ("months", "top", "min_invoices", "include_marketplaces") if args.get(k) is not None}
            return tools.rank_customers(today=ctx.today, **kw)
        if name == "working_capital":
            flows = None
            try:
                from app.zoho_flows import get_flows
                flows = get_flows(today=ctx.snap_date)
            except Exception:
                logger.exception("Flows unavailable for chat")
            return tools.working_capital(ctx.snapshot, ctx.snap_date, flows)
        return tools.actions(ctx.snapshot, ctx.snap_date, int(args.get("limit") or 10))
    except Exception as e:  # a failing tool must not crash the chat; the model reports it
        logger.exception("Chat tool %s failed", name)
        return {"error": f"{name} failed: {type(e).__name__}"}


def _whole_dollars(x):
    """Amounts of 100 or more go to the model as whole dollars so it copies them instead of truncating cents."""
    if isinstance(x, float) and abs(x) >= 100:
        return round(x)
    if isinstance(x, dict):
        return {k: _whole_dollars(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_whole_dollars(v) for v in x]
    return x


def result_text(result: dict, limit: int = 12000) -> str:
    s = json.dumps(_whole_dollars(result), default=str)
    return s if len(s) <= limit else s[:limit] + "...(truncated)"
