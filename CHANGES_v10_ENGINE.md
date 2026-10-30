# Engine update — reproduces the v10 canonical (27 Sep 2026)

## What changed
| Area | Before | Now |
|---|---|---|
| Zoho sync | Fetched bills/POs but saved them under names the forecast never read, so it silently used the old "August 31" files | One read-only **snapshot** (`zoho/snapshot.py`) saved with the run; the forecast uses only that run's data |
| Statuses | Confirmed SOs only, no draft invoices, open POs only | As v10: invoices Sent/Overdue/Partially paid (balance) + Draft (total); SOs Confirmed/Partially invoiced/Draft at the **uninvoiced** remainder; POs Issued/Draft/Partially billed at the **unbilled** amount; bills Open/Overdue/Partially paid at balance |
| PO timing | flat +30 days | delivery date (or PO date, UNVERIFIED) + **Zoho supplier Payment Terms** (Assumptions & Rules row 12). PO-00270 Net 90 -> w/e 12/18/26 |
| Opening cash | only a positive checking balance, else an old manual figure | Zoho CHK + PayPal + Petty Cash (negative allowed) + logged manual adjustments (the $250k deposit is in `forecast_rules.json`, shown on General Info B43) |
| Taxes | estimates + actual Sept bills (double) | General Info schedule only; past dates skipped; tax bills listed as excluded |
| Week 1 | hard-coded 8/15 card actuals | same row timing as every other week (v10) |
| Credit cards | monthly estimates on the 15th only | v10 card roll-forward: Block A charges, live Platinum/CORP balances, Block B statements (27th-26th, due 20th), row 93 payments, row 95 add-back; card transactions pulled read-only for the outbound-freight card share and itemization |
| Excel | 14-Aug template, detail sheets stale | v10 layout, all 10 sheets rebuilt from live data, every total is a formula |
| Horizon | 52 weeks | 45 weeks (v10) |
| "Baseline (Aug 31)" | built a 14-Aug run from stale files, demo cash $47,478.95 | disabled |

## Where the rules live
* `app/config/forecast_rules.json` — statuses, vendor/category mapping, exclusions, card cycle, manual cash adjustments, **held-for-client-review** orders, **open items** shown on the Overview.
* `app/templates/v10_template.xlsx` — General Info fixed amounts / tax schedule, Expense Assumptions column E and Revenue Detail B6-B11 are read by the engine (edit them there).

## Run
* Dashboard: **Sync Live from Zoho API** -> **Export Audited Excel**.
* Check the Zoho calls: `python zoho\verify_connection.py` (also saves `data\last_snapshot.json`).
* Offline from Zoho export files: `python tools\snapshot_from_exports.py <folder> 2026-09-25 snap.json`, then POST it to `/api/forecast/run-from-snapshot` (or use /docs).

## Not changed on purpose (open items, see Overview)
Reseller run-rate vs A/R overlap, loans/interest and Duckbill, card statements vs actual spend, COGS after December, SERVPRO timing/1%, expense run-rates, payroll, SO-05927/05926/05928 were held (now forecast - see 29 Sep below).


---

# Updates 28–29 Sep 2026 (fix 7 – fix 14)

| # | Change | Why |
|---|---|---|
| 7 | PO timing: delivery date (or PO date, UNVERIFIED) + Zoho supplier Payment Terms for **every** open PO, delivered or not | Assumptions & Rules row 12 "Supplier terms"; same as the Aug-14 file (PO-00270 due 12/24) |
| 7 | Card statements: the first statement paid is the oldest **closed but unpaid** cycle (run 10/2 pays the 9/26 statement in w/e 10/16) | It was pushed a month late and October's charges were never paid |
| 8 | White text on every navy / blue heading band in the export | Legibility |
| 9 | Zoho data archive per sync (+ every export); `ZOHO_ARCHIVE_DIR` in `.env` | Trace each report to its data |
| 10 | API Docs button | — |
| 11 | Outbound freight: Cash Flow Model row 29 carries the full monthly amount; the card share is added back (row 95) and paid in its statement (row 93) | Version 10 deducted only 78% but added back 22%, so the card share was never paid ($2,302.10/month) |
| 12 | UI matrix mirrors the Excel Cash Flow Model (all rows, Code / Account columns) | — |
| 13 | Opening cash = exactly CHK + PayPal + Petty Cash + **Stripe Clearing** (read from the Zoho chart of accounts); SO-05927 forecast at its remainder after the SO-05859 / SO-05919 partial fills; SO-05926 and SO-05928 forecast | On instruction 29 Sep; listed in the Overview for client approval |
| 14 | UI: sync for a chosen date, Opening Cash (bank balance) box, Re-run from archive, Open archive folder, live Zoho status light, clearer run names | Replace the `/docs` workflow |

