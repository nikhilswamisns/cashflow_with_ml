# Cash Flow Forecasting Engine — Rebuild Architecture
## Phase 1: File-Ingestion Mode (No Live MCP, No Bank Feed, Bills Gap Deferred)

**Status:** Build specification, ready for implementation by an agentic coding agent.
**Companion sources this spec is derived from:**
1. `Cash_Flow_Forecast_2026-08-14.xlsx` — the live 9-tab workbook this system replaces (structure, formulas, cell-comment audit trail all inspected directly).
2. `Claude_Forecasting_Engine_Architecture.md` — the prior reverse-engineering spec describing the **live-MCP** version of this process (Zoho Books API-driven). Referred to throughout as "**the Reference Doc**."

**What's different about this build vs. the Reference Doc:** The Reference Doc assumes a working Zoho Books MCP connection. This spec assumes **none** — the person building this has historical copies of the workbook and can supply data as files, but has no live API, no bank feed, and is explicitly deferring the Bills Gap problem (Reference Doc §4). Everywhere this spec diverges from the Reference Doc, it says so explicitly and why.

---

## 0. Design Principles (read this before building anything)

1. **Determinism over judgment.** The historical system was AI-operated: a model looked at live data each run and made case-by-case calls (e.g. *"this $32,314.66 isn't supported by any open PO or bill, so I dropped it"* — an actual judgment call found in a cell comment on the source workbook). That is exactly what the Reference Doc's own stated purpose was written to eliminate ("no hidden judgment calls"). **This rebuild must not contain an LLM anywhere in the numeric calculation path.** Every transformation from raw input to forecast number must be a named, testable, deterministic rule (Section 4). Anything that doesn't fit a documented rule becomes a flagged **exception for human review** — it does not get silently resolved.
2. **Same inputs → byte-identical output, forever.** No wall-clock reads inside the calc engine except one explicit `as_of_date` parameter passed in at run time. No randomness. No silent "best guess" fills.
3. **Ingestion is swappable; the calculation core is not.** Everything in Section 2 (adapters) is designed to be replaced later by live Zoho MCP adapters (Phase 2) without touching Sections 4–6 (transform, matrix, output). If a rule in Section 4 needs to change to accommodate file-ingestion, that's a bug in this spec — flag it, don't route around it.
4. **Replicate the *intended* business rule, not the historical bug.** Two defects were confirmed (independently, by both the workbook's own formulas and the Reference Doc) in the historical system: a Gross Profit off-by-one and an Opening Cash dual-write drift. **Do not reproduce either.** Section 9 lists every such correction explicitly, with the reasoning, so nobody mistakes "we fixed it" for "we don't know why the numbers differ from the old file."
5. **Every number carries its own confidence.** Not a tooltip, not a comment — a real field (`data_confidence`) on every line item, all the way to the UI. This is what the Reference Doc recommended for its own (live-MCP) rebuild; it matters even more here, because file-ingestion mode has *more* staleness variance than a live API, not less.

---

## 1. System Overview

```
                    ┌───────────────────────────────────────────┐
                    │   PHASE 1 (this build): File / Manual      │
                    │   PHASE 2 (future, not built now): Zoho MCC│
                    └───────────────────┬─────────────────────── ┘
                                         │  (same adapter interface either way)
                                         ▼
                     ┌──────────────────────────────────┐
                     │   Ingestion & Normalization Layer  │   Section 2
                     │   (per-source adapters →           │
                     │    canonical schema)               │
                     └───────────────┬────────────────────┘
                                      ▼
                     ┌──────────────────────────────────┐
                     │   Canonical Data Store             │   Section 3
                     │   (versioned per run, immutable)   │
                     └───────────────┬────────────────────┘
                                      ▼
                     ┌──────────────────────────────────┐
                     │   Deterministic Transform Engine   │   Section 4
                     │   (date bucketing, COA routing,    │
                     │    tier/basis resolution)          │
                     └───────────────┬────────────────────┘
                                      ▼
                     ┌──────────────────────────────────┐
                     │   Weekly Matrix Consolidation      │   Section 5
                     │   (roll-up + Opening→Ending cash   │
                     │    recursion, corrected formulas)  │
                     └───────────────┬────────────────────┘
                                      ▼
                     ┌──────────────────────────────────┐
                     │   Validation Gate                  │   Section 7
                     └───────────────┬────────────────────┘
                                      ▼
                     ┌──────────────────────────────────┐
                     │   Output Layer                     │   Section 6
                     │   (XLSX export + JSON API + UI)    │
                     └────────────────────────────────────┘
```

**What's in scope for this build:**
- A working ingestion pipeline where every data source is a file upload or a manual entry, not a live API call.
- A "what do you need from me" preflight system that inspects what's already on file, what's missing, and what's stale, and asks for exactly that (Section 8).
- The full deterministic transform + matrix engine, byte-for-byte faithful to the *intended* rules in the source workbook and the Reference Doc — with the two confirmed defects corrected, not replicated.
- An XLSX export that reproduces the original workbook's shape (same 9 tabs, same row layout, same color/comment conventions) so a human user isn't disoriented switching to it.
- A validation/parity harness that can replay historical workbook snapshots and confirm the new engine reproduces them (modulo the intentional corrections).

**Explicitly out of scope for this build (parking lot, not deleted from the design):**
- Any live Zoho MCP adapter implementation (interfaces are defined so this drops in later — Section 2.1).
- Solving the Bills Gap via API access. (Section 4.6 still defines the fallback behavior, because the historical system's own `Reports Needed` checklist already anticipated a manual `Partially Paid Bills` file for exactly this — see the callout in 4.6. That's a nice option to have, not a requirement for this build.)
- Live bank-feed ingestion. Opening Cash is a manual, single-source-of-truth field for Phase 1 (Section 4.7).

---

## 2. Ingestion Layer: Data Source Adapters

### 2.1 Adapter pattern

Every data domain implements the same interface, regardless of where the data actually comes from:

```python
class DataSourceAdapter(Protocol):
    source_name: str                    # e.g. "ar_unpaid_invoices"
    cadence_tier: CadenceTier           # LIVE | PERIODIC | FIXED | MANUAL
    def fetch(self, as_of: date) -> list[CanonicalRecord]: ...
    def last_updated(self) -> datetime | None: ...
    def is_stale(self, as_of: date) -> bool: ...
```

Two implementations of this interface exist conceptually; **only the first is built in this phase**:

| Implementation | Phase | Behavior |
|---|---|---|
| `FileUploadAdapter` | **Phase 1 (build now)** | User uploads a CSV/XLSX matching a documented schema (Section 2.3). Adapter parses, validates, normalizes into `CanonicalRecord`s, stamps `last_updated = upload timestamp`. |
| `ZohoMCPAdapter` | Phase 2 (stub only — do not implement) | Would call the Zoho endpoints listed in Reference Doc §1.1 directly. Leave as an unimplemented class with a `NotImplementedError` and a docstring pointing at Reference Doc §1.2 for the field mapping, so swapping it in later is a scoping exercise, not a redesign. |

**Why this matters for "must work the same every time":** the calculation engine (Sections 4–5) never knows or cares which adapter produced a `CanonicalRecord`. It only sees normalized data plus a confidence tag. This is what makes Phase 2 a drop-in later instead of a rewrite.

### 2.2 Source inventory (maps 1:1 to the original workbook's `Reports Needed` tab)

The original workbook already enumerated the required inputs; this table carries that forward and adds cadence/blocking behavior:

| # | Source name | Feeds | Cadence tier | Blocking? | Phase 1 input method |
|---|---|---|---|---|---|
| 1 | `opening_cash` | Opening Cash Position, week 1 | LIVE (conceptually) | **Yes, run 1 only** | Manual entry (no bank statement available — see 4.7) |
| 2 | `ar_unpaid_invoices` | A/R Collection (row 13), SERVPRO franchisee routing | LIVE | Yes (weeks 1–3 true-up) | File upload |
| 3 | `confirmed_sales_orders` | SERVPRO Corporate Net-45 (row 8) | PERIODIC (weekly ideal) | No — falls back to 0-with-flag if absent | File upload |
| 4 | `purchase_orders` | COGS / Inbound Freight / Inbound Duty (rows 17–19) | LIVE | Yes (weeks 1–3 true-up) | File upload |
| 5 | `partially_paid_bills` | Closes the Bills Gap for matched POs (Section 4.6) | LIVE-equivalent | **No — optional** | File upload, optional |
| 6 | `sales_by_item_6mo` | Other Resellers weekly run-rate (row 9) | PERIODIC (~monthly) | No — holds last value flat | File upload |
| 7 | `amazon_sales_6mo` | Amazon FBA Fees / Seller Fees / Amazon Advertising basis (rows 24, 30, 46) | PERIODIC (~monthly) | No — holds last value flat | File upload |
| 8 | `profit_and_loss` | All `Avg last 6/12 mo` lines in Expense Assumptions; Adjustments/Discount/Freight Billed (rows 10–12) | PERIODIC (~monthly, ideally trailing-12) | No — holds last value flat | File upload |
| 9 | `credit_card_statement` | CC-driven expense overrides for the current statement cycle (Section 4.5) | PERIODIC (monthly, on statement close) | No — falls back to run-rate | File upload |

Row 6 in the original `Reports Needed` tab ("Partially Paid Bills") is genuinely important and is discussed on its own in Section 4.6 — it's the one input that, if supplied, upgrades COGS timing accuracy without needing API access at all.

### 2.3 Per-source schema (Phase 1 file format)

Every schema below is deliberately expressed using the **same field names the Reference Doc documented for the live Zoho API** (Reference Doc §1.2), so that when a `ZohoMCPAdapter` is built in Phase 2, the normalization target doesn't change — only where the fields come from changes.

**`opening_cash`** (manual entry form, not a file)
| Field | Type | Notes |
|---|---|---|
| `amount` | decimal | Sum of CHK + PayPal + Petty Cash, or whatever the user has on hand |
| `as_of_date` | date | |
| `source_note` | string, optional | Free text, e.g. "from QuickBooks dashboard, 8/14" |

**`ar_unpaid_invoices`** (CSV/XLSX, one row per invoice)
| Column | Maps to Zoho field | Required |
|---|---|---|
| Invoice # | `invoice_number` | Yes |
| Customer Name | `customer_name` | Yes |
| Status | `status` (sent / overdue / partially_paid) | Yes |
| Due Date | `due_date` | Yes |
| Balance Due | `balance` (**not** total — see 4.2) | Yes |
| Reference # | `reference_number` | No |

**`confirmed_sales_orders`** (CSV/XLSX, one row per SO)
| Column | Maps to Zoho field | Required |
|---|---|---|
| SO # | `salesorder_number` | Yes |
| Customer Name | `customer_name` | Yes |
| Expected Ship Date | `expected_shipment_date` | Yes |
| Total Amount | `total` | Yes |
| Status | `status` | Yes |
| Linked Invoice # (if since invoiced) | — | No, but if present, the invoice's due date supersedes the SO estimate (Reference Doc §2.3) |

**`purchase_orders`** (CSV/XLSX, one row per PO or PO line)
| Column | Maps to Zoho field | Required |
|---|---|---|
| PO # | `purchaseorder_number` | Yes |
| Vendor Name | `vendor_name` | Yes |
| PO Status | `order_status` (draft / open / closed / cancelled) | Yes |
| Delivery Date | `delivery_date` | No (undated-PO fallback applies — 4.3) |
| PO Date | `date` | Yes (fallback base date) |
| Total Amount | `total` | Yes |
| Payment Terms (days) | `cf_payment_term_formula_unformatted` | No (defaults to 30) |
| Reference # | `reference_number` | No (used for "EFE" freight tagging — 4.3) |

**`partially_paid_bills`** (CSV/XLSX, one row per bill — optional, closes the Bills Gap)
| Column | Maps to | Required |
|---|---|---|
| Bill # | — | Yes |
| Linked PO # | joins to `purchase_orders.purchaseorder_number` | Yes |
| Vendor | — | Yes |
| Balance Due | authoritative balance, supersedes PO `total` when present | Yes |
| Bill Due Date | authoritative due date, supersedes PO-derived due date when present | Yes |
| Status | open / partially_paid | Yes |

**`sales_by_item_6mo`** (CSV/XLSX export of Zoho "Sales by Item")
| Column | Required |
|---|---|
| Item Name | Yes — rows where name contains "SERVPRO" are excluded (Assumptions & Rules rule for row 9) |
| $ Volume | Yes |
| Qty | No |
| Period covered (start/end) | Yes, used to compute weeks-in-period divisor |

**`amazon_sales_6mo`** (CSV/XLSX export of Amazon Seller Central or Zoho Amazon integration)
| Column | Required |
|---|---|
| ASIN | No |
| Sales $ | Yes |
| Units | No |
| Date | Yes |

**`profit_and_loss`** (CSV/XLSX export, by account code, monthly columns)
| Column | Required |
|---|---|
| Account Code | Yes — must match the COA codes in Section 4.1 |
| Account Name | Yes |
| Monthly amounts (one column per month in the export) | Yes |

**`credit_card_statement`** (CSV/XLSX, one row per statement line)
| Column | Required |
|---|---|
| Vendor / Description | Yes |
| Statement Category (as billed — e.g. "Subscriptions", "Drawings") | Yes — needs the mapping table, Section 4.5 |
| Amount | Yes |
| Statement Cycle End Date | Yes |

---

## 3. Canonical Data Model

Store every ingested record exactly as normalized, with provenance, before any transform runs. Suggested Pydantic shape:

```python
class DataConfidence(str, Enum):
    VERIFIED_LIVE = "verified_live"                    # matched a live/file source directly
    MANUAL_ENTRY = "manual_entry"                       # human typed it in (e.g. opening cash)
    PERIODIC_ESTIMATE = "periodic_estimate"              # trailing-average / run-rate, held flat
    FIXED_ASSUMPTION = "fixed_assumption"                # contractual/known fixed $ amount
    ESTIMATE_UNVERIFIED_BILLS_GAP = "estimate_bills_gap"  # closed PO, no matching bill on file
    PLACEHOLDER_NEEDS_TRUEUP = "placeholder_needs_trueup" # newly appended week, no data yet

class CanonicalRecord(BaseModel):
    source: str                 # which adapter produced this
    record_type: str            # "invoice" | "purchase_order" | "sales_order" | ...
    ingested_at: datetime
    as_of_date: date
    confidence: DataConfidence
    payload: dict                # the normalized, source-specific fields
    raw_ref: str | None          # pointer back to source row/file for audit

class Run(BaseModel):
    run_id: UUID
    run_date: date               # forecast_start_friday for this run
    created_at: datetime
    input_snapshot_ids: list[UUID]   # every CanonicalRecord batch used, immutable
    matrix: WeeklyMatrix             # Section 5 output
    validation_result: ValidationResult
```

**Immutability requirement:** once a `Run` is created, its inputs and outputs never change in place. A re-run with updated files creates a **new** `Run`. This is what makes "must be same all the time" auditable — you can always regenerate `Run N` from its recorded `input_snapshot_ids` and get the identical matrix back.

---

## 4. Deterministic Transform Rules

This section ports Reference Doc §§2–4 essentially verbatim, because those rules don't change based on where the data physically comes from — only the exceptions specific to file-ingestion are called out.

### 4.1 Chart of Accounts routing (locked schema)

This table is the single source of truth for which row a given account code lands on. Treat it as seed config data, not something inferred from labels.

| Row range | Section | Code prefix examples |
|---|---|---|
| 7–13 | REVENUES | 1100, 1100.1, 1100.2, 1101, 1102, 1103, (no code) A/R Collection |
| 17–19 | COGS | 3100, 3101, 3102 |
| 23–31 | OPERATIONS | 2101–2109 |
| 37–46 | MARKETING | 5101, 5104, 5107–5109, 5119, 5121–5125 |
| 50–59 | SELLING | 4101–4103, 4105, 4109, 4112, 4115–4116, 4118 |
| 63–71 | FINANCE & ADMIN | 6101–6103, 6106–6109, 6111, 6114 |
| 75–82 | IT | 7102–7104, 7106, 7110–7111, 7113–7114 |
| 86–89 | NON-OPERATING | 9901–9904 |
| 93–95 | BORROWING | (no codes — manual entries only) |

### 4.2 Date bucketing — deliberately mirrored by direction

```python
def bucket_ar_to_week_ending_friday(due_date: date, forecast_start_friday: date) -> date:
    """Cash IN. Lands on the Friday ON-OR-AFTER due_date — money doesn't arrive early."""
    days_until_friday = (4 - due_date.weekday()) % 7   # Mon=0 ... Fri=4
    week_friday = due_date + timedelta(days=days_until_friday)
    return max(week_friday, forecast_start_friday)      # overdue clamp to week 1

def bucket_po_to_week_ending_friday(due_date: date, forecast_start_friday: date) -> date:
    """Cash OUT. Lands on the Friday ON-OR-BEFORE due_date — never assume you can delay past terms."""
    days_since_friday = (due_date.weekday() - 4) % 7
    week_friday = due_date - timedelta(days=days_since_friday)
    return max(week_friday, forecast_start_friday)
```

Applies to: `ar_unpaid_invoices.due_date` and (when present) `confirmed_sales_orders` cash-in estimate → `bucket_ar_to_week_ending_friday`. `purchase_orders` due dates and `credit_card_statement` payment-due dates → `bucket_po_to_week_ending_friday`. **Getting the direction backwards on either shifts cash by up to 6 days — this is the single easiest bug to introduce in a from-scratch rebuild. Write a unit test that asserts the two functions are mirror images of each other before writing anything else.**

Use `balance` (not `total`) for invoice amounts — it already nets out partial payments.

### 4.3 COGS sub-routing and PO due-date resolution

```python
def cogs_category(po: PurchaseOrder) -> str:
    if po.vendor_name == "C.H. Robinson International, Inc." or "EFE" in (po.reference_number or ""):
        return "3101_inbound_freight"
    elif po.vendor_name == "US Customs and Border Protection":
        return "3102_inbound_duty"
    else:
        return "3100_cogs_standard"

def po_due_date(po: PurchaseOrder) -> date:
    base_date = po.delivery_date if po.delivery_date else po.date   # undated-PO fallback
    terms_days = po.cf_payment_term_formula_unformatted or 30       # Net-30 default
    return base_date + timedelta(days=terms_days)
```

This is a **vendor-name allowlist**, not a chart-of-accounts field, matching how the historical system actually behaved. Make this allowlist an editable config table (Section 10), not a hardcoded literal — the Reference Doc flagged the `"EFE"` branch as untested against live data (**INFERRED**), and a config table lets a human correct or extend it without a code change.

### 4.4 Revenue routing: SERVPRO Corporate vs. everyone else

| Customer | Rule | Source |
|---|---|---|
| `"SERVPRO - Corporate"` (exact string match) | Net-45. Cash-in date = `expected_shipment_date + 45 days`. If since invoiced, the invoice's own due date supersedes the SO estimate. | `confirmed_sales_orders`, superseded by `ar_unpaid_invoices` if a matching invoice exists |
| Everyone else, **including SERVPRO franchisees** (e.g. "SERVPRO of East Brunswick / Princeton Meadows") | Standard A/R, 21-day convention, bucketed per 4.2 | `ar_unpaid_invoices` |

Flag as **INFERRED / config, not literal**: this is a maintained allowlist of exactly one string today. A rebuild should store it as a configurable list of corporate-account names, not a hardcoded comparison, since a typo'd or renamed customer record silently misroutes revenue with no error raised.

### 4.5 Credit Card "15th of following month" bridge

```python
def cc_expense_cash_out_week(statement_cycle_end_date: date, forecast_start_friday: date) -> date:
    payment_due_date = date(statement_cycle_end_date.year, statement_cycle_end_date.month, 15) \
                        + relativedelta(months=1)
    return bucket_po_to_week_ending_friday(payment_due_date, forecast_start_friday)  # cash out → same direction as POs
```

- Every category tagged `Credit Card → 15th` (3PL Shipping, Disposal, Misc Operations, Promotional Items, Printing/Mailings, Misc Marketing, SEO, Facebook Ads, Amazon Advertising, Vehicle, Fuel, Travel, Meals & Entertainment, Training, Zoom, Zoho, Shopify, Microsoft, Go Daddy, Phone, Computer/Internet) uses the **actual statement amount** for whichever cycle is currently closed (from the `credit_card_statement` upload), and the **run-rate formula** (Section 4.6 basis table) for every week beyond that.
- **Statement category → COA mapping is not deterministic out of the box** — it's tribal knowledge in the historical system (e.g. statement category "Subscriptions" → account 7103 Microsoft; "Drawings" → account 9904 Owner Disbursements). **Build this as a versioned, editable lookup table from day one** (Section 10), seeded with the mappings observed historically, rather than letting it accumulate as undocumented precedent the way it did in the spreadsheet.

### 4.6 The Bills Gap — deferred, but cheaper to close here than in Phase 2

The Reference Doc's Section 4 describes this as the single largest data gap in the live-MCP system: the Zoho MCP connector has no Bills endpoint, so once a PO becomes `closed` (billed), its true balance and true due date can silently diverge from the PO's own `total`/`delivery_date + terms` calculation, with no way to re-derive them from the PO alone.

**You explicitly said to forget about this for now — and for Phase 1, that's the right call, because it isn't blocking.** But worth knowing: the original workbook's own `Reports Needed` checklist *already* anticipated the fix — item 6, "Partially Paid Bills" (PO type, vendor, expected ship date, payment terms, amount) — as a manually-exportable report. Based on everything actually reviewed in the workbook and the Reference Doc, that report was never actually being supplied in practice; the Bills Gap in the live system is real and unresolved.

Because Phase 1 is file-upload-based anyway, **this report is just another optional file upload** (`partially_paid_bills`, Section 2.3) — no API access required. Implement it as:

```python
def cogs_amount_and_date(po: PurchaseOrder, bills: dict[str, Bill]) -> LineItem:
    matching_bill = bills.get(po.purchaseorder_number)
    if matching_bill is not None:
        return LineItem(amount=matching_bill.balance_due,
                         due_date=matching_bill.due_date,
                         confidence=DataConfidence.VERIFIED_LIVE)
    if po.order_status in ("open", "draft"):
        return LineItem(amount=po.total, due_date=po_due_date(po),
                         confidence=DataConfidence.VERIFIED_LIVE)
    if po.order_status == "closed":
        # No bill on file for a closed PO — this is the gap.
        return LineItem(amount=po.total, due_date=po_due_date(po),
                         confidence=DataConfidence.ESTIMATE_UNVERIFIED_BILLS_GAP)
    return None  # cancelled — excluded entirely
```

If nobody ever uploads a `partially_paid_bills` file, this degrades exactly to the Reference Doc's documented fallback (§4.2) — nothing breaks, nothing is blocked, and the confidence flag tells the truth about it. If someone does upload it later, the gap closes itself with no code change. **Do not build anything more elaborate than this for Phase 1** — no Bills API integration, no reconciliation heuristics. That's explicitly parked.

### 4.7 Opening Cash Position — single source of truth (Phase 1: manual only)

The historical system had Opening Cash Position writable in **two places** (`General Info` and `Cash Flow Model` row 4, week 1) that were expected to always agree and, per both the workbook's own cell comment and the Reference Doc §5.4, **drifted apart** ($151,783.37 vs. $43,986.09 in the run both documents describe).

Phase 1 has no bank feed at all, so this is moot in one sense (there's only ever going to be one manually-entered number) — but the *design* discipline still matters for when Phase 2 adds a live adapter. Build it as:

```python
class OpeningCash(BaseModel):
    amount: Decimal
    as_of_date: date
    entered_by: str
    source: Literal["manual"]   # will grow to include "zoho_bank_feed" in Phase 2

# There is exactly ONE writable field for this in the whole system.
# Every place that displays "Opening Cash Position" (General-Info-equivalent
# settings screen, week-1 matrix cell) reads the same value. There is no
# second field to drift out of sync with, by construction.
```

For week `t > 1`, `Opening_Cash[t] = Ending_Cash[t-1]` — never independently entered (Section 5.3).

---

## 5. Weekly Matrix Consolidation

### 5.1 Rolling window semantics (resolves Reference Doc Appendix Q1)

The Reference Doc flagged this as an open question — the historical file showed 45 dated columns (not a hard-capped 52), plus orphaned staging columns beyond the last dated one. **Resolve it explicitly for this build:** fixed-length rolling window, **default 52 weeks, configurable**. Each refresh:
1. Appends one new week (`last_column_date + 7 days`).
2. Does **not** delete old weeks by default — archive them (they remain queryable via the `Run` history) rather than physically dropping columns. If a strict 52-column *view* is needed for export/parity purposes, that's a display-layer slice over the archived history, not a destructive operation on the canonical data.
3. **New weeks default every cell to `0` with `confidence = PLACEHOLDER_NEEDS_TRUEUP`.** This is not a fallback of last resort — it's the documented, intentional behavior observed in the historical file (its own comments used exactly this pattern: *"Placeholder — new week appended by roll-forward; awaiting live data refresh"*). Never let the engine guess a non-zero value for a week it has no data for.

### 5.2 Per-week vertical roll-up

```python
Total_Revenue[t]      = Sales[t] + SERVPRO[t] + OtherResellers[t] + Adjustments[t] \
                         + DiscountGiven[t] + FreightBilled[t] + ARCollection[t]
Total_COGS[t]          = COGS[t] + InboundFreight[t] + InboundDuty[t]
Total_Operations[t]    = sum(operations_line_items[t])       # rows 23-31
Total_Marketing[t]     = sum(marketing_line_items[t])        # rows 37-46
Total_Selling[t]       = sum(selling_line_items[t])          # rows 50-59
Total_FinanceAdmin[t]  = sum(finance_admin_line_items[t])    # rows 63-71
Total_IT[t]            = sum(it_line_items[t])                # rows 75-82
Total_NonOperating[t]  = sum(non_operating_line_items[t])    # rows 86-89

# CORRECTED — see Section 9.1. Do not shift this to t+1.
Gross_Profit[t]        = Total_Revenue[t] - Total_COGS[t] - Total_Operations[t]
```

### 5.3 Opening → Ending cash recursion (the master formula)

```python
Opening_Cash[1] = opening_cash.amount          # manual entry, Section 4.7
Opening_Cash[t] = Ending_Cash[t - 1]           # for all t > 1

Ending_Cash[t]  = Opening_Cash[t]
                  + Total_Revenue[t] - Total_COGS[t] - Total_Operations[t]
                  - Total_Marketing[t] - Total_Selling[t] - Total_FinanceAdmin[t]
                  - Total_IT[t] - Total_NonOperating[t]
                  + Borrowing[t] - LoanRepayments[t] + PotentialAdjustments[t]
```

**This is a strict linear recursion with no smoothing and no self-correction.** A bad or stale figure in week 1 propagates through every subsequent week undamped. This is why the validation gate (Section 7) exists as a hard checkpoint, not a nice-to-have — there's nothing downstream that will catch an upstream error on its own.

### 5.4 Rule-text vs. actual-implementation discrepancies found in the historical system

Worth carrying forward as explicit open questions rather than silently picking one behavior, because the historical workbook and its stated rules disagree with each other in a few places:

| Line item | Stated rule (`Assumptions & Rules`) | What was actually computed |
|---|---|---|
| Amazon FBA Fees (2102), Seller Fees (2108), Amazon Advertising (5107) | "% of Amazon sales last 6 mo" | A flat trailing-average dollar figure pulled from the P&L export, with no dependency on any forecasted Amazon sales volume at all |
| Operations/EA Salaries add'l ($1,923 biweekly) | Explicitly time-boxed: "July 15, 2026 – August 15, 2026" only | Applied on every biweekly pay week for the entire forecast horizon, indefinitely |
| Office Rent, 1st week of month | $5,000/mo from Sept 2026 onward, every month | Present for every month Sept'26–May'27, but missing for the newest appended month (June 2027) |

**Default behavior for this rebuild: implement the stated rule as written**, not the historical workbook's actual output — i.e., Amazon-related lines should genuinely scale with forecasted Amazon sales percentage, the temporary salary bump should expire on schedule, and rent should apply to every month going forward including newly appended ones. Flag all three in Section 10 as config-driven and explicitly confirmed with whoever owns the assumptions, since "the stated rule" and "what the business actually intends" aren't guaranteed to be the same thing either — this table is a starting point for that conversation, not a final answer.

---

## 6. Output Layer

Both outputs below are generated from the **same** computed `WeeklyMatrix` object — never two separate calculation paths.

### 6.1 XLSX export (continuity with the historical artifact)

Reproduce the original workbook's shape so a human user isn't disoriented:
- Same 9 tab names and order: `Cash Flow Model`, `General Info`, `Assumptions & Rules`, `NewAddtnl Assumptions`, `Reports Needed`, `Revenue Detail`, `COGS Detail`, `Expense Assumptions`, `Credit Card Payments`.
- Same row layout/labels/section groupings and locked row semantics on `Cash Flow Model` (never insert/delete rows programmatically — code that adds an account code appends a new row at the bottom of its section and updates the routing table, it never renumbers).
- Same color convention: blue = input/linked line, black = calculated subtotal.
- Cell-comment-equivalent provenance: instead of freeform AI-authored comments, attach a structured note per cell sourced from `CanonicalRecord.raw_ref` and `confidence` — e.g. *"Sourced from ar_unpaid_invoices upload, 2026-08-14. Confidence: VERIFIED_LIVE."* Same spirit as the historical comments, generated deterministically instead of authored freehand.
- Use the `xlsx` skill's discipline when building this exporter: write real formulas where the original had them (openpyxl, `data_only=False`), never hand-compute a Python value into a formula's cell, and run the recalculation check before treating an export as done.

### 6.2 JSON API + minimal web UI

- `GET /runs/{run_id}/matrix` → full weekly matrix, every cell annotated with `data_confidence`.
- `GET /runs/{run_id}/preflight` → the missing/stale-inputs report (Section 8).
- `POST /runs/{run_id}/inputs/{source_name}` → upload a file for a given source.
- `POST /runs` → kick off a new run from the current canonical data store state.
- Matrix viewer: color each cell by confidence tier (e.g. verified / periodic-estimate / fixed / bills-gap-estimate / placeholder) — an upgrade over the Excel-comment-only provenance the historical system relied on, and a direct answer to the Reference Doc's own recommendation that confidence be "a first-class field... surfaced in the UI, not buried in a tooltip."

---

## 7. Validation Gate

Run this before any output is considered deliverable:

1. **Recursion integrity:** `Opening_Cash[t] == Ending_Cash[t-1]` for every `t > 1`, with zero exceptions.
2. **Single source of truth:** exactly one writable Opening Cash field exists in the data model (structural check, not just a runtime check — this should be nearly impossible to violate given Section 4.7's design, but assert it anyway).
3. **Routing completeness:** every COA code appearing in any uploaded source resolves to exactly one row/section (Section 4.1) — an unrecognized code is a blocking validation failure, not a silently-dropped line.
4. **No silent confidence gaps:** every computed line item has a non-null `data_confidence`. A null here means a code path forgot to tag its output — treat as a bug, not a display nicety to fix later.
5. **Formula-level correctness:** if using openpyxl for the XLSX export, recalculate and confirm zero formula errors (per the `xlsx` skill's own standard) before delivery.
6. **Parity/regression testing against historical snapshots:** if historical `Cash_Flow_Forecast_*.xlsx` files are supplied (see Section 8.3), replay each one's known inputs through the new engine and diff the output against the actual historical file. Every difference must be explainable by one of the corrections in Section 9 — anything else is a regression in the rebuild, not a discrepancy to wave off.

---

## 8. The "Ask For What's Required" Flow

This is the concrete mechanism for the requirement you called out directly: **the system should ask for what it needs, not guess.**

### 8.1 Preflight check

At the start of every run, before any calculation happens:

```python
class InputRequirement(BaseModel):
    source_name: str
    cadence_tier: CadenceTier
    blocking: bool
    last_provided_at: datetime | None
    staleness_threshold_days: int

class PreflightResult(BaseModel):
    missing_blocking: list[InputRequirement]     # run cannot produce a delivery-ready output
    missing_optional: list[InputRequirement]      # run proceeds, uses fallback/held-flat data
    stale: list[InputRequirement]                 # present but past its cadence threshold — warn, don't block
```

The preflight walks the source inventory (Section 2.2) against what's actually on file and produces exactly three buckets. **Blocking items surface as an explicit, specific request** — not a generic "please upload data" message:

> *"Please upload updated A/R Unpaid Invoices — none on file yet. This is required before a run can compute A/R Collection (row 13)."*
> *"Sales by Item (6-month) was last provided 41 days ago; expected cadence is ~monthly. The run will proceed using the held-flat prior figure, flagged PERIODIC_ESTIMATE — upload a refresh if you have one."*

### 8.2 First-run special case: Opening Cash

Since there's no bank statement source in Phase 1, Opening Cash Position is **hard-blocking on the very first run only** (matching the historical workbook's own "must enter first" convention on its yellow-highlighted opening-cash cell). Every subsequent run derives it automatically from the prior run's Ending Cash (Section 5.3) — no repeated manual entry, with an always-available manual override if the person wants to true it up against a real statement later.

### 8.3 Historical file import (uses what you already have)

Since historical snapshots of the workbook are available, build a `HistoricalWorkbookImporter`:
- Parses one or more `Cash_Flow_Forecast_*.xlsx` files (two-pass openpyxl load — formulas and cached values — per the `xlsx` skill's own guidance for reading a model).
- Extracts every underlying data point it can recover (invoice-level rows in `Revenue Detail`, PO-level rows in `COGS Detail`, the `Expense Assumptions` basis figures, cell comments as provenance text) into `CanonicalRecord`s tagged with their original confidence where inferable.
- **Two uses only, deliberately kept separate:**
  1. **Parity/regression testing** (Section 7, item 6) — replay historical inputs, confirm the new engine reproduces historical outputs modulo the corrections in Section 9.
  2. **Backfilling the canonical store's history** so the new system has more than one week of context on day one, instead of starting cold.
  
  **It is not a live input source for new runs** — don't let old snapshots silently satisfy the preflight check for a *current* week's data. A 6-month-old invoice export should never be mistaken for this week's A/R.

---

## 9. Explicit Corrections (do not replicate these from the historical system)

### 9.1 Gross Profit off-by-one

Confirmed independently in both the workbook itself (every one of its ~45 columns wired `Gross_Profit[t] = Revenue[t+1] - COGS[t+1] - Operations[t+1]`) and the Reference Doc (§5.5, which calls it a "confirmed off-by-one bug" and explicitly instructs *"do NOT replicate"*). It never affected the cash recursion (Gross Profit is a display/analysis row only) — but it should be built correctly from day one: `Gross_Profit[t] = Revenue[t] - COGS[t] - Operations[t]` (Section 5.2).

### 9.2 Opening Cash dual-write drift

The historical system had two independently-writable fields expected to always agree, and they didn't ($151,783.37 vs. $43,986.09 in the documented run). Phase 1 design eliminates the second writable field entirely rather than adding a sync check (Section 4.7) — there's nothing to drift if there's only one place to write it.

### 9.3 Rule-text vs. implementation gaps (Section 5.4)

Not "bugs" in the same sense — more like drift between what the assumptions document says and what actually got computed. Listed in 5.4 as config decisions needing explicit confirmation, not silently resolved either direction.

---

## 10. Configuration & Extensibility

Everything below should be **editable config data, not hardcoded Python**, because every one of these was either flagged **INFERRED** in the Reference Doc or observed as tribal knowledge in the historical workbook:

| Config table | Seed with | Why it's config, not code |
|---|---|---|
| Corporate-account allowlist (SERVPRO routing, 4.4) | `["SERVPRO - Corporate"]` | String-match fragile by design; a renamed customer record shouldn't require a code change |
| Freight/duty vendor routing allowlist (4.3) | C.H. Robinson → freight, US Customs and Border Protection → duty, `"EFE"` substring → freight | Reference Doc flagged the EFE branch as untested/INFERRED |
| CC statement category → COA mapping (4.5) | Seed from historical precedent (e.g. "Subscriptions"→Microsoft/7103, "Drawings"→Owner Disbursements/9904) | Was accumulating as undocumented precedent in the spreadsheet; Reference Doc Appendix explicitly asks for this to become "a formal, versioned lookup table" |
| Rolling window length (5.1) | 52 weeks | Reference Doc's own open question — make it a number, not a magic constant |
| Assumption rates: A/R days, biweekly pay anchor date, fixed dollar amounts, tax payment schedule | Copy verbatim from the historical `General Info` / `Assumptions & Rules` / `Expense Assumptions` tabs | These three tabs' *content* is the seed data for this system's config store — don't re-derive them, import them |
| Amazon-% basis, temp salary expiry, rent schedule (5.4) | Implement stated rule; flag as needing explicit sign-off | Rule text and historical behavior disagreed; pick the rule text as default, but don't bury the discrepancy |

---

## 11. Suggested Build Order

1. **Canonical data models** (Section 3) + `FileUploadAdapter` for all 9 sources (Section 2) + manual Opening Cash entry. No calculation yet — just get data in, normalized, versioned.
2. **Deterministic transform engine** (Section 4): date bucketing, COA routing, confidence tagging. Unit-test against the concrete examples already documented in the Reference Doc (e.g. `PO-00280`: delivery 2026-06-30, terms 30 → due 2026-07-30 → clamped to week 8/14; `PO-00294 B`/`C`: undated, PO date 2026-07-27, terms 30 → due 2026-08-26 → bucketed to week-ending 8/21). These are known-correct worked examples — use them as regression tests, not just documentation.
3. **Matrix consolidation + recursion** (Section 5), with the corrected Gross Profit and single-source Opening Cash from the start.
4. **Validation gate** (Section 7).
5. **XLSX exporter** (Section 6.1) — build this early enough to eyeball early runs against the shape you already know from the historical file.
6. **Preflight / "ask for what's required"** (Section 8), including the historical-file importer for parity testing.
7. **JSON API + minimal UI** (Section 6.2).
8. *(Not this phase)* `ZohoMCPAdapter` implementations behind the same interfaces defined in Section 2.1; Bills API integration if/when scope is granted.

---

## Appendix: Open Questions Carried Forward for Product-Owner Sign-Off

(Restated from the Reference Doc where still unresolved, plus what this spec adds.)

1. Rolling window: is 52 weeks the true intended length, or should it be different? (Defaulted to 52, configurable — 5.1.)
2. Is `"EFE"` in a PO's reference number equally authoritative as the C.H. Robinson vendor-name match for freight routing? (Untested against real data either historically or here — 4.3.)
3. Should SERVPRO Corporate-vs-franchise routing become a real flag in the source system (once one exists) instead of a string-match allowlist? (4.4.)
4. Should the Amazon FBA Fees / Seller Fees / Amazon Advertising lines actually be computed as a percentage of forecasted Amazon sales, as the stated rule says — or should the stated rule be updated to match what's actually intended (a flat trailing average)? (5.4.)
5. Should the Operations/EA Salaries temporary bump actually expire on schedule, and should Office Rent apply to every newly appended month automatically? (5.4.)
6. Statement-category → COA mapping (Section 4.5): confirm the seed mappings are correct, and confirm this should be a versioned table going forward.
7. Bills Gap (4.6, deferred): worth actually sourcing a `Partially Paid Bills` export at some point, given it fully closes the gap with zero API dependency — not needed for this build, but worth flagging as a low-effort, high-value future input.
