from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel

from app import db
from app.adapters.file_upload import detect_source, parse_source
from app.config.loader import invalidate_cache, load_assumptions
from app.engine.matrix_builder import build_matrix
from app.engine.transform_engine import TransformEngine
from app.engine.validation_gate import ValidationGate
from app.models.canonical import DataConfidence, safe_parse_date, safe_parse_datetime
from app.models.matrix import WeeklyMatrix
from app.output.xlsx_exporter import XLSXExporter
from app.preflight import run_preflight
from app.transforms.date_bucketing import next_friday, prev_friday

CONFIG_DIR = Path(__file__).parent.parent / "config"
logger = logging.getLogger(__name__)
router = APIRouter()


def _serialize_week_slice(ws) -> dict:
    def cell_to_dict(cell):
        if hasattr(cell, "amount"):
            return {
                "amount": float(cell.amount),
                "confidence": cell.confidence.value if cell.confidence else None,
                "line_items": [
                    {
                        "amount": float(li.amount),
                        "confidence": li.confidence.value if li.confidence else None,
                        "coa_code": li.coa_code,
                        "label": li.label,
                        "raw_ref": li.raw_ref,
                    }
                    for li in cell.line_items
                ],
            }
        return cell

    result = {"week_ending_friday": ws.week_ending_friday.isoformat()}
    for field_name in ws.__dataclass_fields__:
        if field_name == "week_ending_friday":
            continue
        val = getattr(ws, field_name)
        if hasattr(val, "amount"):
            result[field_name] = cell_to_dict(val)
        elif isinstance(val, Decimal):
            result[field_name] = float(val)
        elif isinstance(val, DataConfidence):
            result[field_name] = val.value
        else:
            result[field_name] = val
    return result


def _matrix_to_json(matrix: WeeklyMatrix) -> str:
    return json.dumps(
        {
            "forecast_start_friday": matrix.forecast_start_friday.isoformat() if matrix.forecast_start_friday else None,
            "window_weeks": matrix.window_weeks,
            "weeks": [_serialize_week_slice(ws) for ws in matrix.weeks],
        },
        default=str,
    )


from app.outflow_buckets import outflow_buckets


