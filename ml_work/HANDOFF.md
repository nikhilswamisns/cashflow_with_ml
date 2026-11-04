# Handoff: ML revenue forecasting and the dashboard (written 3 Nov 2026, updated 4 Nov 2026)

For a teammate (or their Claude) picking this up. Read this first, then `REPORT.md`, `ML_APPROACH.md` and `NEXT_PHASE_PLAN.md`.

## What this is
The Gutster Tools cash flow engine (Zoho Books, FastAPI + plain JS dashboard) now has an ML layer in `ml_work/`. It forecasts **monthly revenue** for the next 12 months from 5 years of Zoho history and shows it on a new dashboard page. It is separate from the 52-week cash engine (`app/`, `tools/`); nothing here changes the engine's Excel output.

Not to be confused with `app/ml/` (older): that is the **payment-timing** model, which moves invoices to the week cash is expected. It has the ON/OFF switch, Train, Backtest and Compare controls.

## Two ML models, two different jobs (read this first, it caused the most confusion)
| | Payment-timing model (`app/ml/`) | Revenue trend model (`ml_work/`) |
|---|---|---|
| Predicts | *When* each known invoice, order or bill is paid | Monthly invoiced revenue, next 12 months |
| Shown in | Cash Position Trajectory: the line "Paid when customers actually pay (ML timing)" and its band | Expected Receipts: the layer "Expected new revenue (ML)" |
| Not included | Anything not yet booked | Costs, bills, payment timing |

Neither model predicts net cash flow. There is no cost model. The trajectory is known documents (timing from rules or ML) plus flat run-rates. The ML timing is OFF in the base forecast (`forecast_rules.json` `ml.enabled=false`), so the Expected Receipts "Known" layer is plain rules.

## What was done
| Step | Script (`ml_work/`) | Result |
|---|---|---|
| 1-2 | `01_explore_data.py`, `02_build_monthly_table.py` | 60 clean months (Oct 2021 - Sep 2026), 3,411 invoices, $10.37M, ~10x growth. SERVPRO about 50% of revenue |
| 3 | `03_train_and_test.py` | 12 models, 2 time-based tests. Best: log-linear trend on last 24 months, 27% average monthly miss. Trees go flat, raw neural nets overshoot |
| 4, 4b | `04_*.py`, `04b_*.py` | 12-month forecast and a 4-year backtest |
| 5 | `05_calibrate_range.py` | Range from errors of the last 12 months: 89% walk-forward coverage, 11 of 12 months in the backtest. Also writes `05_backtest_new_range.csv` |
| 5b | `05b_compare_trends.py` | Log-linear vs dollar-line vs damped trend. Log-linear narrowly best (28.5% vs 29.5% vs 34.9% monthly miss). Damped clearly worst. Log-linear vs dollar-line is close to a tie |

Headline: **$9.02M next 12 months** (+92% vs last 12 months), range $7.74M to $15.11M. The dollar-line gives $7.08M, just below the range's low edge. Every model under-forecast by about 21% on 12-month totals because growth sped up.

## What is in the UI
- `GET /api/ml/revenue-forecast` (`app/ml/api.py`): read-only; computes everything from CSVs in `ml_work/outputs/`.
- `static_v2/` is the restyled dashboard (dark, one accent, grouped sidebar). **`static/` is still the original.** Swap by copying `static_v2/` over `static/` only when agreed.
- `static_v2/forecast.js`: the Revenue Forecast page (history, dashed forecast, range band, 3 summary cards). Injected by `app/main.py`.
- `static_v2/ml.js`: payment-timing page; train/backtest/compare are in a collapsed Admin block.
- The restyled dashboard is served at `/ui2/` (the original stays at `/ui/`). Run: `CASHFLOW_DISABLE_AUTH=1 python -m uvicorn app.main:app --port 8011`, then open `/ui2/`. `CASHFLOW_DISABLE_AUTH` is local-only; never set it on a hosted copy.
- **Expected Receipts (cash in only)** panel on `/ui2/`, under the trajectory: line chart of running total or per week, 52/26/13 week pills, layer chips (Booked, Known, Known + expected new, Likely range) with live totals, three cards. Code: `renderReceiptsOutlook` in `static_v2/app.js`, chips and tooltip in `static_v2/index.html` and `style.css`. API: `GET /api/ml/runs/{run}/receipts-outlook` (`app/ml/api.py`), logic in `app/ml/receipts_outlook.py`. Standalone version and PNG: `ml_work/06_receipts_rules_vs_forecast.py`.
  - Method: per month, `max(0, forecast x share of the month inside the 52 weeks - receipts the rules already show)`, spread over that month's weeks. Known documents are counted first, so nothing is counted twice.
  - Latest run (week 1 = 30 Oct 2026): known $3.15M ($1.10M booked, $2.05M flat run-rate), expected new revenue $6.30M, total $9.45M, range $8.10M to $15.82M. Booked documents thin out after about week 18.
  - Weeks after Sep 2027 extend the same log-linear trend (constant monthly growth factor, band as fixed multiples), inside this module only. The 12-month files and the $9.02M headline are unchanged.
  - Tests: `tests/test_receipts_outlook.py` (extension, gap-only rule, never negative).
