"""API for the ML layer:  /api/ml/...   (login-protected like every other /api route)

GET  /api/ml/status                     is a model trained, on what data, when
POST /api/ml/train                      train from ml_data/Zoho_history_*.xlsx (newest) or an uploaded workbook
POST /api/ml/backtest                   walk-forward test: ML vs the current fixed rules (takes ~1 minute)
GET  /api/ml/revenue-forecast           monthly revenue history + 12-month forecast with range (from ml_work/outputs)
GET  /api/ml/runs/{run_id}/compare      this run forecast with rules vs with ML, plus P10/P50/P90 ending-cash bands
"""
from __future__ import annotations

import copy
import json
import logging
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.ml import HISTORY_DIR, ROOT
from app.ml.result_cache import ResultCache

router = APIRouter(tags=["ml"])
_compare_cache = ResultCache(size=8)
_receipts_cache = ResultCache(size=8)


@router.get("/status")
def ml_status():
    from app.ml.train import latest_history_file, status
    h = latest_history_file()
    rules = json.loads((ROOT / "app" / "config" / "forecast_rules.json").read_text(encoding="utf-8"))
    mlr = rules.get("ml") or {}
    return {**status(), "enabled_in_rules": bool(mlr.get("enabled")),
            "use_for": mlr.get("use_for", {"invoices": True, "sales_orders": True, "bills": False}),
            "history_file_found": h.name if h else None}


class MLSettings(BaseModel):
    enabled: Optional[bool] = None
    invoices: Optional[bool] = None
    sales_orders: Optional[bool] = None
    bills: Optional[bool] = None