def compute_analytics_from_dict(matrix_data: dict) -> dict:
    weeks = matrix_data.get("weeks", [])
    labels = []
    cash_trajectory = []
    inflows = []
    outflows = []
    net_cashflow = []
    
    rev_servpro = []
    rev_other = []
    rev_ar = []
    rev_amazon = []
    
    cogs_cogs = []
    cogs_freight = []
    cogs_duty = []
    out_streams: dict[str, list] = {}
    
    lowest_cash = None
    lowest_week = None
    peak_cash = None
    peak_week = None

    for w in weeks:
        dt_raw = w.get("week_ending_friday", "")
        dt_str = dt_raw[5:] if len(dt_raw) >= 10 else dt_raw
        labels.append(dt_str)
        
        c_end = float(w.get("ending_cash") or 0.0)
        cash_trajectory.append(round(c_end, 2))
        
        if lowest_cash is None or c_end < lowest_cash:
            lowest_cash = c_end
            lowest_week = dt_str
        if peak_cash is None or c_end > peak_cash:
            peak_cash = c_end
            peak_week = dt_str
            
        r_tot = float(w.get("total_revenue") or 0.0)
        inflows.append(round(r_tot, 2))
        
        def _get_val(field):
            v = w.get(field)
            if isinstance(v, dict):
                return float(v.get("amount") or 0.0)
            if isinstance(v, (int, float)):
                return float(v)
            return 0.0
            
        rev_servpro.append(round(_get_val("servpro_corporate"), 2))
        rev_other.append(round(_get_val("other_resellers"), 2))
        rev_ar.append(round(_get_val("ar_collection"), 2))
        rev_amazon.append(round(_get_val("amazon"), 2))
        
        c_tot = float(w.get("total_cogs") or 0.0)
        cogs_cogs.append(round(_get_val("cogs_standard"), 2))
        cogs_freight.append(round(_get_val("inbound_freight"), 2))
        cogs_duty.append(round(_get_val("inbound_duty"), 2))
        
        o_ops = float(w.get("total_operations") or 0.0)
        o_mkt = float(w.get("total_marketing") or 0.0)
        o_sell = float(w.get("total_selling") or 0.0)
        o_fin = float(w.get("total_finance_admin") or 0.0)
        o_it = float(w.get("total_it") or 0.0)
        o_non = float(w.get("total_non_operating") or 0.0)
        
        tot_out = c_tot + o_ops + o_mkt + o_sell + o_fin + o_it + o_non
        tot_out += _get_val("cc_payment_due") + _get_val("loan_repayments") - _get_val("cc_charges_deferred")
        outflows.append(round(tot_out, 2))
        for k, v in outflow_buckets(w, tot_out).items():
            out_streams.setdefault(k, []).append(v)
        net_cashflow.append(round(r_tot - tot_out, 2))

    ar_trajectory = []
    ap_trajectory = []
    for w in weeks:
        ar_amt = 0.0
        for ar_field in ("ar_collection", "amazon"):
            if isinstance(w.get(ar_field), dict):
                ar_amt += float(w[ar_field].get("amount", 0))
        if isinstance(w.get("servpro_corporate"), dict):
            for li in w["servpro_corporate"].get("line_items", []):
                ref = str(li.get("raw_ref", "")).lower()
                lbl = str(li.get("label", "")).lower()
                if "invoice" in ref or "inv-" in ref or "invoice" in lbl:
                    ar_amt += float(li.get("amount", 0))
        ar_trajectory.append(round(ar_amt, 2))

        ap_amt = 0.0
        for cat in ["cogs_standard", "inbound_freight", "inbound_duty", "nonop_irs_tax", "nonop_nj_tax", "loan_repayments"]:
            cell = w.get(cat)
            if isinstance(cell, dict):
                for li in cell.get("line_items", []):
                    ref = str(li.get("raw_ref", "")).lower()
                    lbl = str(li.get("label", "")).lower()
                    if "bill" in ref or "po" in ref or "bill" in lbl or "loan" in ref or "loan" in lbl or "customs" in ref:
                        ap_amt += float(li.get("amount", 0))
            elif isinstance(cell, (int, float)):
                ap_amt += float(cell)
        ap_trajectory.append(round(ap_amt, 2))

    eng = matrix_data.get("kpis") or {}
    first_open = float(weeks[0].get("opening_cash") or 0.0) if weeks else 0.0
    last_end = float(weeks[-1].get("ending_cash") or 0.0) if weeks else 0.0

    return {
        "labels": labels,
        "cash_trajectory": cash_trajectory,
        "inflows": inflows,
        "outflows": outflows,
        "net_cashflow": net_cashflow,
        "revenue_streams": {
            "SERVPRO": rev_servpro,
            "Other Resellers": rev_other,
            "Amazon": rev_amazon,
            "A/R Collection": rev_ar,
        },
        "outflow_streams": out_streams,
        "cogs_breakdown": {
            "COGS Standard": cogs_cogs,
            "Inbound Freight": cogs_freight,
            "Inbound Duty": cogs_duty,
        },
        "ar_ap": {
            "ar_trajectory": ar_trajectory,
            "ap_trajectory": ap_trajectory,
            "total_ar": round(sum(ar_trajectory), 2),
            "total_ap": round(sum(ap_trajectory), 2),
        },
        "kpis": {
            "opening_cash": round(first_open, 2),
            "ending_cash": round(last_end, 2),
            "lowest_cash": round(lowest_cash or 0.0, 2),
            "lowest_week": lowest_week or "N/A",
            "peak_cash": round(peak_cash or 0.0, 2),
            "peak_week": peak_week or "N/A",
            "total_inflow": round(sum(inflows), 2),
            "total_outflow": round(sum(outflows), 2),
            "total_ar": eng.get("open_ar", round(sum(ar_trajectory), 2)),
            "total_ap": eng.get("ap_total", round(sum(ap_trajectory), 2)),
            "net_change": round(last_end - first_open, 2),
            "avg_weekly_net": round(sum(net_cashflow) / len(net_cashflow), 2) if net_cashflow else 0.0,
            "as_of": weeks[0].get("week_ending_friday") if weeks else None,
        },
    }


