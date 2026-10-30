# Machine-Learning Layer — Guide

> Adds ML to the existing Cash Flow Forecasting Engine **without replacing it**. The v10 engine stays the source of
> truth; ML only replaces three *timing guesses* and adds probability bands. Switch it off and the engine is identical to before.

---

## 1. What ML does here (and what it does not)

| Question the engine asks today | Fixed rule today | With ML |
|---|---|---|
| When does a customer **invoice** get paid? | Friday on/after the due date | Predicted from that customer's own payment history (P10 / P50 / P90) |
| When does a **sales order** turn into cash? | Ship date + 45 (SERVPRO) / 30 (Amazon) / 21 (others) days | Predicted ship-to-cash lag per customer |
| When do we pay a vendor **bill**? | Friday on/before the due date | Available, **off by default** (backtest: rule was better) |
| How uncertain is ending cash? | Single line | **P10 / P50 / P90 band** by Monte Carlo |

Not touched: payroll, card cycle, run-rate expenses, taxes, interest, manual entries, opening cash.
The band therefore measures **collection / payment timing risk**, not total forecast risk.

Model: gradient-boosted quantile regression (scikit-learn `HistGradientBoostingRegressor`), trained on the 5-year
Zoho history. Deterministic (fixed seed) → same history gives the same forecast, so numbers stay auditable. Each ML-timed
line in Revenue Detail shows its reason in the *basis* column, e.g.
`ML: expected 2026-09-30 (P10 2026-09-25, P90 2026-10-13; +4 d vs rule) from this customer's payment history, 7 past payments`.

---

## 2. Where it plugs into the existing code

```
tools/export_history.py  ──►  ml_data/Zoho_history_*.xlsx          (existing tool, 5-year read-only pull)
                                   │
tools/train_ml.py  /  POST /api/ml/train
                                   ▼
app/ml/history.py        builds finished-payment tables (invoice / sales order / bill)
app/ml/timing_model.py   quantile model per table
app/ml/train.py          saves  data/ml_models/timing_models.joblib  + model_card.json
                                   │
app/engine/v10_engine.py ──► 3 small hooks:  ml_receipt_invoice / ml_receipt_so / ml_payment_bill
                             (only the week a line lands in changes; amounts never change)
app/ml/predictor.py      answers the engine's 3 questions, or returns None → the old rule is used
app/ml/montecarlo.py     P10/P50/P90 ending-cash band
app/ml/api.py            /api/ml/status | train | backtest | runs/{id}/compare
```

Safety nets: customer/vendor with fewer than 3 past payments → old rule; ML moves a date by more than 75 days → old rule;
overdue items stay in week 1; model file missing → old rule **plus an open-item warning** (the forecast never fails because of ML).

---

## 3. Installing it

1. Stop the server. Unzip `ml_integration.zip` **over** the project folder (new files + `v10_engine.py`, `main.py`, `requirements.txt`).
   If you changed those two files yourself, apply `patches/*.diff` instead (`patch -p0` or by hand — ~30 lines).
2. Add the `"ml": {...}` block from `forecast_rules.ml_block.json` to `app\config\forecast_rules.json` (top level, e.g. after `"bills"`).
   It is **not** shipped as a file because updates overwrite local rule edits.
3. Install packages (venv active): `pip install -r requirements.txt` (adds scikit-learn, scipy, numpy, joblib; `start.bat` does it too).
4. Start `start.bat`, hard refresh (Ctrl+F5).

## 4. First training (≈15 seconds)

```cmd
python tools\export_history.py --days 1825          :: 5 years, read-only Zoho pull (or use your existing workbook)
copy exports\Zoho_history_*.xlsx ml_data\            :: create the ml_data folder if needed
python tools\train_ml.py --backtest                  :: trains + prints ML-vs-rules test results
```
Same thing from the API: `POST /api/ml/train`, `POST /api/ml/backtest` (docs at `http://localhost:8000/docs`, section **ml**).

## 5. Using it


## 5b. Excel only - no dashboard, no Zoho API

```cmd
python tools\make_forecast.py --exports "C:\path\to\zoho_exports_folder" --date 2026-10-09 --ml both --bands
python tools\make_forecast.py --snapshot data\snapshot_2026-09-25_from_exports.json --ml both --bands
```
Writes to the `output` folder: `Cash_Flow_Forecast_<date>.xlsx` (fixed rules - identical to the old file),
`Cash_Flow_Forecast_<date>_ML.xlsx` (same template and layout, ML-timed weeks) and, with `--bands`, `..._ML_range.xlsx`
(P10/P50/P90 ending cash + the lines ML moved). `--ml on|off|both` chooses which. Needs the model trained once (`python tools\train_ml.py`).

