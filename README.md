# Gutster Tools — Cash Flow Forecasting Engine (Zoho Books)

Builds the weekly cash flow forecast (Version 10 layout, 52 weeks) directly from **live Zoho Books data**, read-only,
and exports it as the audited Excel workbook finance and the client review.

* One click pulls invoices, sales orders, purchase orders, bills, cash and card balances from Zoho.
* The forecast follows the **Assumptions & Rules**, **General Info**, **Expense Assumptions** and **NewAddtnl Assumptions**
  sheets of the Version 10 template, plus `app/config/forecast_rules.json`.
* Every sync is archived (the exact Zoho data, the rules in force, and every export), so each report can be traced
  back to the data it was built from.
* **Nothing is ever written to Zoho.**
* The app needs a **login**; without one no page or data can be opened.

---

## Files needed to run (not in Git, ask the project owner)

Put these in the project folder before starting:

- `.env` (copy `.env.example`, fill in the Zoho keys)
- `data/cashflow.db` and `data/snapshot_*.json` (database and Zoho data)
- `app/config/assumptions.json` and `app/config/corporate_accounts.json`
- `app/templates/v10_template.xlsx` and `app/templates/Cash_Flow_Forecast_Template.xlsx`
- `ml_data/` (Zoho history workbook, only for the ML scripts in `ml_work/`)

Setup: `pip install -r requirements-dev.txt`, create a login with `python tools/add_user.py`, then start the server
(section 1). The dashboard is at `/ui/` and the restyled one at `/ui2/`.

---

## 1. Install and start (Windows)

Requirements: **Python 3.9+** (3.11 recommended) and internet access to Zoho.

1. Unzip the project, e.g. to `C:\Users\<you>\cashflow\cashflow-2`.
2. Create `.env` from `.env.example` and fill in the Zoho values (section 3).
3. **Create a login (once):** in the project folder run `python tools\add_user.py` and type a user name and a
   password (at least 6 characters). Without a user nobody can open the app; the login page shows this command.
4. Double-click **`start.bat`**. It installs the packages in `requirements.txt` and starts the server.
5. Open **http://localhost:8000/ui** in the browser and sign in. **Logout** is at the top right of the dashboard.

**First start on a new computer:** the `data` folder is created automatically, with an empty runs database
(`data\cashflow.db`). The run list is empty until the first **Sync Zoho**.