def _execute_v10(run_id: str) -> Optional[dict]:
    """Runs created from a Zoho snapshot use the v10 engine (app/engine/v10_engine.py)."""
    from app.output.v10_adapter import forecast_for_run, forecast_to_matrix_dict
    f = forecast_for_run(run_id)
    if f is None:
        return None
    matrix_dict = forecast_to_matrix_dict(f)
    validation = {"passed": not f.exceptions,
                  "checks": [{"name": "engine_exceptions", "passed": not f.exceptions,
                              "message": f"{len(f.exceptions)} exception(s)", "details": f.exceptions}]}
    db.update_run_matrix(run_id, json.dumps(matrix_dict, default=str), json.dumps(validation, default=str),
                         json.dumps({"is_runnable": True, "messages": []}))
    return {"run_id": run_id, "status": "completed" if validation["passed"] else "completed_with_errors",
            "validation": validation, "weeks": len(f.fridays), "analytics": compute_analytics_from_dict(matrix_dict),
            "opening_cash": f.opening_cash, "zoho_cash": f.zoho_cash}


def _execute_run(run_id: str) -> dict:
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    v10 = _execute_v10(run_id)
    if v10 is not None:
        return v10
    
    run_date = safe_parse_date(run["run_date"])
    is_first_run = bool(run.get("is_first_run", 1))
    
    uploads = db.get_effective_uploads_for_run(run_id)
    all_records = []
    for upload in uploads:
        if upload["records_json"]:
            raw_list = json.loads(upload["records_json"])
            for r_dict in raw_list:
                from uuid import UUID
                from app.models.canonical import CanonicalRecord
                all_records.append(
                    CanonicalRecord(
                        record_id=UUID(r_dict["record_id"]),
                        source=r_dict["source"],
                        record_type=r_dict["record_type"],
                        ingested_at=safe_parse_datetime(r_dict["ingested_at"]),
                        as_of_date=safe_parse_date(r_dict["as_of_date"]),
                        confidence=DataConfidence(r_dict["confidence"]),
                        payload=r_dict["payload"],
                        raw_ref=r_dict.get("raw_ref"),
                    )
                )
                
    opening_cash_amount = Decimal(str(run.get("opening_cash_amount") or "0"))
    if opening_cash_amount == Decimal("0"):
        latest_oc = db.get_latest_opening_cash()
        if latest_oc and latest_oc.get("amount"):
            opening_cash_amount = Decimal(str(latest_oc["amount"]))
            db.set_run_opening_cash(run_id, opening_cash_amount, run_date)
        elif not is_first_run:
            derived = db.get_most_recent_ending_cash()
            if derived:
                opening_cash_amount = derived

    engine = TransformEngine(all_records, run_date)
    week_items = engine.run()
    
    cfg = load_assumptions()
    matrix = build_matrix(week_items, opening_cash_amount, run_date, window_weeks=cfg.rolling_window_weeks)
    
    gate = ValidationGate()
    vresult = gate.run(matrix)
    validation_data = {
        "passed": vresult.passed,
        "checks": [{"name": c.name, "passed": c.passed, "message": c.message, "details": c.details} for c in vresult.checks],
    }
    
    matrix_json = _matrix_to_json(matrix)
    preflight_data = {"is_runnable": True, "messages": []}
    db.update_run_matrix(run_id, matrix_json, json.dumps(validation_data, default=str), json.dumps(preflight_data, default=str))
    
    matrix_dict = json.loads(matrix_json)
    analytics = compute_analytics_from_dict(matrix_dict)
    
    return {
        "run_id": run_id,
        "status": "completed" if vresult.passed else "completed_with_errors",
        "validation": validation_data,
        "weeks": len(matrix.weeks),
        "analytics": analytics,
    }


