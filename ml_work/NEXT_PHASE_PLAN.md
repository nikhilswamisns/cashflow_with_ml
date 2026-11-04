# Next phase plan (written 2 Nov 2026)

Handoff for a fresh session. Read this first, then `ml_work/REPORT.md` and `ml_work/README.md`.

## Where we are

- Project: Gutster Tools cash flow engine (Zoho Books, FastAPI + plain JS dashboard) plus our ML work in `ml_work/`.
- Git: local repo only (never push). Last commit `e82f002` (step 5). Steps 1 to 5 are committed.
- **Uncommitted, waiting for the user's yes:** `ml_work/ML_APPROACH.md`, `ml_work/ML_VISUAL_SUMMARY.md`, `ml_work/report/ML_Approach.pdf`, `ml_work/report/ML_Visual_Summary.pdf`, `ml_work/report/images/05_*.png`, `.gitignore` (`.gstack/` line added by the PDF tool), this plan file.
- Environment: Mac venv `.venv-mac`. Installed by hand, not in requirements: fastapi, uvicorn, pydantic, python-multipart, httpx, pytest, matplotlib, statsmodels.
- Dashboard: run with `CASHFLOW_DISABLE_AUTH=1 .venv-mac/bin/python -m uvicorn app.main:app --port 8010` (port 8000 is used by another process on the user's Mac). The switch is local-only, off by default, committed in `9da23fd`.
- PDFs: `$HOME/.claude/skills/gstack/make-pdf/dist/pdf generate`. Local images are dropped, so build from a temp copy with images inlined as base64 and `<img style="width:100%">`.

## Findings so far (do not redo)

- 60 clean months (Oct 2021 to Sep 2026), 3,411 invoices, $10.37M. About 10x growth. SERVPRO about 50% of revenue.
- 12 models compared on two time-based tests. Best: log-linear trend on last 24 months, 27% average monthly miss. Trees go flat, raw neural nets overshoot, every sane model under-forecasts (growth accelerated).
- Sales orders are not a leading indicator (order to ship median 1 day). SERVPRO is not driven by a few huge invoices.
- Range: method D (errors from the last 12 months) gave 89% walk-forward coverage and 11 of 12 months in the 4b backtest. The first version covered only 4 of 12.
- Open doubt: the trend compounds about 100% a year ($9.0M next 12 months). A dollar-based line gives $7.1M, below the band's low edge ($7.7M).

## Phases

| Phase | Task | Done when |
|---|---|---|
| A | Housekeeping: ask to commit the pending files. Fix `requirements.txt` (split into full and Excel-only, pin versions). Add `.dockerignore` (exclude `.env`, `data/`, `ml_data/`, `BankStatement/`, venvs, `output/`). | Commits made after approval; `pip install -r requirements.txt` works on a clean venv |
| B | **Step 5b:** walk-forward test of log-linear vs dollar-line vs damped trend on 12-month totals and 1 to 12 month errors. Redraw the forecast chart on the winner. Update `REPORT.md`, `ML_APPROACH.md`, `ML_VISUAL_SUMMARY.md` and rebuild both PDFs. | One trend chosen with numbers; charts and PDFs updated |
| C0 | **UI design pass (user request, 2 Nov 2026).** The dashboard looks generic and AI-generated. Goal: better readability and room for future work. **Do not remove or hide any chart or feature**; reorganize instead. Steps: (1) screenshot every page as it is now (browse skill); (2) critique it and agree a design direction with the user before coding (use the impeccable, design-consultation and design-review skills); (3) restyle through design tokens in `static/style.css` (type scale, spacing, colour, chart sizing and labels); (4) restructure the sidebar into sections that can grow (for example Forecast, Revenue forecast, Models, Data, Settings); (5) before and after screenshots. | User approves the direction and the after screenshots; every original chart and control still works; checked at laptop and narrow widths |
| C | **UI: Revenue Forecast page.** First ask the user exactly what UI change they were asked for. Default proposal: `static/forecast.js` modelled on `static/ml.js`, plus an endpoint under `app/ml/` that serves forecast, range, model scores and backtest as JSON. Chart.js is already loaded. | Page shows in the sidebar and renders from the API; user has seen it in the browser |
| D | **Step 6:** forecast SERVPRO, Amazon and Other separately, test whether the sum beats one total. | Scores for both approaches on the same two folds |
| E | **Step 7:** turn monthly revenue into weekly receipts for weeks 14 to 52, using the existing payment-timing model. Behind the ML switch. Add a golden test on the committed snapshot first (lowest cash -$54,470 in week 7, week-13 ending cash about $12k). | Engine output for weeks 1 to 13 unchanged; weeks 14 to 52 changed only when the switch is on |
| F | **Step 8:** warehouse database (SQLite, `data/warehouse.db`) with raw, clean, forecast and prediction tables, plus a forecast vs bank balance scorecard. | Row counts match the history Summary sheet; scorecard runs |

Order: A, B, then C0 (design pass) before C (so the new page is built in the new design), then E in whichever order the user prefers, then D, F.

## Questions for the client (via the user)

1. What are the about 660 checking-account journal entries (about $1.7M, nearly all money in, no payee)?
2. Does SERVPRO really pay about 11 days after invoice?
3. Known events the data cannot see: new locations, price changes, big orders?

## Deployment notes (if asked)

Docker image would crash (requirements missing web packages) and would copy real data in (no `.dockerignore`). Compose maps port 8000. Never set `CASHFLOW_DISABLE_AUTH` on a hosted copy. CORS is open (`*`).

## Working rules (from the user)

Ask before every commit and never push. Run scripts and open the charts. Go step by step. Say plainly when a result is weak. Keep ML work inside `ml_work/`; do not change the engine without a golden test.

## Update 4 Nov 2026: combine rule-based and ML on the cash chart

Done: `/ui2/` Cash Position Trajectory now shows the rule-based line (blue), the ML-timed line (orange dashed) and the ML p10 to p90 band, from `GET /api/ml/runs/{run}/compare` (about 3.5 s, cached per run). Code: `overlayMlTrajectory` in `static_v2/app.js`, legend in `static_v2/index.html`. `/ui/` is untouched.

What the chart is: a forecast from today's opening cash, built only from rules. Weeks 1 to 13 rest on real open invoices, orders, POs and bills. After about week 29 the only inflow is the flat reseller run-rate (about $42k a week); SERVPRO inflow is about zero because no future orders exist yet. The ML timing line only moves known documents, so the two lines match after week 29 (30 Oct run). The revenue forecast from `ml_work/` (the $9.02M) is **not** in the cash chart yet. The revenue model was trained on monthly invoice revenue totals only, not on costs, bills or timing.

Idea to build: **known first, ML fills the gap.** Expected receipts per week = known documents (rules, retimed by the timing model) + forecast revenue not yet booked (monthly forecast minus what is already booked in that month, so nothing is counted twice). Known backlog only reaches a few weeks out (orders ship about 1 day after they are placed), so the revenue model matters most after week 13.

Steps, in order:
1. Receipts chart, weeks 1 to 52: rules only vs rules plus the revenue forecast (receipts only, no cost problem).
2. Costs for later weeks: known bills and POs, then a cost-to-revenue ratio from the 5-year history. Needs client input. Do not add revenue without matching costs, or cash is overstated.
3. Third line on the Cash Position Trajectory. Write a golden test first so weeks 1 to 13 cannot change.
4. Optional: use known data (open order amounts, customer payment lags) as model inputs.

Open client questions: the cost-to-revenue ratio; the about 660 no-payee checking-account journal entries (about $1.7M); does SERVPRO pay about 11 days after invoice; known events the data cannot see.
Also open: $9.0M (log-linear) vs $7.1M (dollar-line) next 12 months; XGBoost was discussed as a possible step 5c (expected to lose, same as the other tree models).

Run the new look: `CASHFLOW_DISABLE_AUTH=1 python -m uvicorn app.main:app --port 8011`, then open `/ui2/`. An older server on port 8010 has no forecast endpoint.