**With a virtual environment (cmd)** instead of `start.bat`:
```
cd /d "C:\Users\<you>\cashflow\cashflow-2"
python -m venv .venv                      (first time only)
.venv\Scripts\activate
pip install -r requirements.txt           (first time, and after an update that changes requirements.txt)
python tools\add_user.py                  (first time only)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Stop the server with **Ctrl+C**. In PowerShell activate with `.venv\Scripts\Activate.ps1`.

Mac / Linux: `pip3 install -r requirements.txt`, `python3 tools/add_user.py`, then `./start.sh` (or
`python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000`).

### 1a. Login

| Task | How |
|---|---|
| Add a user / change a password | `python tools\add_user.py` (password at least 6 characters, typed twice) |
| List users | `python tools\add_user.py --list` |
| Remove a user | `python tools\add_user.py --remove NAME` |
| Sign out | **Logout**, top right of the dashboard |
| Log everybody out | delete `data\.session_secret` and restart |

* Passwords are stored only as salted hashes in `data\users.json`. A login lasts 12 hours.
* 5 wrong passwords from one computer within 5 minutes: that computer waits 5 minutes.
* Changes to users take effect immediately; no restart needed.

### 1b. Logo and login picture

* **Logo** (login page and top left of the dashboard): the image in the **`logo`** folder (`.svg`, `.png`, `.jpg`,
  `.webp`; a file with "logo" in its name is used first). Now `logo\cashflow-logo.svg`.
* **Login picture** (left half of the login card): the image in the **`background`** folder; a portrait picture of
  about 600 × 720 or larger fits best. Now `background\login-background.svg`, made for this app.
* To change either, put the new image in the folder and remove the old one; refresh the browser. If a picture's
  licence asks for a credit (e.g. a free Magnific / Freepik image: "Designed by Magnific"), create
  `background\credit.txt` with the credit text on line 1 and the link on line 2; it is shown on the picture.

### 1c. Sending the app to someone else (release zip)

**Leave out of the zip** — the app creates what it needs on the first start:

| Leave out | Why |
|---|---|
| **`.env`** | Zoho client secret and refresh token. **Never send it**; the receiver creates their own from `.env.example`. |
| **`data\`** (whole folder) | `cashflow.db` = all your runs and the Zoho data behind them; `users.json` and `.session_secret` = your logins. Recreated empty on the first start. |
| `exports\` | Zoho history exports (company data) |
| `zoho_data_archive\` (or the `ZOHO_ARCHIVE_DIR` folder) | Archived Zoho data and exports of your runs |
| `.venv\`, every `__pycache__\` | Built on the receiving computer |
| `archive\`, `August 31\`, `BankStatement\`, `examples\`, old `*.xlsx` / `*.pdf` in the project root | Old sample files, statements and reports; not used by the app |

**Keep:** `app\`, `zoho\`, `static\`, `logo\`, `background\`, `tools\`, `tests\`, `requirements.txt`, `start.bat`,
`start.sh`, `.env.example`, `README.md`, `SETUP_GUIDE.md`, `LOGIN_SETUP.md`, `CHANGES_v10_ENGINE.md`
(and `Dockerfile` / `docker-compose.yml` if Docker is used).

The receiver then follows section 1: `.env` → `python tools\add_user.py` → `start.bat` → sign in → **Sync Zoho**.

**Updating to a new version:** unzip the new files over the project folder (allow overwrite), restart `start.bat`,
and refresh the browser with **Ctrl+F5**. Your `.env`, `.venv`, the `data` folder (runs and logins) and the archive
folder are not part of the update and are left untouched.

---

### 1d. One year of Zoho history to Excel (read-only)

With the venv active, from the app folder:

| Task | Command |
|---|---|
| Last 365 days | `python tools\export_history.py` |
| Last 2 years | `python tools\export_history.py --days 730` |
| Exact dates | `python tools\export_history.py --from 2025-10-01 --to 2026-09-30` |
| Some datasets only | `python tools\export_history.py --only invoices,bills,bank` |

Writes `exports\Zoho_history_<from>_to_<to>.xlsx`: a Summary sheet (range, pull time, count per dataset) and one
sheet each for invoices, customer payments, credit notes, sales orders, bills, vendor payments, vendor credits,
purchase orders, expenses and bank/card transactions — all statuses, by document date. Only reads from Zoho; it does
not touch the forecast or the runs. A year takes a few minutes. The file is company data: keep it out of zips and emails.

## 2. Using the app

### Top bar
| Control | What it does |
|---|---|
| **Week 1 from [date] + 🔄 Sync Zoho** | Pulls Zoho and builds a forecast whose week 1 is the **Friday on or before the chosen date** (defaults to the latest Friday). The new run is selected automatically. |
| **🔁 Refresh & Compare** *(fix 23+)* | For the selected run: pulls Zoho again (read-only) with the **same week 1** and compares. The run's own numbers do not change; the dashboard shows a **Since run** panel, the matrix gets **Run / Refresh / Difference** views, and every export of the run gets an extra sheet **"Changes Since Run"** (section 2a). |
| **⬇ Export** | Downloads the Excel for the selected run (`Cash_Flow_Forecast_<date>.xlsx`) and saves a copy in the run's archive folder. |
| **🏦 Opening Cash** | Shows opening cash for the selected run (Zoho balance per account, the logged adjustments, the total). Enter the **bank balance and its date** and click *Apply to this run*: the difference from Zoho cash becomes the adjustment line (General Info row 45). *Use Zoho cash + logged adjustments* removes the override. |

### Sidebar
| Control | What it does |
|---|---|
| **Active forecast run** | All runs, shown as `forecast date · synced date time`. |
| **📂 Open archive folder** | Opens the selected run's Zoho data folder in Windows Explorer. |
| **Zoho status light** | Green "Zoho connected · org …" or red "Zoho not connected" (hover for the reason). Click to re-check. |
| **🔁 Re-run from archive** | Choose a `zoho_snapshot.json` from an archive folder: the forecast is rebuilt from exactly that data as a new run. |
| **🛠 API Docs** | Opens the technical API page (`/docs`) — not needed for normal use. |
| **User name · Logout** (top right) | Who is signed in; signs out and returns to the login page. |

### Screens
* **Executive Dashboard** — opening cash, lowest point, horizon end, A/R, A/P, charts.
* **52-Week Matrix** — the Excel *Cash Flow Model* sheet row for row (Code, Account, every section incl.
  Non-Operating and Borrowing, totals, Ending Cash). Click a SERVPRO / Amazon / A/R / COGS cell to see its line items.

### 2a. Refresh & Compare ("Changes Since Run")

*(Versions with fix 23 or later. If there is no **🔁 Refresh & Compare** button, this feature is not installed.)*

Use it when the forecast is built (e.g. Thursday evening) but sent later (e.g. Friday morning), to show what moved in Zoho in between.

1. Select the run, click **🔁 Refresh & Compare** (takes as long as a sync). Repeat any time; the latest refresh is used.
2. **Dashboard → Since run:** run vs refresh for opening cash, week 1–3 ending cash, lowest point, horizon end, A/R,
   uninvoiced SOs, and the bridge of why horizon-end cash changed.
3. **52-Week Matrix → Run | Refresh | Difference:** *Run* = the forecast as exported, *Refresh* = rebuilt from the refresh
   pull, *Difference* = Refresh minus Run with changed cells highlighted; click a SERVPRO / Amazon / A/R / COGS cell to see
   which invoice, order, PO or bill caused it.
4. **⬇ Export:** all sheets show the **run** (unchanged); the last sheet **"Changes Since Run"** has
   * A — summary (run, refresh, change), B — ending cash for the first 13 weeks,
   * C — the bridge: *settled activity* (opening cash change, receipts/payments no longer open or partly paid — close to 0
     when cash simply settled forecast items) and *real changes* (new items, amount / status / date changes, card
     statements); it totals exactly to the change in horizon-end cash,
   * D — **every change** by area: opening cash per account, invoices, sales orders, purchase orders, bills, linked lines,
     credit cards (balances, statements, new card transactions), manual entries — with status from → to, run and refresh
     amount and week, and the effect on cash ("No cash effect" = status only, "Timing only" = same amount, other week).
5. The refresh is saved with the run (database) and in its archive folder: `refresh_<date>_<time>\` with its own
   `Zoho_data.xlsx`, `zoho_snapshot.json` and `forecast_rules.json`.

Both sides are built with the **current** rules and the same week 1, so every difference comes from Zoho. If the rules file
changed since the run was synced, the sheet says so at the top. Uncategorized bank items are not pulled yet.

### Weekly routine
1. After Friday's banking is posted in Zoho: pick the Friday in **Week 1 from**, click **Sync Zoho**.
2. If you have the bank statement: **🏦 Opening Cash** → enter the bank balance → *Apply*.
3. **⬇ Export**, open the file in Excel and save it once (so the calculated values are stored).
4. One-off amounts (e.g. a loan repayment Ralph confirms by email) go in `forecast_rules.json` →
   `manual_entries` (section 4a), then **Sync Zoho** or **Export** again. Remove an entry once it is posted in Zoho,
   or it is counted twice.

---

## 3. Zoho connection (`.env`)

```env
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REFRESH_TOKEN=...
ZOHO_ORG_ID=695133731
ZOHO_ACCOUNTS_URL=https://accounts.zoho.com
ZOHO_API_BASE_URL=https://www.zohoapis.com/books/v3