@router.post("/settings")
def ml_settings(body: MLSettings):
    """Switch ML timing on/off (and per document type) by editing the "ml" block of forecast_rules.json.
    Takes effect on the next forecast run - no restart needed (the engine reads the file on every run)."""
    path = ROOT / "app" / "config" / "forecast_rules.json"
    rules = json.loads(path.read_text(encoding="utf-8"))
    ml = rules.setdefault("ml", {"enabled": False, "use_for": {}})
    if body.enabled:
        from app.ml import MODEL_FILE
        if not MODEL_FILE.exists():
            raise HTTPException(409, "Train the model first (ML Forecast page > Train model).")
    use = ml.setdefault("use_for", {"invoices": True, "sales_orders": True, "bills": False})
    if body.enabled is not None:
        ml["enabled"] = body.enabled
    for k in ("invoices", "sales_orders", "bills"):
        v = getattr(body, k)
        if v is not None:
            use[k] = v
    backup = path.with_name("forecast_rules.json.before_ml_ui")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(json.dumps(rules, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"enabled": ml["enabled"], "use_for": use}


@router.post("/train")
def ml_train(file: Optional[UploadFile] = File(None)):
    from app.ml.train import train
    try:
        if file is not None:
            HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            dest = HISTORY_DIR / (Path(file.filename or "Zoho_history_upload.xlsx").name)
            with open(dest, "wb") as out:
                shutil.copyfileobj(file.file, out)
            return train(dest)
        return train()
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Training failed: {e}")


@router.post("/backtest")
def ml_backtest(cutoffs: int = 6):
    from app.ml.backtest import run_backtest
    from app.ml.train import latest_history_file
    h = latest_history_file()
    if h is None:
        raise HTTPException(404, "No Zoho history workbook in ml_data/.")
    return run_backtest(h, n_cutoffs=max(2, min(cutoffs, 10)))


@router.get("/runs/{run_id}/compare")
def ml_compare(run_id: str):
    """Rules vs ML-timed forecast. About 2 s to compute, so the result is cached by run, its data and the model/rules files."""
    from app.ml.result_cache import fingerprint
    from app.output.v10_adapter import get_prior_snapshot, get_run_snapshot
    from app import db
    snap = get_run_snapshot(run_id)
    if snap is None:
        raise HTTPException(404, "Run not found")
    run = db.get_run(run_id) or {}
    key = (run_id, fingerprint(snap, get_prior_snapshot(run_id), run.get("opening_cash_amount"), run.get("opening_cash_date")))
    return _compare_cache.get_or_compute(key, lambda: _compute_compare(run_id, snap))


def _compute_compare(run_id: str, snap: dict):
    from app.engine.v10_engine import ROW_ENDING, V10Engine
    from app.ml.montecarlo import cash_bands
    from app.output.v10_adapter import forecast_for_run, get_prior_snapshot
    base = forecast_for_run(run_id)

    def build(enabled: bool):
        rules = copy.deepcopy(base.rules)
        rules.setdefault("ml", {})["enabled"] = enabled
        rules["opening_cash"]["manual_adjustments"] = [dict(a) for a in base.manual_adjustments]
        return V10Engine(snap, rules=rules, prior_snapshot=get_prior_snapshot(run_id)).run()

    rule_f, ml_f = build(False), build(True)
    warn = [e for e in ml_f.exceptions if e.startswith("ML timing")]
    if warn:
        raise HTTPException(409, warn[0])
    mc = (ml_f.rules.get("ml") or {}).get("montecarlo", {})
    bands = cash_bands(ml_f, simulations=int(mc.get("simulations", 2000)), seed=int(mc.get("seed", 42)),
                       party_correlation=float(mc.get("party_correlation", 0.5)))
    moved = [{"source": r.source, "ref": r.ref, "party": r.party, "amount": r.amount, "week": r.week.isoformat(),
              "expected": r.ml["p50"].isoformat(), "p10": r.ml["p10"].isoformat(), "p90": r.ml["p90"].isoformat(),
              "shift_days": r.ml["shift_days"]} for r in ml_f.revenue + ml_f.cogs if r.ml]
    return {"run_id": run_id, "weeks": bands["weeks"],
            "ending_cash_rules": rule_f.values[ROW_ENDING], "ending_cash_ml": ml_f.values[ROW_ENDING],
            "bands": {k: bands[k] for k in ("p10", "p50", "p90")}, "ml_lines": bands["ml_lines"], "note": bands["note"],
            "lines_retimed": sorted(moved, key=lambda x: -abs(x["amount"] * x["shift_days"]))[:100]}


def _actuals_or_503(fridays, today=None, start=None):
    from app.ml.actuals import weekly_actuals
    try:
        return weekly_actuals(fridays, today, start=start)
    except Exception as e:  # noqa: BLE001 - no Zoho keys here, or Zoho is down: the dashboard just hides the green line
        raise HTTPException(503, f"Actual cash is not available on this server ({type(e).__name__}).")


@router.get("/runs/{run_id}/actuals")
def run_actuals(run_id: str):
    """Actual cash (Zoho books, read-only) from the day this run was made (its start) to today: the balance at the start,
    at the end of each past Friday, and today's balance. Never later than today."""
    from datetime import date, datetime, timedelta
    from app import db
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    first = date.fromisoformat(str(run["run_date"])[:10])
    start = datetime.fromisoformat(run["created_at"]).date()
    fridays = [first + timedelta(weeks=i) for i in range(52)]
    return {"run_id": run_id, "first_week": first.isoformat(), "start_date": start.isoformat(), **_actuals_or_503(fridays, start=start)}


@router.get("/runs/{run_id}/receipts-outlook")
def receipts_outlook(run_id: str):
    """Weekly receipts in layers (booked documents, flat run-rate, ML revenue forecast addition). Read-only."""
    from app.ml.receipts_outlook import FORECAST_CSV, build_outlook
    from app.output.v10_adapter import forecast_for_run
    if not FORECAST_CSV.exists():
        raise HTTPException(404, "Forecast files not found. Run ml_work/05_calibrate_range.py first.")
    from app.ml.result_cache import _FILES_THAT_CHANGE_RESULTS, fingerprint
    from app.output.v10_adapter import get_prior_snapshot, get_run_snapshot
    from app import db
    snap = get_run_snapshot(run_id)
    if snap is None:
        raise HTTPException(404, "Run not found")
    run = db.get_run(run_id) or {}
    key = ("receipts", run_id, fingerprint(snap, get_prior_snapshot(run_id), run.get("opening_cash_amount"), run.get("opening_cash_date"),
                                           files=[*_FILES_THAT_CHANGE_RESULTS, FORECAST_CSV]))

    def build():
        f = forecast_for_run(run_id)
        return {"run_id": run_id, **build_outlook(f)}
    return _receipts_cache.get_or_compute(key, build)


@router.get("/revenue-forecast")
def revenue_forecast():
    """Read-only: the ML work's monthly revenue history and 12-month forecast (ml_work/outputs/*.csv)."""
    import csv
    out = ROOT / "ml_work" / "outputs"
    files = {"history": out / "monthly_table.csv", "forecast": out / "05_forecast_new_range.csv",
             "backtest": out / "05_backtest_new_range.csv"}
    if not files["history"].exists() or not files["forecast"].exists():
        raise HTTPException(404, "Forecast files not found. Run ml_work/02_build_monthly_table.py and 05_calibrate_range.py first.")

    def rows(f):
        with open(f, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    history = [{"date": r["date"][:7], "revenue": round(float(r["Total"]))} for r in rows(files["history"])]
    fc = rows(files["forecast"])
    forecast = [{"date": r[""][:7], "forecast": float(r["trend_forecast"]), "low": float(r["low"]), "high": float(r["high"])} for r in fc]
    last12 = sum(h["revenue"] for h in history[-12:])
    next12 = sum(f["forecast"] for f in forecast)
    accuracy = None
    if files["backtest"].exists():
        bt = rows(files["backtest"])
        misses = [abs(float(r["miss_pct"])) for r in bt]
        accuracy = {"months": len(bt), "avg_miss_pct": round(sum(misses) / len(misses), 1),
                    "inside_range": sum(1 for r in bt if r["inside_range"] == "True")}
    return {"history": history, "forecast": forecast,
            "summary": {"last12": round(last12), "next12": round(next12),
                        "growth_pct": round((next12 / last12 - 1) * 100, 1) if last12 else None,
                        "low12": round(sum(f["low"] for f in forecast)), "high12": round(sum(f["high"] for f in forecast))},
            "accuracy": accuracy,
            "model": "Log-linear trend on the last 24 months (best of 12 models tested)"}


def warm_caches(limit: int = 3) -> None:
    """Compute the slow results (rules/ML comparison, receipts outlook) for the newest runs once, in the background,
    so the first page load after a restart does not wait for them."""
    def work():
        from app import db
        for r in db.list_runs()[:limit]:
            for fn in (ml_compare, receipts_outlook):
                try:
                    fn(r["run_id"])
                except Exception as e:  # noqa: BLE001 - warming is best effort
                    logging.getLogger(__name__).info("warm %s for %s skipped: %s", fn.__name__, r["run_id"][:8], e)
    threading.Thread(target=work, daemon=True, name="warm-ml-caches").start()
