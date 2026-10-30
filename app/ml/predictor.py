"""What the engine talks to.  Loads the saved models once and answers three questions:

    ml.invoice(inv, due, amount)         -> expected cash-in date for an open customer invoice
    ml.sales_order(so, ship, amount)     -> expected cash-in date for an open sales order
    ml.bill(bill, due, amount)           -> expected payment date for an open vendor bill

Each returns None (= "use the existing rule") when the model is missing, the customer/vendor has too little
history, or the model moves the date by an implausible amount.  Otherwise a dict:
    {"p10": date, "p50": date, "p90": date, "shift_days": int, "party_n": int}
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import joblib
import pandas as pd

from app.ml import MODEL_FILE
from app.ml.history import norm


class MLTiming:
    def __init__(self, bundle: dict, cfg: dict):
        self.models = bundle["models"]
        self.meta = bundle.get("meta", {})
        self.cfg = cfg or {}
        use = self.cfg.get("use_for", {})
        self.use = {"inv": use.get("invoices", True), "so": use.get("sales_orders", True), "bill": use.get("bills", True)}
        self.min_n = int(self.cfg.get("min_party_history", 3))
        self.max_shift = int(self.cfg.get("max_shift_days", 75))
        self._cache: dict = {}

    @classmethod
    def load(cls, cfg: dict) -> "MLTiming":
        from pathlib import Path
        p = Path(cfg.get("model_path") or MODEL_FILE)
        if not p.is_absolute():
            from app.ml import ROOT
            p = ROOT / p
        if not p.exists():
            raise FileNotFoundError(f"ML model file not found: {p}. Train it first (python tools/train_ml.py).")
        return cls(joblib.load(p), cfg)

    # ------------------------------------------------------------------
    def _predict(self, kind: str, party: str, base: date, known: Optional[date], amount: float,
                 terms: Optional[float], rule_date: date) -> Optional[dict]:
        m = self.models.get(kind)
        if m is None or not self.use.get(kind, True):
            return None
        party = norm(party)
        n = m.stats.n(party)
        if n < self.min_n:
            return None
        key = (kind, party, base, round(float(amount), 0), terms)
        if key not in self._cache:
            row = pd.DataFrame([{"party": party, "base_date": pd.Timestamp(base), "known_date": pd.Timestamp(known or base),
                                 "amount": amount, "terms": terms if terms is not None else float("nan")}])
            self._cache[key] = m.predict(row)[0]
        q10, q50, q90 = (int(round(v)) for v in self._cache[key])
        p50 = base + timedelta(days=q50)
        if abs((p50 - rule_date).days) > self.max_shift:
            return None                                                     # implausible: keep the rule
        return {"p10": base + timedelta(days=q10), "p50": p50, "p90": base + timedelta(days=q90),
                "shift_days": (p50 - rule_date).days, "party_n": n}

    @staticmethod
    def _d(v) -> Optional[date]:
        if v in (None, "", "None"):
            return None
        return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])

    def invoice(self, inv: dict, due: date, amount: float, rule_date: date) -> Optional[dict]:
        issued = self._d(inv.get("date"))
        terms = (due - issued).days if issued else None
        return self._predict("inv", inv.get("customer"), due, issued, amount, terms, rule_date)

    def sales_order(self, so: dict, ship: date, amount: float, rule_date: date) -> Optional[dict]:
        return self._predict("so", so.get("customer"), ship, self._d(so.get("date")), amount, None, rule_date)

    def bill(self, b: dict, due: date, amount: float, rule_date: date) -> Optional[dict]:
        issued = self._d(b.get("date"))
        terms = (due - issued).days if issued else None
        return self._predict("bill", b.get("vendor"), due, issued, amount, terms, rule_date)