# Optional: where the Zoho data archive is written (absolute path, or relative to the project folder)
# ZOHO_ARCHIVE_DIR=D:\Finance\Gutster\Cashflow Zoho Archive
```

Getting the refresh token (Zoho API Console → **Self Client** → *Generate Code*), read-only scopes:

```text
ZohoBooks.invoices.READ,ZohoBooks.salesorders.READ,ZohoBooks.purchaseorders.READ,ZohoBooks.bills.READ,
ZohoBooks.banking.READ,ZohoBooks.accountants.READ,ZohoBooks.settings.READ,ZohoBooks.expenses.READ
```

Then exchange the grant code: `python -m zoho.auth --exchange <grant code>` and put the printed refresh token in `.env`.
Find the organisation id with `python -m zoho.client --list-orgs`. Check everything with
`python zoho\verify_connection.py` (it also saves `data\last_snapshot.json`).

`ZohoBooks.accountants.READ` is needed for the **Stripe Clearing** balance (chart of accounts). Without it the sync
still works but Stripe Clearing is left out of opening cash (a warning is logged in the `start.bat` window).

**Never share `.env`** (client secret, refresh token) and never include it in a zip.

---

## 4. What the forecast does (rules)

| Area | Rule |
|---|---|
| Window | 52 week-ending Fridays from week 1 (`window_weeks` in `forecast_rules.json`; 45 before 6 Oct 2026) |
| Receipts | Friday **on or after** the due / cash-in date; anything overdue lands in week 1 |
| Payments | Friday **on or before** the due date; anything overdue lands in week 1 |
| Invoices | Sent / Overdue / Partially paid at balance; **Draft** at total |
| Sales orders | Confirmed / Open / Overdue / Partially invoiced / Draft at the **uninvoiced** remainder. SERVPRO ship date + 45 days, Amazon + 30, resellers + 21; no ship date → order date + days, labelled UNVERIFIED. A parent order whose partial fills were raised under other SO numbers (`sales_orders.parent_orders`, e.g. SO-05927) has the fills deducted only while its Zoho total still includes them |
| Purchase orders | Issued / Open / Draft / Partially billed at the **unbilled** amount; due = delivery date (or PO date, UNVERIFIED) + the **payment terms on the PO** (Net 30/60/90, Due on Receipt = 0; the "Payment Term" custom field is ignored) — Assumptions & Rules row 13 |
| Bills | Open / Overdue / Partially paid at balance; COGS accounts only; Prudent (3PL), Amex loan installment, IRS/NJ tax bills excluded (covered by run-rates / schedules) |
| Opening cash | Exactly **BUSINESS FUNDAMENTALS CHK + PayPal + Petty Cash + Stripe Clearing** (book balances) + any logged opening-cash adjustment (`opening_cash.manual_adjustments`, currently none), or the bank balance entered in the UI |
| Expenses | Expense Assumptions column E on their schedules (card-paid lines 3rd Friday, payroll biweekly from 21 Aug 2026, rent / vehicle / owner draws 1st Friday, commission 2nd Friday, health insurance 2nd-Tuesday week, accounting April 4th week); taxes and interest from General Info |
| Revenue rows | Revenue Detail column A routes each line: `SERVPRO*` → Cash Flow Model row 8, `Amazon*` → row 10 (customers whose name contains "Amazon": Gutster / Staple Popper / Duckbill Amazon USA & Canada — client decision 1 Oct 2026, Assumptions & Rules row 7), `A/R*` → row 14 (everyone else). Other Resellers run-rate row 9 |
| Credit cards | Card-paid expenses (incl. Amazon Ads row 47 and Vehicle row 51) are added back (row 96) and paid as monthly statements (row 94): cycle closes the 26th, due the 20th, paid the Friday on or before. The first statement is the oldest **closed but unpaid** one, at the **balance at the close** (live balance less charges posted after the close); those later charges go on the next statement (Credit Card Payments B34). Outbound freight is taken out in full on row 30 (1st Friday cash part, 2nd Friday card part); the card share is measured from the last three card cycles |
| Duckbill repayment | Row 95 (Loan Repayments), General Info B32 ($3,750) on the **1st Friday** of each month through Dec 2027. An open Duckbill bill in Zoho (Skagit Valley Innovations, IP rights payable) is paid on the 1st Friday of the month after its bill date (before week 1 → week 1) and replaces that month's scheduled payment, so no month is counted twice. Client decision 6 Oct 2026 (`duckbill` in `forecast_rules.json`) |
| Paid / realised since the prior forecast | Compared with the last run for an **earlier** week 1 (a re-sync of the same week is not a prior forecast) |

### 4a. Manual entries (one-off amounts)

Amounts that are not in Zoho yet — e.g. the **$73,000 loan repayment** for w/e 10/02/26 — are entered in
`app/config/forecast_rules.json` under `manual_entries`:

```json
"manual_entries": [
  {"label": "Loan repayment - one-off", "cfm_row": 95, "week_ending": "2026-10-02", "amount": 73000.0,
   "source": "Ralph Markham email, 1 Oct 2026", "entered_by": "Ravleen", "entered_on": "2026-10-01",
   "note": "Remove once categorised in Zoho"}
]
```

* `cfm_row` = the Cash Flow Model row (95 = Loan Repayments). Allowed: 9, 11–13, the non-card expense rows, 87–90 and 95.
  Not the detail-driven rows (8 SERVPRO, 10 Amazon, 14 A/R, 18–20 COGS), the card-funded rows or rows 94/96 — those are
  refused and listed.
* `week_ending` = the Friday of the week (another date uses the Friday on or before it). Amounts are positive
  (a payment in an expense / loan row, a receipt in rows 9–12).
* In the export each entry is a line in **General Info → MANUAL ENTRIES** (row 50 on); the Cash Flow Model cell links
  to it by formula (e.g. `='General Info'!$B$50`, added to any amount already in that cell). It is listed on the
  Overview (KPIs and "Fixed in this run").
* An entry dated **before week 1 expires** automatically (its cash is already in the opening balance): it is listed as
  EXPIRED and not applied. Delete it from the file when it is no longer needed.
* Opening-cash corrections (not a weekly amount) go in `opening_cash.manual_adjustments` instead (General Info row 45),
  or use **🏦 Opening Cash** in the app.

Where to change things:
* `app/config/forecast_rules.json` — statuses, vendor exclusions, cash accounts, manual adjustments, parent orders,
  card cycle, open items shown on the Overview.
* `app/templates/v10_template.xlsx` — General Info (fixed amounts, tax schedule) and Expense Assumptions column E
  are read by the engine. The Assumptions & Rules sheet is kept word for word as Version 10.

Every change from Version 10 is listed in the exported **Overview** under
*"Fixed in this run — changes vs Version 10 and why (for approval)"*; items still open for the client are listed
under *"Additional items for client review"*.

---

## 5. Zoho data archive

Every sync creates a folder (default `<project>\zoho_data_archive\`, or `ZOHO_ARCHIVE_DIR`):

```
Cash_Flow_Forecast_2026-10-02_generated_2026-09-29_1119\
    Zoho_data.xlsx          one sheet per dataset + Summary (counts, totals, pull time, run id)
    zoho_snapshot.json      the exact data the forecast used (re-run it with 🔁 Re-run from archive)
    forecast_rules.json     the rules in force at the time
    manifest.json           run id, dates, counts, totals, list of exports
    Cash_Flow_Forecast_2026-10-02_exported_<date>_<time>.xlsx   every export of this run