**In the dashboard:** sidebar → **🤖 ML Forecast**. There you can see the model status, **Train model**, **Run backtest**, switch ML **ON/OFF** (and per type), and **Compare current run: rules vs ML** (chart with the P10–P90 band and the table of lines whose week moved). The same things are available as API calls below.

**Compare first (recommended before switching on).** For any run:
`GET /api/ml/runs/<run_id>/compare` returns ending cash with rules, with ML, the P10/P50/P90 band per week, and the
100 lines whose week moved most (amount × days). Review those lines with finance.

**Switch on** — in `forecast_rules.json` set `"enabled": true` (per-type switches under `use_for`). Restart `start.bat`.
Every new run, the dashboard and the Excel export then use ML-timed weeks; Revenue Detail shows the ML reason per line.
**Switch off** — `"enabled": false`.

**Weekly routine** (add after the existing weekly sync, section 7 of SETUP_GUIDE):
`export_history` → copy to `ml_data` → `python tools\train_ml.py`. Retrain at least monthly; the model weights recent
payments more (half-life 18 months). Re-train after any `pip` upgrade of scikit-learn (saved models are version-specific).

## 6. Results on your data (walk-forward backtest, 6 cut-offs Sep 2025 – Jun 2026, trained only on data before each cut-off)

| Type | Metric | Fixed rule | ML |
|---|---|---|---|
| Invoices | median date error | 11.0 days | **6.8 days** |
| | placed within ±1 week | 55% | **72%** |
| | 12-week weekly-total error | 99% | **79–95%** (varies with library versions) |
| Sales orders | median date error | 20.7 days | **8.1 days** |
| | placed within ±1 week | 35% | **64%** |
| | 12-week weekly-total error | 106% | **93–95%** |
| Bills | median date error | **4.4 days** | 7.0 days |

→ ML helps invoices and sales orders; for bills the existing rule is better, so bills ship **off**.
The date-level gains (median error, within ±1 week) are stable across library versions; the weekly-total gain is smaller and less stable.
Averages hide variance: ML did not win every cut-off (e.g. May–Jun 2026 invoices were roughly equal).
Weekly-total errors are high for both methods because only ~50–80 documents are open at any time; large single
invoices (SERVPRO) dominate.

## 7. ⚠ Decision needed before enabling sales orders — SERVPRO

The history shows SERVPRO pays **about 11 days after the invoice date**, stable for 7 straight quarters, regardless of
whether terms are Net 30 or Net 45, and ~11–15 days after ship date. The engine assumes **ship + 45 days**. ML follows
the data, which moves SERVPRO cash roughly 30 days earlier (on the 9 Oct run, week-1 ending cash goes from –$22k to about
+$262k). This is the biggest effect in the whole model. Confirm with the client that the 11-day pattern is a real
arrangement and not a data artefact (e.g. ship dates entered after the fact) **before** enabling it for SERVPRO.
To keep SERVPRO on the rule while using ML for everyone else, use the optional exclusion in §8.

## 8. Tuning (all in the `"ml"` block)

| Key | Default | Meaning |
|---|---|---|
| `enabled` | false | master switch |
| `use_for.invoices / sales_orders / bills` | true / true / false | per document type |
| `min_party_history` | 3 | customer needs this many past payments, else rule |
| `max_shift_days` | 75 | ignore ML if it moves a date more than this |
| `montecarlo.simulations / seed / party_correlation` | 2000 / 42 / 0.5 | band settings; correlation = a customer's invoices tend to be late together |

## 9. Limits to know

* Learns **timing only**. If a customer stops paying or is written off, history will not predict it.
* Backtest uses final shipment dates from the history (a mild optimistic bias for sales orders).
* Customers with < 3 payments use the rule; new customers get no ML benefit until history builds.
* The dashboard does not yet show the band — it is available through the API/JSON (§5). A chart is the natural next step.
* Not done (next phases): ML for the run-rate expense rows (card spend, freight) from `expenses` + `bank transactions`; predicting
  ship-date slippage for orders without a ship date; band shown on the dashboard and in the Excel export.

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| Open item "ML timing is switched on but could not be used (…)" | Model not trained or wrong path → run `python tools\train_ml.py`. Forecast used the rules meanwhile. |
| `No Zoho history workbook found` | Put `Zoho_history_*.xlsx` in `ml_data\`. |
| `ModuleNotFoundError: sklearn` | `pip install -r requirements.txt` in the active venv. |
| Pickle / version error loading the model | scikit-learn version changed → retrain. |
| `/api/ml/...` returns 401 | Not logged in (same session as the dashboard). |
| Compare shows 0 ML lines | `use_for` all false, or customers have < 3 payments, or ML lines overdue. |

Tests: `python -m pytest tests/test_ml_timing.py -q` (synthetic data, no Zoho needed).
