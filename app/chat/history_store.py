"""The Zoho history workbook (ml_data/Zoho_history_*.xlsx) loaded once and reloaded only when the file changes."""
from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd

from app.ml.history import _dt, load_history, norm
from app.ml.train import latest_history_file

_lock = threading.Lock()
_cache: dict = {"key": None, "data": None}


def load(path: Path | None = None) -> dict | None:
    """{'invoices', 'payments', 'source', 'last_date'} or None when no workbook exists."""
    path = path or latest_history_file()
    if path is None or not Path(path).exists():
        return None
    key = (str(path), Path(path).stat().st_mtime)
    with _lock:
        if _cache["key"] != key:
            h = load_history(path)
            inv, pay = h["invoices"].copy(), h["customer payments"].copy()
            inv["name"] = inv["customer_name"].map(norm)
            pay["name"] = pay["customer_name"].map(norm)
            pay["pdate"] = _dt(pay["date"])
            inv["due"] = _dt(inv["due_date"])
            inv["idate"] = _dt(inv["date"])
            _cache.update(key=key, data={"invoices": inv, "payments": pay, "source": Path(path).name,
                                         "last_date": pay["pdate"].max().date().isoformat()})
    return _cache["data"]


def display_names(df: pd.DataFrame) -> dict[str, str]:
    """Normalised name -> the spelling used most often in Zoho."""
    return df.groupby("name")["customer_name"].agg(lambda s: s.value_counts().index[0]).to_dict()