```

Archiving never blocks a sync or an export. Deleting old folders does not affect the forecast.

---

## 6. API (for reference — the UI uses these)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/forecast/sync-zoho-live?run_date=YYYY-MM-DD` | Pull Zoho, build a run (returns `run_id`, `archive_folder`) |
| POST | `/api/forecast/run-from-snapshot` (file) | Rebuild a run from a saved `zoho_snapshot.json` |
| GET | `/api/runs` | List runs (with archive folder) |
| GET | `/api/runs/{id}/matrix` · `/analytics` | Weekly figures (Cash Flow Model layout) and dashboard numbers |
| GET | `/api/runs/{id}/export/xlsx` | Excel export (also saved in the archive) |
| GET / POST | `/api/runs/{id}/opening-cash` · `/api/opening-cash` | Read opening cash / set the bank balance for a run |
| POST | `/api/runs/{id}/open-archive` | Open the run's archive folder |
| GET | `/api/zoho/status` | Read-only Zoho connection check |
| POST | `/api/auth/login` · `/api/auth/logout` · GET `/api/auth/me` | Sign in / out, current user (every other call needs a signed-in session) |
| POST | `/api/runs/{id}/refresh` | *(fix 23+)* Refresh & Compare: second Zoho pull for the run's week 1 |
| GET | `/api/runs/{id}/compare` | *(fix 23+)* The comparison (summary, bridge, every change) |
| GET | `/api/runs/{id}/matrix?view=run\|refresh\|diff` | *(fix 23+)* Matrix of the run, of the refresh, or the difference |

