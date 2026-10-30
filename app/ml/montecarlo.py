"""Probability bands around the forecast: "what could ending cash look like if payments are earlier/later than P50?"

Only the ML-timed items (customer invoices, sales orders, optionally bills) are random; everything else in the
forecast (payroll, card cycle, run-rate expenses) stays at the engine's deterministic value.  So the band measures
*collection / payment timing risk*, not total forecast risk.

Method: for every ML-timed line, draw a payment date from its (P10, P50, P90) distribution, drop the line into the
simulated week, and recompute cumulative ending cash.  Lines of the same customer share a common random shock
(party_correlation), because a customer that pays late tends to pay *all* its invoices late.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from scipy.special import ndtr

from app.engine.v10_engine import ROW_ENDING, fri_on_or_after, fri_on_or_before


def cash_bands(f, simulations: int = 2000, seed: int = 42, party_correlation: float = 0.5) -> dict:
    n = len(f.fridays)
    idx = {w: i for i, w in enumerate(f.fridays)}
    lines = [(r, +1) for r in f.revenue if r.ml] + [(r, -1) for r in f.cogs if r.ml]
    base = np.array(f.values[ROW_ENDING], dtype=float)
    if not lines:
        return {"weeks": [w.isoformat() for w in f.fridays], "deterministic": base.round(2).tolist(),
                "p10": base.round(2).tolist(), "p50": base.round(2).tolist(), "p90": base.round(2).tolist(),
                "ml_lines": 0, "note": "No ML-timed lines in this forecast (is ml.enabled true and the model trained?)."}
    rng = np.random.default_rng(seed)
    parties = {}
    z_party = {}
    for r, _ in lines:
        parties.setdefault(r.party, len(parties))
    zp = rng.standard_normal((simulations, len(parties)))
    rho = float(party_correlation)
    delta = np.zeros((simulations, n))
    for r, sign in lines:
        info = r.ml
        days = np.array([(info["p10"] - info["p50"]).days, 0, (info["p90"] - info["p50"]).days], dtype=float)
        spread = max(days[2] - days[0], 4.0)
        knots_u = np.array([0.0, 0.1, 0.5, 0.9, 1.0])
        knots_d = np.array([days[0] - 0.5 * spread, days[0], 0.0, days[2], days[2] + 0.5 * spread])
        knots_d = np.maximum.accumulate(knots_d)                      # keep it monotone
        u = ndtr(rho * zp[:, parties[r.party]] + np.sqrt(1 - rho ** 2) * rng.standard_normal(simulations))
        offs = np.interp(u, knots_u, knots_d)
        week_fn = fri_on_or_after if sign > 0 else fri_on_or_before
        planned = idx.get(r.week, n)                                  # n = beyond the window
        sim_idx = np.empty(simulations, dtype=int)
        cache: dict[int, int] = {}
        for k, o in enumerate(np.round(offs).astype(int)):
            if o not in cache:
                w = max(week_fn(info["p50"] + timedelta(days=int(o))), f.run_date)
                cache[o] = idx.get(w, n if w > f.fridays[-1] else 0)
            sim_idx[k] = cache[o]
        amt = sign * r.amount
        for target, mult in ((sim_idx, +1.0), (np.full(simulations, planned), -1.0)):
            mask = target < n
            rows_i = np.nonzero(mask)[0]
            delta[rows_i, target[mask]] += mult * amt
    sim_end = base[None, :] + np.cumsum(delta, axis=1)
    q = np.percentile(sim_end, [10, 50, 90], axis=0)
    return {"weeks": [w.isoformat() for w in f.fridays], "deterministic": base.round(2).tolist(),
            "p10": q[0].round(2).tolist(), "p50": q[1].round(2).tolist(), "p90": q[2].round(2).tolist(),
            "ml_lines": len(lines), "simulations": simulations,
            "note": "Band = timing risk of the ML-timed invoices / orders / bills only. Other rows are deterministic."}
