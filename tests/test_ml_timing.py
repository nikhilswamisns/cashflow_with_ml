"""ML timing layer: synthetic data only (no Zoho files needed)."""
import copy
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.history import norm
from app.ml.timing_model import TimingModel

RULES = Path(__file__).resolve().parent.parent / "app" / "config" / "forecast_rules.json"


def synthetic(n=400, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        party = "fast payer" if i % 2 else "slow payer"
        known = pd.Timestamp("2024-01-01") + pd.Timedelta(days=int(i * 2))
        due = known + pd.Timedelta(days=30)
        y = int(rng.normal(-10 if party == "fast payer" else 15, 2))
        rows.append(dict(key=f"I{i}", party=party, amount=1000.0, base_date=due, known_date=known,
                         paid_on=due + pd.Timedelta(days=y), terms=30, y=y, kind="inv"))
    return pd.DataFrame(rows)


def test_model_learns_party_specific_delay():
    tab = synthetic()
    m = TimingModel.fit(tab, "inv")
    assert m is not None
    base = pd.Timestamp("2026-01-30")
    q = m.predict(pd.DataFrame([
        dict(party="fast payer", base_date=base, known_date=base - pd.Timedelta(days=30), amount=1000.0, terms=30),
        dict(party="slow payer", base_date=base, known_date=base - pd.Timedelta(days=30), amount=1000.0, terms=30)]))
    assert q[0, 1] < -6 and q[1, 1] > 10           # P50: fast pays early, slow pays late
    assert (q[:, 0] <= q[:, 1]).all() and (q[:, 1] <= q[:, 2]).all()   # quantiles never cross


def test_too_little_history_gives_no_model():
    assert TimingModel.fit(synthetic(50), "inv") is None


def test_norm():
    assert norm("  SERVPRO -   Corporate ") == "servpro - corporate"


def test_engine_unchanged_when_ml_off():
    from app.engine.v10_engine import ROW_ENDING, V10Engine
    snap_file = Path(__file__).resolve().parent.parent / "data" / "snapshot_2026-09-25_from_exports.json"
    if not snap_file.exists():
        return
    snap = json.loads(snap_file.read_text(encoding="utf-8"))
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    assert not rules.get("ml", {}).get("enabled", False)
    f = V10Engine(snap, rules=copy.deepcopy(rules)).run()
    assert all(r.ml is None for r in f.revenue + f.cogs)


def test_engine_falls_back_when_model_missing(tmp_path):
    from app.engine.v10_engine import V10Engine
    snap_file = Path(__file__).resolve().parent.parent / "data" / "snapshot_2026-09-25_from_exports.json"
    if not snap_file.exists():
        return
    snap = json.loads(snap_file.read_text(encoding="utf-8"))
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    rules.setdefault("ml", {}).update(enabled=True, model_path=str(tmp_path / "nope.joblib"))
    f = V10Engine(snap, rules=rules).run()
    assert any("ML timing is switched on" in e for e in f.exceptions)
    assert all(r.ml is None for r in f.revenue)


def test_all_empty_feature_column_is_ignored():
    """Sales orders have no 'terms'; a column with no variation must not crash training (newer scikit-learn)."""
    tab = synthetic()
    tab["terms"] = np.nan
    m = TimingModel.fit(tab, "so")
    assert m is not None and "terms" not in m.feats
    base = pd.Timestamp("2026-01-30")
    q = m.predict(pd.DataFrame([dict(party="fast payer", base_date=base, known_date=base, amount=1000.0, terms=np.nan)]))
    assert q.shape == (1, 3)