Offline (from Zoho export files instead of the API):
`python tools\snapshot_from_exports.py <exports folder> 2026-10-02 snap.json`, then **🔁 Re-run from archive** with `snap.json`.

---

## 7. Tests

```bash
python -m pytest tests/ -q
```
73 pass. 4 tests are skipped unless the `archive\Files 14th Aug` sample export folder is present; the Zoho connection tests need valid credentials in `.env`.

## 8. Project layout

```
app/engine/v10_engine.py      forecast engine (rules above)
app/output/v10_exporter.py    Excel export on the Version 10 template
app/output/v10_adapter.py     engine -> dashboard / matrix
app/output/zoho_archive.py    archive folders
app/output/json_api.py        API used by the UI
app/auth.py                   login (users, sessions, logo / login picture)
app/main.py                   web server, login protection
app/config/forecast_rules.json
app/templates/v10_template.xlsx
zoho/                         read-only Zoho client, snapshot pull, connection check
tools/snapshot_from_exports.py
tools/add_user.py             add / change / remove logins
static/                       web UI (index.html, app.js, style.css; login.html, login.css, auth.js)
logo/                         logo image (login page, dashboard top left)
background/                   login-page picture (+ optional credit.txt)
data/                         created on first start: cashflow.db (runs), users.json, .session_secret — local, never shared
```