@router.get("/runs")
def list_runs():
    """Runs, newest first, with the archive folder name when the Zoho data was archived."""
    from app.output.zoho_archive import find_run_folder
    out = []
    for r in db.list_runs():
        r = dict(r)
        try:
            folder = find_run_folder(r["run_id"])
        except Exception:
            folder = None
        r["archive_folder"] = str(folder) if folder else None
        out.append(r)
    return out


@router.get("/zoho/status")
def zoho_status():
    """Read-only connection check: can we log in to Zoho Books and see the configured organisation?"""
    try:
        from zoho.client import ZohoClient
        client = ZohoClient()
        orgs = client.get("organizations").get("organizations", []) or []
        org = next((o for o in orgs if str(o.get("organization_id")) == str(client.org_id)), None)
        if client.org_id and org is None:
            return {"ok": False, "message": f"Logged in, but organisation {client.org_id} is not visible to this login."}
        return {"ok": True, "org_id": client.org_id, "org_name": (org or {}).get("name", ""),
                "message": f"Zoho connected · org {client.org_id}"}
    except Exception as e:  # never raise: the UI only shows the reason
        msg = str(e).splitlines()[0][:200] if str(e) else e.__class__.__name__
        return {"ok": False, "message": f"Zoho not connected: {msg}"}


@router.get("/runs/{run_id}/opening-cash")
def get_run_opening_cash(run_id: str):
    """Opening cash of a run: Zoho cash by account, manual adjustments, and the bank override if one is set."""
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    from app.output.v10_adapter import forecast_for_run
    f = forecast_for_run(run_id)
    if f is None:
        raise HTTPException(status_code=404, detail="This run has no Zoho snapshot")
    ov = run.get("opening_cash_amount")
    return {"run_id": run_id, "run_date": f.run_date.isoformat(), "zoho_cash": f.zoho_cash,
            "accounts": [{"name": c["name"], "balance": c["balance"]} for c in f.cash_accounts],
            "manual_adjustments": f.manual_adjustments, "opening_cash": f.opening_cash,
            "override": (float(ov) if ov not in (None, "", "0") else None),
            "override_as_of": run.get("opening_cash_date")}


@router.post("/runs/{run_id}/open-archive")
def open_archive(run_id: str):
    """Open this run's Zoho data folder in Windows Explorer (the server runs on the user's own PC)."""
    import os
    import subprocess
    import sys
    from app.output.zoho_archive import find_run_folder
    folder = find_run_folder(run_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="No archive folder for this run yet - export it once to create one.")
    opened = False
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(folder))  # type: ignore[attr-defined]
            opened = True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
            opened = True
    except Exception:
        logger.exception("Could not open %s", folder)
    return {"folder": str(folder), "opened": opened}


@router.post("/runs")
def create_run(run_date: Optional[str] = None):
    if run_date:
        rd = safe_parse_date(run_date)
    else:
        rd = prev_friday(date.today())
    run_id = db.create_run(rd)
    result = _execute_run(run_id)
    return result


