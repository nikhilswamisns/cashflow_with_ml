# Cash Flow Forecasting Engine — Setup Guide

> **For:** whoever installs and runs the software (finance PC or a server).
> Day-to-day use of the screens is in [README.md](README.md).

---

## Contents
1. [How it fits together](#1-how-it-fits-together)
2. [First-time setup on Windows (step by step)](#2-first-time-setup-on-windows-step-by-step)
3. [Connecting Zoho Books (read-only)](#3-connecting-zoho-books-read-only)
4. [Updating to a new version](#4-updating-to-a-new-version)
5. [Data, archive and backups](#5-data-archive-and-backups)
6. [Running on a server (optional)](#6-running-on-a-server-optional)
7. [Scheduled weekly sync (optional)](#7-scheduled-weekly-sync-optional)
8. [Environment variables (`.env`)](#8-environment-variables-env)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. How it fits together

```
Browser  http://localhost:8000/ui   (dashboard, matrix, buttons)
   │
   ▼
Local server (FastAPI / Uvicorn, started by start.bat)
   ├── /api/...                     commands the UI calls  (/docs lists them)
   ├── app/engine/v10_engine.py     forecast engine (Version 10 rules, 45 weeks)
   ├── app/output/v10_exporter.py   Excel export on app/templates/v10_template.xlsx
   ├── app/output/zoho_archive.py   archive folder per sync (+ every export)
   ├── app/config/forecast_rules.json
   ├── data/cashflow.db             runs database (SQLite)
   └── zoho/                        Zoho Books client — READ-ONLY pulls
                    │
                    ▼
            Zoho Books API (org 695133731)
```

* Python 3.9+ (3.11 recommended). Packages: `requirements.txt` (FastAPI, Uvicorn, openpyxl, pandas, requests, python-dotenv …).
* The server runs on the user's own PC; the browser page and the server talk over `localhost`.
* The forecast **only reads** from Zoho. Nothing is created, changed or deleted in Zoho.
* The dashboard charts load Chart.js from the internet (cdn.jsdelivr.net); everything else works offline except the Zoho sync.

---

## 2. First-time setup on Windows (step by step)

1. **Install Python** from python.org (3.11). On the first installer screen tick **"Add python.exe to PATH"**.
   Check in a Command Prompt: `python --version`.
2. **Unzip the project**, e.g. to `C:\Users\<you>\cashflow\cashflow-2`.
3. *(Recommended)* create a virtual environment in the project folder:
   ```cmd
   cd "C:\Users\<you>\cashflow\cashflow-2"
   python -m venv .venv
   .venv\Scripts\activate
   ```
   `start.bat` uses whichever `python` is active; activate `.venv` first if you created one.
4. **Create `.env`**: copy `.env.example` to `.env` and fill in the Zoho values (section 3).
5. **Start**: double-click `start.bat` (or run it from the Command Prompt). It installs `requirements.txt` and
   starts the server. Keep this window open — closing it stops the software. Messages and warnings appear here.
6. **Open** `http://localhost:8000/ui`. The Zoho status light in the sidebar should turn green
   ("Zoho connected · org 695133731").
7. **First forecast**: pick the Friday in **Week 1 from**, click **🔄 Sync Zoho**, then **⬇ Export**.

---

## 3. Connecting Zoho Books (read-only)

You need four values in `.env`: `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`, `ZOHO_ORG_ID`.

1. Sign in to **https://api-console.zoho.com** with the Zoho account that has access to the Gutster Tools books.
   Use the console for your Zoho data centre (`.com` for US accounts; `.in`, `.eu` … otherwise — then also set
   `ZOHO_ACCOUNTS_URL` and `ZOHO_API_BASE_URL` to the same domain).
2. **Add Client → Self Client → Create.** Copy the **Client ID** and **Client Secret** into `.env`.
3. In the Self Client open **Generate Code** and paste these read-only scopes:
   ```text
   ZohoBooks.invoices.READ,ZohoBooks.salesorders.READ,ZohoBooks.purchaseorders.READ,ZohoBooks.bills.READ,ZohoBooks.banking.READ,ZohoBooks.accountants.READ,ZohoBooks.settings.READ,ZohoBooks.expenses.READ
   ```
   Time duration 10 minutes, any description → **Create** → choose the Gutster Tools organisation → copy the code
   (`1000.xxxx…`). The code expires in 10 minutes — do the next step right away.
4. Exchange the code for the permanent refresh token (in the project folder):
   ```cmd
   python -m zoho.auth --exchange 1000.xxxx...
   ```
   Put the printed refresh token in `.env` as `ZOHO_REFRESH_TOKEN`.
5. Organisation id: `python -m zoho.client --list-orgs` → put the Gutster Tools id (695133731) in `ZOHO_ORG_ID`.
6. Check everything: `python zoho\verify_connection.py`. It runs read-only calls (invoices, sales orders, POs, bills,
   bank and card accounts, a snapshot test) and saves `data\last_snapshot.json`.

Why each scope: invoices / sales orders / POs / bills = the forecast lines; **banking** = bank and card balances and card
transactions; **accountants** = chart of accounts (Stripe Clearing balance); **settings** = organisation check
(status light); **expenses** = connection test.

> Keep `.env` private: it holds the client secret and refresh token. Never email it or include it in a zip.
> If it leaks, delete the Self Client's token in the API console and generate a new one.

---

## 4. Updating to a new version

1. Stop the server (close the `start.bat` window, or Ctrl+C in it).
2. Unzip the update **over** the project folder and allow it to overwrite. Updates contain program files only
   (same paths as before).
3. Start `start.bat` again and refresh the browser with **Ctrl+F5** (loads the new page, not the cached one).

Never overwritten by an update: `.env`, `.venv`, `data\cashflow.db`, `zoho_data_archive\` (or your
`ZOHO_ARCHIVE_DIR`). If you move to a completely new folder, copy those across yourself.

If an update changes `app\config\forecast_rules.json`, any local edits you made to that file (e.g. manual entries or
adjustments) must be made again — check the file after updating.

---

## 5. Data, archive and backups

| What | Where | Notes |
|---|---|---|
| Runs database | `data\cashflow.db` | every sync (run), its Zoho snapshot and opening-cash overrides. Change with `DATABASE_PATH`. |
| Zoho data archive | `zoho_data_archive\` (or `ZOHO_ARCHIVE_DIR`) | one folder per sync: `Zoho_data.xlsx`, `zoho_snapshot.json`, `forecast_rules.json`, `manifest.json`, and every export of that run |
| Rules | `app\config\forecast_rules.json` | statuses, exclusions, cash accounts, opening-cash adjustments, manual entries, parent orders, card cycle, Overview open items |
| Template | `app\templates\v10_template.xlsx` | General Info and Expense Assumptions values are read by the engine |
| Secrets | `.env` | never share |

**Backups:** copy `data\cashflow.db`, the archive folder and `.env` somewhere safe (e.g. weekly). Any archived run can
be rebuilt with **🔁 Re-run from archive** using its `zoho_snapshot.json`, even if the database is lost.

The archive folder can be on another drive or a shared / OneDrive folder
(`ZOHO_ARCHIVE_DIR=D:\Finance\Gutster\Cashflow Zoho Archive`). The Windows user running `start.bat` needs write
access there; if it cannot be written the sync and export still work, and the reason is shown in the `start.bat` window.

---

## 6. Running on a server (optional)

Only needed if several people should use one shared instance. The **📂 Open archive folder** button opens Explorer on the
machine running the server, so on a server it just shows the folder path.

**Linux (systemd)** — `/etc/systemd/system/cashflow.service`:
```ini
[Unit]
Description=Cash Flow Forecasting Engine
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/cashflow-2
EnvironmentFile=/home/ubuntu/cashflow-2/.env
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
`sudo systemctl daemon-reload && sudo systemctl enable --now cashflow`. Use **1 worker**: the database is SQLite.

**Docker**: `docker compose up -d` (the compose file maps `data/`, `zoho_data_archive/` and `.env` into the container);
logs with `docker compose logs -f`.

**HTTPS / domain**: put Nginx in front (`proxy_pass http://127.0.0.1:8000;`, `proxy_read_timeout 300s;` — a Zoho sync
takes a few minutes) and add a certificate with Certbot. The app has no login of its own: only expose it inside the
company network or behind a VPN / access control.

**External database** (PostgreSQL etc.) is not supported out of the box: `app/db.py` uses SQLite. Pointing it at
another database requires code changes; `DATABASE_PATH` only moves the SQLite file.

---

## 7. Scheduled weekly sync (optional)

The server must be running. Example: every Saturday 09:00, build the forecast for the Friday just ended.

**Windows (Task Scheduler)** — action *Start a program*:
```text
Program:   curl.exe
Arguments: -s -X POST "http://localhost:8000/api/forecast/sync-zoho-live"
```
(With no date, week 1 is the Friday on or before today.) Export from the UI afterwards, or call
`http://localhost:8000/api/runs/<run_id>/export/xlsx`; each export is saved in the archive folder.

**Linux (cron)**:
```bash
0 9 * * 6 curl -s -X POST http://localhost:8000/api/forecast/sync-zoho-live > /dev/null
```

---

## 8. Environment variables (`.env`)

| Variable | Required | Description |
|---|---|---|
| `ZOHO_CLIENT_ID` | Yes | Self Client ID (Zoho API Console) |
| `ZOHO_CLIENT_SECRET` | Yes | Self Client secret |
| `ZOHO_REFRESH_TOKEN` | Yes | Permanent refresh token (section 3) |
| `ZOHO_ORG_ID` | Yes | Zoho Books organisation id (Gutster Tools: 695133731) |
| `ZOHO_ACCOUNTS_URL` | Optional | `https://accounts.zoho.com` (default; change for other data centres) |
| `ZOHO_API_BASE_URL` | Optional | `https://www.zohoapis.com/books/v3` (default) |
| `ZOHO_ARCHIVE_DIR` | Optional | Archive location: absolute path, or relative to the project folder. Default `zoho_data_archive` |
| `DATABASE_PATH` | Optional | Location of the SQLite database. Default `data/cashflow.db` |

Restart `start.bat` after changing `.env`.

---

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Status light red: **"invalid_client"** | Client ID/secret wrong, or the Self Client was made in another data centre than `ZOHO_ACCOUNTS_URL`. |
| **"invalid_code"** when exchanging | The grant code expired (10 min) or was already used — generate a new one. |
| **Zoho error code 57** / "not authorized" | A scope is missing from the refresh token. Generate a new code with all scopes in section 3 and exchange again. |
| Stripe Clearing missing from opening cash (warning in the `start.bat` window) | Refresh token lacks `ZohoBooks.accountants.READ` — regenerate with the full scope list. |
| **"Address already in use"** / port 8000 busy | Another copy is running. Close it, or on Windows: `for /f "tokens=5" %a in ('netstat -aon ^| findstr :8000') do taskkill /f /pid %a` |
| `python` not recognised | Python not on PATH — reinstall with "Add python.exe to PATH" ticked. |
| Page looks old after an update | Hard refresh: **Ctrl+F5**. |
| Charts on the dashboard are empty | No internet access to cdn.jsdelivr.net (Chart.js). Figures, matrix and export still work. |
| Sync takes several minutes | Normal: it reads the details of every open invoice, order, PO and bill. Do not click again while it runs. |
| Garbled characters (e.g. "â€”") in text | An old version reading files without UTF-8 — update to the latest version. |
| Export shows blanks in some viewers | Open the file in Excel and save once; Excel then stores the calculated values. |
| "No archive folder for this run" | Runs synced before the archive feature get one on their first export. |

Health checks: `http://localhost:8000/docs` (all API commands), `python zoho\verify_connection.py` (Zoho, read-only),
`python -m pytest tests/ -q` (51 pass; 4 skipped without the 14 Aug sample files).
