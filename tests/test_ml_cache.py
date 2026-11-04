"""The ML result cache must be fast on a repeat but never serve a stale result."""
import os
import threading
import time

import pytest

from app.ml import predictor
from app.ml.result_cache import ResultCache, fingerprint


def test_result_cache_computes_once_and_evicts_oldest():
    c, calls = ResultCache(size=2), []
    f = lambda v: (lambda: calls.append(v) or v)
    assert [c.get_or_compute(k, f(k)) for k in ("a", "a", "b", "c", "a")] == ["a", "a", "b", "c", "a"]
    assert calls == ["a", "b", "c", "a"]          # "a" was evicted by "c" and recomputed


def test_result_cache_stores_nothing_when_compute_fails():
    c = ResultCache()
    with pytest.raises(ValueError):
        c.get_or_compute("k", lambda: (_ for _ in ()).throw(ValueError("boom")))
    assert c.get_or_compute("k", lambda: "ok") == "ok"


def test_identical_concurrent_requests_compute_once():
    c, calls = ResultCache(), []

    def slow():
        calls.append(1)
        time.sleep(0.2)
        return "v"
    ts = [threading.Thread(target=lambda: c.get_or_compute("k", slow)) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(calls) == 1


def test_fingerprint_changes_with_data_and_with_each_file(tmp_path):
    f = tmp_path / "rules.json"
    f.write_text("{}")
    base = fingerprint({"a": 1}, files=[f])
    assert fingerprint({"a": 1}, files=[f]) == base
    assert fingerprint({"a": 2}, files=[f]) != base                       # run data changed
    f.write_text('{"ml": {"enabled": true}}')
    os.utime(f, ns=(1, 2_000_000_000))
    assert fingerprint({"a": 1}, files=[f]) != base                       # rules/model file changed
    f.unlink()
    assert fingerprint({"a": 1}, files=[f]) != base                       # file removed


def test_model_bundle_loaded_once_and_reloaded_after_retrain(tmp_path, monkeypatch):
    import joblib
    p = tmp_path / "m.joblib"
    joblib.dump({"v": 1}, p)
    loads = []
    real = joblib.load
    monkeypatch.setattr(predictor.joblib, "load", lambda path: loads.append(1) or real(path))
    predictor._BUNDLES.clear()
    assert predictor._load_bundle(p) == {"v": 1} and predictor._load_bundle(p) == {"v": 1}
    assert len(loads) == 1
    joblib.dump({"v": 2, "pad": "x" * 50}, p)                              # retrain: new size/mtime
    assert predictor._load_bundle(p)["v"] == 2 and len(loads) == 2
