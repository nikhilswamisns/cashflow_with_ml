# ML work: trend forecasting from 5 years of Zoho history

Separate from the production engine (app/, tools/). Nothing here changes the forecast Excel files.
Source data: ml_data/Zoho_history_2021-10-01_to_2026-10-07.xlsx (read-only).

Run scripts from the project root with the Mac venv:  .venv-mac/bin/python ml_work/<script>.py

| Step | Script | What it does |
|---|---|---|
| 1 | 01_explore_data.py | Profile each dataset, find data problems, draw first charts |
| 2 | 02_build_monthly_table.py | Clean invoices (drop void, draft, $0), build one row per month by segment |
| 3 | 03_train_and_test.py | Train 12 forecasting models (incl. 3 neural-network variants) on the past, test on unseen months (2 time-based folds), chart + scores |
| 4 | 04_forecast_next_12_months.py | Train on all 60 months, forecast Oct 2026 - Sep 2027 with a range |
| 4b | 04b_backtest_last_year.py | Same chart run in the past: train on 4 years, forecast year 5, compare with reality |
| 5 | 05_calibrate_range.py | Walk-forward test of 4 range methods; picks the one closest to 80% coverage and redraws steps 4 and 4b with it |