@router.get("/runs/{run_id}/matrix")
def get_matrix(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.get("matrix_json"):
        raise HTTPException(status_code=404, detail="Run has not been executed yet")
    try:  # rebuild from the saved Zoho snapshot so the matrix always mirrors the Excel Cash Flow Model
        from app.output.v10_adapter import forecast_for_run, forecast_to_matrix_dict
        f = forecast_for_run(run_id)
        if f is not None:
            return forecast_to_matrix_dict(f)
    except Exception:
        logger.exception("Matrix rebuild failed for run %s; returning the stored matrix", run_id)
    return json.loads(run["matrix_json"])


@router.get("/runs/{run_id}/actions")
def get_actions(run_id: str, limit: int = 200):
    """Overdue invoices to chase and bills to pay (due within 14 days), from the open items stored with the run."""
    from app.actions import build_actions, snapshot_date
    from app.output.v10_adapter import get_run_snapshot
    run = db.get_run(run_id)
    snap = get_run_snapshot(run_id) if run else None
    if snap is None:
        raise HTTPException(status_code=404, detail="This run has no open invoices and bills stored with it.")
    return {"run_id": run_id, **build_actions(snap, snapshot_date(snap, run), limit=limit)}


@router.get("/runs/{run_id}/working-capital")
def get_working_capital(run_id: str):
    """A/R and A/P aging, DSO / DPO and customer concentration. Open items come from the run's snapshot; the last-90-day
    sales and COGS are read live from Zoho (cached) and are null when Zoho could not be read."""
    from app.actions import snapshot_date
    from app.output.v10_adapter import get_run_snapshot
    from app.working_capital import build_working_capital
    from app.zoho_flows import get_flows
    run = db.get_run(run_id)
    snap = get_run_snapshot(run_id) if run else None
    if snap is None:
        raise HTTPException(status_code=404, detail="This run has no open invoices and bills stored with it.")
    as_of = snapshot_date(snap, run)  # the 90-day window ends the day the open items were read, so A/R and sales match
    return {"run_id": run_id, **build_working_capital(snap, as_of, get_flows(today=as_of))}


@router.post("/chat")
def chat(body: dict):
    """Ask the AI advisor. Body: {question, history?: [{role, content}]}. Streams one JSON event per line (NDJSON):
    tool / delta / done / error. Read-only tools over the latest run."""
    from fastapi.responses import StreamingResponse
    from app.chat.agent import events
    q = str(body.get("question") or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Ask a question.")

    def stream():
        try:
            for e in events(q[:2000], body.get("history")):
                yield json.dumps(e) + "\n"
        except Exception:
            logger.exception("Chat failed")
            yield json.dumps({"type": "error", "message": "The AI service did not answer. Try again."}) + "\n"
    return StreamingResponse(stream(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/chat/transcribe")
def chat_transcribe(audio: UploadFile = File(...)):
    """Mic button: audio recording in, text out (OpenAI Whisper). The text is then sent to /chat like a typed question."""
    from app.chat.voice import MAX_BYTES, transcribe
    data = audio.file.read(MAX_BYTES + 1)
    out = transcribe(data, audio.filename or "audio.webm", audio.content_type or "audio/webm")
    if out.get("error"):
        raise HTTPException(status_code=400 if "audio" in out["error"] or "hear" in out["error"] or "long" in out["error"] else 503, detail=out["error"])
    return out


@router.get("/runs/{run_id}/analytics")
def get_analytics(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.get("matrix_json"):
        raise HTTPException(status_code=404, detail="Run has not been executed yet")
    matrix_dict = json.loads(run["matrix_json"])
    return compute_analytics_from_dict(matrix_dict)


@router.post("/forecast/auto-run")
async def auto_run_batch(
    files: list[UploadFile] = File(...),
    opening_cash: Optional[float] = Form(None),
    as_of_date: Optional[str] = Form(None),
    run_date: Optional[str] = Form(None),
):
    target_date = safe_parse_date(run_date) if run_date else (safe_parse_date(as_of_date) if as_of_date else date(2026, 8, 14))
    run_id = db.create_run(target_date)
    
    if opening_cash is not None and opening_cash > 0:
        db.save_opening_cash(Decimal(str(opening_cash)), target_date, "auto_upload")
        db.set_run_opening_cash(run_id, Decimal(str(opening_cash)), target_date)
        
    detected_files = []
    for f in files:
        contents = await f.read()
        source_name = detect_source(contents, f.filename or "")
        if not source_name:
            continue
        try:
            records = parse_source(source_name, contents, f.filename or "", as_of=target_date)
            db.save_upload(run_id, source_name, f.filename or source_name, records)
            detected_files.append({"filename": f.filename, "source": source_name, "count": len(records)})
        except Exception as e:
            detected_files.append({"filename": f.filename, "source": source_name, "error": str(e)})

    exec_result = _execute_run(run_id)
    exec_result["detected_files"] = detected_files
    return exec_result


@router.post("/forecast/quick-demo")
def quick_demo_run():
    raise HTTPException(status_code=410, detail="Disabled: this built a 14-Aug run from the stale 'August 31' files "
                                                 "with a demo opening cash of $47,478.95. Use Sync Live from Zoho.")


def _quick_demo_run_disabled():
    folder = Path(__file__).parent.parent.parent / "August 31"
    target_date = date(2026, 8, 14)
    run_id = db.create_run(target_date)
    opening_cash = Decimal("47478.95")
    db.save_opening_cash(opening_cash, target_date, "demo_init")
    db.set_run_opening_cash(run_id, opening_cash, target_date)
    
    detected = []
    for path in sorted(folder.glob("*.*")):
        if path.name.startswith("."):
            continue
        ext = path.suffix.lower()
        if ext not in (".xlsx", ".xls", ".csv"):
            continue
        b = path.read_bytes()
        src = detect_source(b, path.name)
        if src:
            try:
                records = parse_source(src, b, path.name, as_of=target_date)
                db.save_upload(run_id, src, path.name, records)
                detected.append({"filename": path.name, "source": src, "count": len(records)})
            except Exception as e:
                detected.append({"filename": path.name, "source": src, "error": str(e)})
                
    result = _execute_run(run_id)
    result["detected_files"] = detected
    return result


@router.post("/forecast/sync-zoho-live")
def sync_zoho_live(run_date: Optional[str] = None):
    """Read-only Zoho pull -> snapshot saved with the run -> v10 engine."""
    from app.output.v10_adapter import SNAPSHOT_SOURCE
    from zoho.client import ZohoClient
    from zoho.snapshot import pull_snapshot

    target_date = prev_friday(safe_parse_date(run_date) if run_date else date.today())
    snap = pull_snapshot(ZohoClient(), target_date)
    return _run_from_snapshot(snap, target_date, SNAPSHOT_SOURCE, "Zoho Live API snapshot")


@router.post("/forecast/run-from-snapshot")
async def run_from_snapshot(file: UploadFile = File(...)):
    """Run the v10 engine on a snapshot JSON built offline by tools/snapshot_from_exports.py."""
    from app.output.v10_adapter import SNAPSHOT_SOURCE
    snap = json.loads(await file.read())
    target_date = prev_friday(safe_parse_date(snap["run_date"]))
    return _run_from_snapshot(snap, target_date, SNAPSHOT_SOURCE, file.filename or "snapshot.json")


def _run_from_snapshot(snap: dict, target_date: date, source: str, label: str) -> dict:
    run_id = db.create_run(target_date)
    db.save_snapshot(run_id, source, label, snap)
    result = _execute_run(run_id)
    db.save_opening_cash(Decimal(str(result["zoho_cash"])), target_date, "zoho_live_banking")
    result["synced_sources"] = [{"source": k, "label": k.replace("_", " ").title(), "count": len(v)}
                                for k, v in snap.items() if isinstance(v, list)]
    result["live_opening_cash"] = result["opening_cash"]
    from app.output.zoho_archive import archive_snapshot
    folder = archive_snapshot(run_id, snap, target_date, source, label)
    result["archive_folder"] = str(folder) if folder else None
    return result


@router.post("/opening-cash")
def set_opening_cash(req: dict):
    amount = Decimal(str(req.get("amount", 0)))
    as_of = safe_parse_date(req.get("as_of_date", str(date.today())))
    entered_by = req.get("entered_by", "user")
    db.save_opening_cash(amount, as_of, entered_by)
    target_run_id = req.get("run_id") or db.get_latest_run_id()
    if target_run_id:
        db.set_run_opening_cash(target_run_id, amount, as_of)
        run = db.get_run(target_run_id)
        if run and run.get("matrix_json"):
            _execute_run(target_run_id)
    return {"message": "Opening Cash recorded.", "amount": str(amount), "as_of_date": as_of.isoformat(), "run_id": target_run_id}


@router.post("/runs/{run_id}/execute")
def execute_run(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _execute_run(run_id)


@router.get("/runs/{run_id}/export/xlsx")
def export_xlsx(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.get("matrix_json"):
        _execute_run(run_id)
        run = db.get_run(run_id)
    if not run or not run.get("matrix_json"):
        raise HTTPException(status_code=404, detail="Run matrix not found")

    from app.output.v10_adapter import forecast_for_run
    from app.output.v10_exporter import export_forecast
    f = forecast_for_run(run_id)
    if f is not None:
        from app.output.v10_adapter import get_run_snapshot
        from app.output.zoho_archive import save_export
        content = export_forecast(f)
        saved = save_export(run_id, f.run_date, content, get_run_snapshot(run_id))
        headers = {"Content-Disposition": f"attachment; filename=Cash_Flow_Forecast_{f.run_date:%Y-%m-%d}.xlsx"}
        if saved:
            headers["X-Archive-Folder"] = str(saved.parent).encode("ascii", "replace").decode()
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )

    matrix_dict = json.loads(run["matrix_json"])
    run_date = safe_parse_date(matrix_dict.get("forecast_start_friday") or run["run_date"])
    opening_cash = Decimal(str(run.get("opening_cash_amount") or "0"))

    from app.engine.matrix_builder import build_matrix
    from app.models.matrix import WeeklyMatrix
    from app.config.loader import load_assumptions

    cfg = load_assumptions()
    all_records = []
    for upload in db.get_effective_uploads_for_run(run_id):
        if upload["records_json"]:
            raw_list = json.loads(upload["records_json"])
            for r_dict in raw_list:
                from uuid import UUID
                from app.models.canonical import CanonicalRecord
                all_records.append(
                    CanonicalRecord(
                        record_id=UUID(r_dict["record_id"]),
                        source=r_dict["source"],
                        record_type=r_dict["record_type"],
                        ingested_at=safe_parse_datetime(r_dict["ingested_at"]),
                        as_of_date=safe_parse_date(r_dict["as_of_date"]),
                        confidence=DataConfidence(r_dict["confidence"]),
                        payload=r_dict["payload"],
                        raw_ref=r_dict.get("raw_ref"),
                    )
                )

    from app.engine.transform_engine import TransformEngine
    engine = TransformEngine(all_records, run_date)
    week_items = engine.run()
    matrix = build_matrix(week_items, opening_cash, run_date, window_weeks=cfg.rolling_window_weeks)

    xlsx_bytes = XLSXExporter(matrix).export()
    filename = f"Cash_Flow_Forecast_{run_date.strftime('%Y-%m-%d')}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _loans_file():
    return CONFIG_DIR / "loans.json"


def _loans_payload() -> dict:
    from app.loans import summarize
    try:
        cfg = json.loads(_loans_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        cfg = {"facilities": []}
    try:
        assumptions = json.loads((CONFIG_DIR / "assumptions.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        assumptions = {}
    return summarize(cfg, assumptions)


@router.get("/loans")
def get_loans():
    """Loans and credit lines entered by hand, with headroom and what the cash forecast already carries. Display only."""
    return _loans_payload()


@router.put("/loans")
def put_loans(body: dict):
    from app.loans import validate
    try:
        clean = validate(body)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    tmp = _loans_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    tmp.replace(_loans_file())
    return _loans_payload()


@router.get("/config/{table}")
def get_config(table: str):
    allowed = {"corporate_accounts", "freight_duty_vendors", "cc_category_coa_map", "assumptions", "coa_routing"}
    if table not in allowed:
        raise HTTPException(status_code=404, detail=f"Config table '{table}' not found.")
    config_file = CONFIG_DIR / f"{table}.json"
    if not config_file.exists():
        raise HTTPException(status_code=404, detail=f"Config file {table}.json not found")
    with open(config_file, encoding="utf-8") as f:
        return json.load(f)


@router.put("/config/{table}")
def update_config(table: str, body: dict):
    allowed = {"corporate_accounts", "freight_duty_vendors", "cc_category_coa_map", "assumptions"}
    if table not in allowed:
        raise HTTPException(status_code=403, detail=f"Config table '{table}' is read-only or not found.")
    config_file = CONFIG_DIR / f"{table}.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2)
    invalidate_cache()
    return {"message": f"Config '{table}' updated and cache invalidated."}
