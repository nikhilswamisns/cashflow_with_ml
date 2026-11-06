"""Deployment health check: which files and settings this server needs, and which of them are missing.

`required` items break the main dashboard when missing; the rest only switch off one feature (ML panels, Excel export).
The same list is printed at startup and served at GET /api/health, so a missing file is seen at once instead of as a blank chart.
"""
from __future__ import annotations

from pathlib import Path

from app import auth, db
from app.ml import CARD_FILE, MODEL_FILE, ROOT


def _file(name: str, path: Path, fix: str, required: bool = False) -> dict:
    ok = path.is_file()
    return {"name": name, "ok": ok, "required": required,
            "detail": str(path.relative_to(ROOT)) if ok else f"missing: {path.relative_to(ROOT)}", "fix": "" if ok else fix}


def _run_count() -> int | None:
    try:
        return len(db.list_runs())
    except Exception:
        return None


def run_checks(login_disabled: bool = False) -> dict:
    runs = _run_count()
    out = ROOT / "ml_work" / "outputs"
    checks = [
        {"name": "Database", "ok": runs is not None, "required": True,
         "detail": f"{db.DB_PATH.name} opened" if runs is not None else f"cannot open {db.DB_PATH}",
         "fix": "" if runs is not None else "Copy data/cashflow.db from the project owner."},
        {"name": "Forecast runs", "ok": bool(runs), "required": True,
         "detail": f"{runs} run(s) in the database" if runs else "no runs: the charts have nothing to show",
         "fix": "" if runs else "Copy data/cashflow.db, or click Sync Zoho once (needs the Zoho keys in .env)."},
        _file("Forecast rules", ROOT / "app" / "config" / "forecast_rules.json", "Restore app/config/forecast_rules.json from Git.", True),
        _file("Assumptions", ROOT / "app" / "config" / "assumptions.json", "Copy app/config/assumptions.json from the project owner (not in Git).", True),
        {"name": "Login user", "ok": login_disabled or bool(auth.load_users()), "required": True,
         "detail": "login disabled for this computer" if login_disabled else "a user exists",
         "fix": "Run: python tools/add_user.py"},
        _file("Excel template", ROOT / "app" / "templates" / "v10_template.xlsx", "Copy app/templates/v10_template.xlsx (not in Git). Excel export needs it."),
        _file("ML timing model", MODEL_FILE, "Copy data/ml_models/timing_models.joblib from the project owner (not in Git)."),
        _file("ML model card", CARD_FILE, "Copy data/ml_models/model_card.json from the project owner (not in Git)."),
        _file("Revenue history table", out / "monthly_table.csv", "Run ml_work/02_build_monthly_table.py (outputs are not in Git)."),
        _file("Revenue forecast", out / "05_forecast_new_range.csv", "Run ml_work/05_calibrate_range.py (outputs are not in Git)."),
    ]
    missing_required = [c["name"] for c in checks if c["required"] and not c["ok"]]
    missing_optional = [c["name"] for c in checks if not c["required"] and not c["ok"]]
    status = "broken" if missing_required else ("degraded" if missing_optional else "ok")
    return {"status": status, "missing_required": missing_required, "missing_optional": missing_optional, "checks": checks}


def print_startup_report(login_disabled: bool = False) -> None:
    h = run_checks(login_disabled)
    if h["status"] == "ok":
        return
    print(f"\n  HEALTH: {h['status'].upper()}", flush=True)
    for c in h["checks"]:
        if not c["ok"]:
            print(f"    - {'REQUIRED' if c['required'] else 'optional'}  {c['name']}: {c['detail']}. {c['fix']}", flush=True)
    print("", flush=True)