Still open for the client: Ops/EA $1,923 period (Expense Assumptions F29 says Jul 15–Aug 15 only), Tradeshow $4,000 July 2027,
reseller run-rate vs open A/R, loans / interest / Duckbill, card statements vs actual spend, COGS after December,
SERVPRO timing and 1%, run-rates, payroll, week 1 already elapsed.

---

# Update 1 Oct 2026 (fix 18)

| # | Change | Why |
|---|---|---|
| 18 | `$250,000` owner-deposit line removed (`opening_cash.manual_adjustments` = empty); General Info row 45 = "Manual adjustment - none"; D4 text updated; a "Resolved" note on the Overview | Deposit posted in Zoho 9/22 (Counter Credit 200,000 + transfer from CRD 4664 50,000), already inside the CHK balance |
| 18 | **Manual entries** (`manual_entries` in `forecast_rules.json`): one-off amounts by Cash Flow Model row and week. Listed in General Info rows 48+ and linked into the Cash Flow Model by formula; shown in the Overview KPIs and "Fixed in this run"; entries before week 1 expire; card / detail / total rows refused. First entry: **$73,000 loan repayment, row 94, w/e 10/02/26** (Ralph email 1 Oct) | One-off amounts were being typed into the Excel by hand, which left General Info and the Overview out of step |

# Update 1 Oct 2026 (fix 19) — Amazon row (client decision, Ralph)

| # | Change | Why |
|---|---|---|
| 19 | **Cash Flow Model row 10 = 1100.3 Amazon** (new). Amazon marketplace customers (name contains "Amazon": Gutster / Staple Popper / Duckbill Amazon USA & Canada) are labelled `Amazon Invoice` / `Amazon Sales Order` in Revenue Detail and feed row 10 by SUMIFS, like SERVPRO; they are no longer in A/R Collection. Amazon sales orders: ship date + 30 days | Ralph, 1 Oct 2026 |
| 19 | **Assumptions & Rules row 7 = 1100.3 Amazon** rule (new); A/R Collection rule now reads "excluding SERVPRO and Amazon" | Same decision, worded like the SERVPRO rule |
| 19 | Row map: every Cash Flow Model row from Adjustments down moves one row (A/R Collection 14, Total Revenue 15, COGS 18–20, Gross Profit 35, Tradeshow 54 (hidden), card payment 94, Loan Repayments 95, card add-back 96, **Ending Cash 98**); Assumptions & Rules rows from A/R Collection down move one row (supplier terms 13, Rent 51, IRS 69, NJ 70). Engine, export, app matrix / dashboard, manual entries (the $73k is now `cfm_row` 95) and tests updated | Insert the new rows without changing any figure |
| 19 | Verified on the 1 Oct Zoho data: every Cash Flow Model cell equals fix 18 one row down, and row 10 + row 14 = the old A/R row; ending cash unchanged; no formula errors | — |

# Update 1 Oct 2026 (fix 20) — Other Resellers from week 5

| # | Change | Why |
|---|---|---|
| 20 | Other Resellers run-rate (Cash Flow Model row 9) is collected **week + 4**, so it first appears in **week 5** (weeks 1–4 = $0); `reseller_run_rate_start_week` = 5; Assumptions & Rules D6 sentence updated | Client, 1 Oct 2026 (was week 4 from 30 Sep). On the 1 Oct data: w/e 10/23 drops $42,185.81, horizon end $630,004.38 |

# Update 1 Oct 2026 (fix 22) — Amazon row re-applied over fix 21

| # | Change | Why |
|---|---|---|
| 22 | Fix 19 Amazon row restored on top of fix 21: Cash Flow Model row 10 = 1100.3 Amazon; Amazon customers (name contains "Amazon") labelled `Amazon Invoice` / `Amazon Sales Order` and **excluded from A/R Collection (row 14)**; Assumptions & Rules row 7 Amazon rule, A/R rule "excluding SERVPRO and Amazon"; Other Resellers from week 5 kept; $73k manual entry in row 95 | Ralph, 1 Oct 2026. Checked on the 1 Oct data: 0 Amazon lines in A/R (Revenue Detail, row 14, app drill-down); row 10 + row 14 = the old A/R row in every week; ending cash unchanged; no formula errors |

