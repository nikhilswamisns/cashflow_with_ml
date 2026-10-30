"""Train and save the three timing models from the Zoho history workbook."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

import joblib

from app.ml import CARD_FILE, HISTORY_DIR, MODEL_DIR, MODEL_FILE
from app.ml.history import build_tables
from app.ml.timing_model import TimingModel

LABELS = {"inv": "Customer invoices (days after due date)", "so": "Sales orders (days after ship date)",
          "bill": "Vendor bills (days after due date)"}


def latest_history_file() -> Optional[Path]:
    for folder in (HISTORY_DIR, HISTORY_DIR.parent / "exports"):
        files = sorted(folder.glob("Zoho_history_*.xlsx"), key=lambda p: p.stat().st_mtime) if folder.exists() else []
        if files:
            return files[-1]
    return None


def train(history_path: Union[str, Path, None] = None, out_file: Path = MODEL_FILE) -> dict:
    path = Path(history_path) if history_path else latest_history_file()
    if path is None or not path.exists():
        raise FileNotFoundError("No Zoho history workbook found. Run  python tools/export_history.py --days 1825  "
                                "and copy the file into the ml_data folder.")
    tables = build_tables(path)
    models, card_models = {}, {}
    for kind, tab in tables.items():
        m = TimingModel.fit(tab, kind)
        if m is None:
            card_models[kind] = {"label": LABELS[kind], "trained": False,
                                 "reason": f"only {0 if tab is None else len(tab)} finished documents (need 150)"}
            continue
        models[kind] = m
        recent = tab[tab["known_date"] >= tab["known_date"].max() - __import__("pandas").Timedelta(days=365)]
        card_models[kind] = {"label": LABELS[kind], "trained": True, "rows": int(len(tab)), "parties": int(tab["party"].nunique()),
                             "trained_through": m.trained_through,
                             "median_days_last_12m": float(recent["y"].median()) if len(recent) else None}
    meta = {"trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "history_file": path.name,
            "models": card_models}
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"models": models, "meta": meta}, out_file)
    CARD_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def status() -> dict:
    if not MODEL_FILE.exists():
        return {"trained": False, "message": "No model yet. Train it from the 5-year Zoho history."}
    meta = json.loads(CARD_FILE.read_text(encoding="utf-8")) if CARD_FILE.exists() else {}
    return {"trained": True, **meta}