- The Cash Position Trajectory on `/ui2/` also shows the ML-timed line and p10 to p90 band next to the rule-based line (`overlayMlTrajectory` in `static_v2/app.js`). See the 4 Nov update in `NEXT_PHASE_PLAN.md` for what is and is not connected.

## Known gaps (be honest about these)
- The revenue forecast is **not connected to the 52-week cash forecast**. Connecting it (weeks 14 to 52, behind the ML switch, with a golden test first) is Phase E in `NEXT_PHASE_PLAN.md`.
- The page reads a **snapshot**: CSVs from the Zoho history export. Sync Zoho refreshes the dashboard, not these CSVs. Re-run the scripts on a newer export, or build the warehouse + scheduled refresh (Phase F).
- Some page text is hardcoded in `forecast.js` and `api.py` (model name, "Oct 2026 to Sep 2027", the "4 in 5" legend). Should come from the data.
- `$9.0M` vs `$7.1M` is unresolved by the tests. Plan: add the dollar-line as a thin "conservative case" line.
- `REPORT.md`, `ML_APPROACH.md`, `ML_VISUAL_SUMMARY.md` and the PDFs do not yet include step 5b or the UI page.
- Speed of the ML line on the trajectory (`GET /api/ml/runs/{run}/compare`): about 2 to 3.5 s to compute, almost all of it the timing model predicting about 130 documents one at a time (about 1.5 to 2 s) plus reloading the model file (about 0.65 s). Fixed on 4 Nov without touching the engine: the result is cached in the server (`app/ml/result_cache.py`, keyed on the run's data plus the rules, assumptions, template and model files, so any edit recomputes) and the model file is loaded once per file version (`_load_bundle` in `app/ml/predictor.py`). A repeat load is about 0.01 s; the first load after a server restart is still about 3.5 s. Still open: predict all documents in one batch (biggest saving, touches the engine, needs a golden test first) or warm the cache at startup.
- The saved timing model was written with scikit-learn 1.9.1 but the server runs 1.8.0 (a version warning on load). It works today; retrain on the server's setup to remove the risk.
- The new endpoint itself has no HTTP-level test (the logic has unit tests).
- Expected Receipts simplifications, stated on the chart tooltip: forecast revenue is treated as cash in the same month (no payment lag); the flat run-rate may overlap open A/R (client note in `forecast_rules.json`); receipts only.
- About two thirds of the 52-week total is the ML trend, which misses about 27% a month on average and is wide ($8.1M to $15.8M). Rules alone assume zero growth, so $3.15M is a floor and the ML total is probably on the high side. Show the range, not one number.
- Cash Position Trajectory weeks 30 to 52 are identical in both lines with a zero-width band. That is a flat run-rate assumption, not a forecast. The note under the chart says so.
- The payment-timing model's backtest (config says it beat the rules for invoices and sales orders, not bills) was not re-run in this work.
- Local setup: the Python 3.13 used for the server was missing `openpyxl` and `python-multipart` on 4 Nov. Installed with pip (both are in the requirements files).

## Data and privacy
`ml_data/`, `data/`, `ml_work/outputs/` and PDFs in the repo root are git-ignored (real client data). A teammate must get the Zoho history workbook separately, then run `ml_work/02_build_monthly_table.py`, `05_calibrate_range.py`, `05b_compare_trends.py` in that order. Setup: `pip install -r requirements-dev.txt` (exact versions: `requirements-lock.txt`, Python 3.13).

## Working rules from the user
Ask before every commit. Never push. Run scripts and look at the charts. Go step by step. Say plainly when a result is weak. Keep ML work in `ml_work/`; do not change the engine without a golden test.