# Update 1 Oct 2026 (fix 23) — Refresh & Compare ("Changes Since Run")

| # | Change | Why |
|---|---|---|
| 23 | **🔁 Refresh & Compare** button: a second read-only Zoho pull for the selected run with the same week 1, saved with the run and in `<run archive>\refresh_<date>_<time>\` | The forecast is pulled Thursday evening and sent Friday morning; Zoho moves in between |
| 23 | Export: main sheets stay as the run; new last sheet **"Changes Since Run"** — summary, 13-week ending cash, an exact bridge of the horizon-end change (settled activity vs real changes) and every change by area (opening cash, invoices, SOs, POs, bills, linked lines, cards, manual entries) with status from → to, amounts, weeks and cash effect | Client: show clearly how much the changes move the forecast |
| 23 | App: **Since run** panel on the dashboard; **Run / Refresh / Difference** toggle on the 52-Week Matrix with drill-down of changed cells; refreshed runs marked ↻ in the run list | — |
| 23 | New `app/engine/compare.py`; API `POST /runs/{id}/refresh`, `GET /runs/{id}/compare`, `GET /runs/{id}/matrix?view=`; tests `tests/test_compare.py` | — |

# Update 2 Oct 2026 (fix 24) — card statements at the close, live card share, SO-05927

Found by checking the 10/09 run against the AI-built file (same Zoho data, pulled 10 minutes apart).

| # | Change | Why |
|---|---|---|
| 1 | **First Platinum statement = balance at the cycle close** = live balance less the net charges posted after the close. Those charges now go on the **next** statement (with the CORP residual). New input on Credit Card Payments **B34** ("charges posted after the close"); Block B row 46 opening = B32 + B34; reconciliation B64 = B31 + B32 + B34 (still equals the live card balances, so nothing is lost or counted twice). | The 10/20 statement is $63,812.88, not the live $71,669.69: the $7,856.81 charged 9/27–9/29 is due on 11/20. |
| 2 | **Zoho pull reads card activity from two cycles before the unpaid one up to today** (`zoho/snapshot.py`; `card_cycle` now also has `history_start` and `pulled_to`). | Needed for 1 and 3. |
| 3 | **Outbound freight card share measured live over the last three cycles** (refunds net off, payments ignored). The stored amounts in `forecast_rules.json` are used only for an older snapshot, with a note on the Overview. | The stored history held two old cycles (due 7/15 and 8/15) and missed the 7/27–8/26 cycle. 10/09: share 20% (avg $2,105.10), was 22% ($2,302.10). |
| 4 | **SO-05927 kept.** The parent-order deduction applies only while the parent total still includes the fills. Zoho has since reduced SO-05927 to $61.75, so it is forecast as it stands (w/e 11/13, UNVERIFIED). | The fills were being deducted a second time, dropping the order. |
| 5 | Refresh & Compare lists card transactions from the unpaid cycle onward only. | The earlier cycles are history pulled for the share. |
| 6 | **"Paid / realised since the prior forecast" compares with the last run for an EARLIER week 1** (`get_prior_snapshot`), not just the last fetch. When the prior forecast exists but nothing was paid, the block now says "None — nothing open in the prior forecast (week 1 = …) has been paid since" instead of "No prior forecast on file". | A re-fetch for the same week 1 was taken as the prior forecast, so the block was empty and the message was wrong. |

Older snapshots still work: first statement = live balance (labelled), share from the stored cycles. **Fetch Zoho again** to get the new card data.

Checked on the 10/09 data: revenue identical to before plus SO-05927 $61.75; first statement 63,812.88 and share 2,105.10 (both equal to the AI's live figures); card identity closes; itemization check 0.00; no formula errors. Tests: `tests/test_fix24_cards.py`.

# Update 6 Oct 2026 (fix 26) — 52 weeks, Duckbill repayment

| # | Change | Why |
|---|---|---|
| 1 | **Window 52 weeks** (was 45): Cash Flow Model and Credit Card Payments columns C–BB; `window_weeks` in `forecast_rules.json`. | Client request 6 Oct 2026. |
| 2 | **Duckbill repayment forecast on row 95 (Loan Repayments)**: General Info **row 32** = $3,750/month (new line), paid on the **1st Friday** of each month through **Dec 2027**. An open Duckbill bill in Zoho (vendor "Skagit Valley…", account "Intellectual Property Rights-Payable") is paid on the 1st Friday of the month after its bill date (overdue → week 1) and replaces that month's schedule. The bill is listed in COGS Detail EXCLUDED with the reason "paid on row 95". A bill amount different from B32 is used and flagged. Assumptions & Rules E74 updated; the Overview open item removed; "Fixed in this run" explains it. | Client decision 6 Oct 2026. Before, $3,750/month was in no row. |

Checked on the 10/09 data: week 1 −$135,412.53 (−$3,750: the open 30 Sep bill), lowest point −$249,475.00 w/e 10/16, 13 Duckbill payments in the window (10/09 bill + 1st Fridays 11/06/26 … 10/01/27). No formula errors. Tests: `tests/test_fix26_duckbill.py`.

# Update 6 Oct 2026 (fix 27) — card statement paid early

Found on the 6 Oct pull: the 10/20 Platinum statement ($63,812.88) was paid on 10/04 ($62,875.70). The live balance fell
to $17,270.94, the plausibility check compared the cycle's charges with that lower balance, rejected all card
transactions and fell back to "first statement = live balance" — paying $16,333.76 of next-cycle charges 5 weeks early.

| # | Change |
|---|---|
| 1 | The plausibility check compares the cycle's charges with the balance **at the close** (live − charges since the close + payments since the close), so a statement payment no longer rejects the card data. |
| 2 | First statement (B31) = **still due** = live balance − charges since the close; label and note show "balance at the close X less Y paid since the close". Charges since the close (B34) go on the next statement as before. |
| 3 | Itemization adds "Less paid since the close" and "STILL DUE (row 94)"; the check ties to B31. |
| 4 | If more was paid than the statement, the first statement is 0 and the excess is taken off the next statement (noted). |

Checked on the 6 Oct data: 10/16 statement $937.18 (63,812.88 − 62,875.70); 11/20 statement $48,683.99 (CORP 2,846.10 +
16,333.76 since the close + Block A); card share 20% from 3 live cycles; identity and itemization checks 0.00; no formula
errors. Week 1 −$21,915.99, lowest point −$79,195.61 (w/e 10/16), horizon $611,217.74. Tests in `tests/test_fix24_cards.py`.

# Update 6 Oct 2026 (fix 28) — Amex statement bill in A/P (corrects fix 27)

Found comparing the AI and app forecasts of the 6 Oct pull. The 10/04 "payment" of $62,875.70 on the Platinum card was
not cash: it is Zoho moving the Amex statement into A/P as bill "AMEX Credit Card(04 Oct 2026)", open, due 10/19, posted
to the Business Platinum Card account. Fix 27 treated it as paid, and the bill was also dropped from COGS as a non-COGS
bill, so the $62,875.70 was paid nowhere and cash was overstated by that amount from w/e 10/16.

| # | Change |
|---|---|
| 1 | An open bill posted to the Platinum card account is the **statement still due**: B31 = its balance, paid on the Friday on or before its due date (overdue → week 1; Block B row 45 uses the bill's due date). |
| 2 | Whatever is left on the card beyond the bill (live balance − charges since the close; $937.18 on 6 Oct) goes on the **next** statement with the charges since the close: B34 = live Platinum balance $17,270.94. Flagged in exceptions to check against the Amex statement. |
| 3 | The bill is listed in COGS Detail EXCLUDED with "paid on row 94"; no longer a "non-COGS, run-rate" restatement. |
| 4 | Itemization: balance at the close (Zoho book) → less left on the card beyond the bill → AMEX STATEMENT BILL STILL DUE (row 94); check ties to B31. Row 64 = bill + live Platinum + CORP. |
| 5 | With no open statement bill the fix 27 logic is unchanged (a statement bill already paid in cash is a real payment). |

Checked on the 6 Oct data: matches the AI forecast in every Cash Flow Model cell across 52 weeks. 10/16 statement
$62,875.70; 11/20 statement $49,621.17; week 1 −$21,915.99; lowest point −$141,134.13 (w/e 10/16); 5 negative weeks;
10/01/27 $548,342.04. Test: `tests/test_fix24_cards.py::test_open_amex_statement_bill_is_paid_on_row_94_not_treated_as_paid`.
