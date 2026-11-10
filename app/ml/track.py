"""Forecast tracking: the near-term predictions (rules and ML) of each run, kept in ONE small file, so they can be
compared with the cash that really arrived.

Rule (stated on the dashboard): a week's prediction is the one made by the most recent run created on or before that
week's Monday. A run made during the week, or after it, never replaces it, so the stored number is "the forecast as it
stood when the week began" and cannot know what happened inside the week. The file is written when a run is made, so a
later model retrain cannot change a past prediction. Only the first HORIZON_WEEKS weeks of each run are kept.
"""
import json
import logging
import os
import threading
from datetime import date, datetime, timedelta

from app.ml import MODEL_DIR, ROOT

log = logging.getLogger(__name__)
TRACK_FILE = ROOT / "data" / "forecast_track.json"
HORIZON_WEEKS = 2
_lock = threading.Lock()


def week_start_monday(friday: date) -> date:
    return friday - timedelta(days=4)


def load() -> dict:
    try:
        return json.loads(TRACK_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"horizon_weeks": HORIZON_WEEKS, "weeks": {}}


def _save(data: dict) -> None:
    TRACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TRACK_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, TRACK_FILE)


def _model_trained_at() -> str | None:
    try:
        return json.loads((MODEL_DIR / "model_card.json").read_text(encoding="utf-8")).get("trained_at")
    except (FileNotFoundError, ValueError):
        return None


def record(run_id: str, run_created: str, compare: dict) -> list[str]:
    """Store this run's first weeks. Returns the week-ending dates that were written."""
    created = datetime.fromisoformat(run_created)
    weeks = compare["weeks"][:HORIZON_WEEKS]
    rules, ml = compare["ending_cash_rules"], compare.get("ending_cash_ml") or []
    p10, p90 = compare.get("bands", {}).get("p10", []), compare.get("bands", {}).get("p90", [])
    written = []
    with _lock:
        data = load()
        data["horizon_weeks"] = HORIZON_WEEKS
        for i, w in enumerate(weeks):
            if created.date() > week_start_monday(date.fromisoformat(w)):
                continue  # made inside or after that week: not a prediction of it
            old = data["weeks"].get(w)
            if old and old["run_created"] > created.isoformat():
                continue  # an older run must never replace a newer eligible one
            data["weeks"][w] = {
                "rules": round(float(rules[i]), 2),
                "ml": round(float(ml[i]), 2) if i < len(ml) else None,
                "p10": round(float(p10[i]), 2) if i < len(p10) else None,
                "p90": round(float(p90[i]), 2) if i < len(p90) else None,
                "run_id": run_id, "run_created": created.isoformat(), "model_trained_at": _model_trained_at(),
            }
            written.append(w)
        if written:
            _save(data)
    return written


def record_run(run_id: str) -> list[str]:
    """Compute the run's rules/ML lines (cached) and store its first weeks."""
    from app import db
    from app.ml.api import ml_compare
    run = db.get_run(run_id)
    if not run:
        return []
    return record(run_id, run["created_at"], ml_compare(run_id))


def record_in_background(run_id: str) -> None:
    """Called after a run is created. Never raises and never delays the response."""
    def work():
        try:
            written = record_run(run_id)
            log.info("forecast_track: run %s wrote %s", run_id[:8], written)
        except Exception as e:  # noqa: BLE001 - tracking must never break a sync
            log.warning("forecast_track: run %s not recorded: %s", run_id[:8], e)
    threading.Thread(target=work, daemon=True, name="forecast-track").start()