CASH FLOW FORECAST WITH ML  -  QUICK START (Excel only, no Zoho API, no dashboard)

1. Unzip this folder anywhere (e.g. Desktop).
2. Double-click  run_forecast.bat
   - first run: creates the environment, installs packages, trains the ML model (about 2-3 minutes total)
   - next runs: about 20 seconds
3. The Excel files appear in the  output  folder:
     13-Week_Cash_Outlook_<date>.xlsx          <- the one to present (next ~3 months = the reliable part)
     Cash_Flow_Forecast_<date>_ML.xlsx          <- full 52 weeks, same format, ML-timed receipts
     Cash_Flow_Forecast_<date>.xlsx             <- old fixed-rule forecast (for comparison)
     Cash_Flow_Forecast_<date>_ML_range.xlsx    <- low / median / high range + lines ML moved

Data already inside:
  data\snapshot_2026-10-16_from_db.json   latest Zoho data (pulled 12 Oct 2026, week 1 = Fri 16 Oct 2026)
  data\snapshot_2026-09-25_from_exports.json   earlier sample
  ml_data\Zoho_history_2021-10-01_to_2026-10-07.xlsx   5-year history used to train the model

New dates: new Zoho data is NOT fetched automatically. Put a newer snapshot in the data folder
(or build one from Zoho export files: python tools\make_forecast.py --exports "folder" --date YYYY-MM-DD --ml both --outlook --bands).
run_forecast.bat uses the newest data\snapshot_*.json by name unless you pass one:  run_forecast.bat data\snapshot_xxx.json
Refresh the ML model monthly: replace the file in ml_data with a newer Zoho_history_*.xlsx, delete data\ml_models, run again.

Reliability: weeks 1-13 only. After that the forecast rests on fixed assumptions. Full explanation: ML_GUIDE.md
The dashboard (start.bat) is optional and not needed for these files.