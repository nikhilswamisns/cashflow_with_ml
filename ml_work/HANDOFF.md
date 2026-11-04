# Handoff: ML revenue forecasting and the dashboard (written 3 Nov 2026)

For a teammate (or their Claude) picking this up. Read this first, then `REPORT.md`, `ML_APPROACH.md` and `NEXT_PHASE_PLAN.md`.

## What this is
The Gutster Tools cash flow engine (Zoho Books, FastAPI + plain JS dashboard) now has an ML layer in `ml_work/`. It forecasts **monthly revenue** for the next 12 months from 5 years of Zoho history and shows it on a new dashboard page. It is separate from the 52-week cash engine (`app/`, `tools/`); nothing here changes the engine's Excel output.

Not to be confused with `app/ml/` (older): that is the **payment-timing** model, which moves invoices to the week cash is expected. It has the ON/OFF switch, Train, Backtest and Compare controls.

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
- The Cash Position Trajectory on `/ui2/` also shows the ML-timed line and p10 to p90 band next to the rule-based line (`overlayMlTrajectory` in `static_v2/app.js`). See the 4 Nov update in `NEXT_PHASE_PLAN.md` for what is and is not connected.

## Known gaps (be honest about these)
- The revenue forecast is **not connected to the 52-week cash forecast**. Connecting it (weeks 14 to 52, behind the ML switch, with a golden test first) is Phase E in `NEXT_PHASE_PLAN.md`.
- The page reads a **snapshot**: CSVs from the Zoho history export. Sync Zoho refreshes the dashboard, not these CSVs. Re-run the scripts on a newer export, or build the warehouse + scheduled refresh (Phase F).
- Some page text is hardcoded in `forecast.js` and `api.py` (model name, "Oct 2026 to Sep 2027", the "4 in 5" legend). Should come from the data.
- `$9.0M` vs `$7.1M` is unresolved by the tests. Plan: add the dollar-line as a thin "conservative case" line.
- `REPORT.md`, `ML_APPROACH.md`, `ML_VISUAL_SUMMARY.md` and the PDFs do not yet include step 5b or the UI page.
- No automated test for the new endpoint.

## Data and privacy
`ml_data/`, `data/`, `ml_work/outputs/` and PDFs in the repo root are git-ignored (real client data). A teammate must get the Zoho history workbook separately, then run `ml_work/02_build_monthly_table.py`, `05_calibrate_range.py`, `05b_compare_trends.py` in that order. Setup: `pip install -r requirements-dev.txt` (exact versions: `requirements-lock.txt`, Python 3.13).

## Working rules from the user
Ask before every commit. Never push. Run scripts and look at the charts. Go step by step. Say plainly when a result is weak. Keep ML work in `ml_work/`; do not change the engine without a golden test.
