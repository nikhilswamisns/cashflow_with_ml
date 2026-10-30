"""Export Zoho Books history (default: the last 365 days) to one Excel file. READ-ONLY: only GET calls.

    python tools\\export_history.py                          last 365 days up to today
    python tools\\export_history.py --days 730               last 2 years
    python tools\\export_history.py --from 2025-10-01 --to 2026-09-30
    python tools\\export_history.py --only invoices,bills    just some datasets

Run it from the app folder with the venv active (same .env as the app). The file is written to
exports\\Zoho_history_<from>_to_<to>.xlsx: one sheet per dataset (all statuses, paid and unpaid, by document date)
plus a "Summary" sheet with the pull time, the date range and the record count per dataset.

Datasets: invoices, customer payments, credit notes, sales orders, bills, vendor payments, vendor credits,
purchase orders, expenses, bank and card account transactions (one sheet, every bank/card account).
It does not change the forecast, the runs database or anything in Zoho. The file holds company data: keep it
out of zips and emails like .env.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import dotenv
    dotenv.load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Font  # noqa: E402

from zoho.client import ZohoAPIError, ZohoClient  # noqa: E402
from zoho.fetch import _fetch_all_pages  # noqa: E402

# (sheet name, endpoint, list key, date field)
DATASETS = [
    ("invoices", "invoices", "invoices", "date"),
    ("customer payments", "customerpayments", "customerpayments", "date"),
    ("credit notes", "creditnotes", "creditnotes", "date"),
    ("sales orders", "salesorders", "salesorders", "date"),
    ("bills", "bills", "bills", "date"),
    ("vendor payments", "vendorpayments", "vendorpayments", "date"),
    ("vendor credits", "vendorcredits", "vendorcredits", "date"),
    ("purchase orders", "purchaseorders", "purchaseorders", "date"),
    ("expenses", "expenses", "expenses", "date"),
]
BANK = "bank transactions"


def _scalar(v):
    return v if isinstance(v, (str, int, float, bool)) or v is None else str(v)


def _in_range(rec: dict, field: str, lo: date, hi: date) -> bool:
    d = str(rec.get(field) or rec.get("transaction_date") or "")[:10]
    return bool(d) and lo.isoformat() <= d <= hi.isoformat()


def _pull(client: ZohoClient, endpoint: str, key: str, field: str, lo: date, hi: date, extra: dict | None = None):
    # Zoho list filters by document date; rows are also filtered here, so an ignored filter cannot widen the range.
    params = {"date_start": lo.isoformat(), "date_end": hi.isoformat(), **(extra or {})}
    try:
        rows = _fetch_all_pages(client, endpoint, key, params=params)
    except ZohoAPIError:
        rows = _fetch_all_pages(client, endpoint, key, params=extra or {})
    return [r for r in rows if _in_range(r, field, lo, hi)]


def _bank(client: ZohoClient, lo: date, hi: date) -> list[dict]:
    out = []
    for acc in client.get("bankaccounts").get("bankaccounts", []):
        params = {"account_id": acc.get("account_id"), "date.start": lo.isoformat(), "date.end": hi.isoformat(),
                  "filter_by": "Status.All"}
        try:
            rows = _fetch_all_pages(client, "banktransactions", "banktransactions", params=params)
        except ZohoAPIError as e:
            print(f"   {acc.get('account_name')}: failed ({e})", flush=True)
            continue
        for r in rows:
            if r.get("account_id") and str(r.get("account_id")) != str(acc.get("account_id")):
                continue
            if _in_range(r, "date", lo, hi):
                out.append({"bank_account": acc.get("account_name"), "bank_account_type": acc.get("account_type"), **r})
    return out


def _sheet(wb: Workbook, title: str, rows: list[dict]) -> None:
    ws = wb.create_sheet(title[:31])
    cols: list[str] = []
    for r in rows:
        for k, v in r.items():
            if k not in cols and not isinstance(v, (list, dict)):
                cols.append(k)
    first = [c for c in ("bank_account", "date", "transaction_date") if c in cols]
    cols = first + [c for c in cols if c not in first]
    ws.append(cols or ["(no records)"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append([_scalar(r.get(c)) for c in cols])
    ws.freeze_panes = "A2"


def main() -> int:
    ap = argparse.ArgumentParser(description="Export Zoho Books history to Excel (read-only).")
    ap.add_argument("--days", type=int, default=365, help="days back from --to (default 365)")
    ap.add_argument("--from", dest="date_from", help="start date YYYY-MM-DD (overrides --days)")
    ap.add_argument("--to", dest="date_to", help="end date YYYY-MM-DD (default today)")
    ap.add_argument("--only", help="comma list of datasets, e.g. invoices,bills,bank")
    ap.add_argument("--out", help="output .xlsx path")
    a = ap.parse_args()

    hi = date.fromisoformat(a.date_to) if a.date_to else date.today()
    lo = date.fromisoformat(a.date_from) if a.date_from else hi - timedelta(days=a.days)
    if lo > hi:
        print("--from is after --to")
        return 2
    want = {w.strip().lower() for w in a.only.split(",")} if a.only else None

    def wanted(name: str) -> bool:
        return want is None or any(w in name for w in want)

    out = Path(a.out) if a.out else ROOT / "exports" / f"Zoho_history_{lo.isoformat()}_to_{hi.isoformat()}.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)

    client = ZohoClient()
    print(f"Zoho history export {lo} to {hi} (org {client.org_id}, read-only)", flush=True)
    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    counts = []
    for title, endpoint, key, field in DATASETS:
        if not wanted(title):
            continue
        print(f" - {title}...", flush=True)
        try:
            rows = _pull(client, endpoint, key, field, lo, hi)
        except ZohoAPIError as e:
            print(f"   failed: {e}", flush=True)
            counts.append((title, "FAILED", str(e)))
            continue
        _sheet(wb, title, rows)
        counts.append((title, len(rows), ""))
        print(f"   {len(rows)}", flush=True)
    if wanted(BANK):
        print(f" - {BANK} (every bank and card account)...", flush=True)
        try:
            rows = _bank(client, lo, hi)
            _sheet(wb, BANK, rows)
            counts.append((BANK, len(rows), ""))
            print(f"   {len(rows)}", flush=True)
        except ZohoAPIError as e:
            counts.append((BANK, "FAILED", str(e)))

    summary.append(["Zoho Books history export (read-only)"])
    summary["A1"].font = Font(bold=True, size=13)
    summary.append(["Organisation", str(client.org_id)])
    summary.append(["Date range (document date)", f"{lo.isoformat()} to {hi.isoformat()}"])
    summary.append(["Pulled at (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")])
    summary.append([])
    summary.append(["Dataset", "Records", "Note"])
    for c in summary[summary.max_row]:
        c.font = Font(bold=True)
    for row in counts:
        summary.append(list(row))
    summary.column_dimensions["A"].width = 30
    wb.save(out)
    print(f"Saved {out}")
    return 0 if all(c[1] != "FAILED" for c in counts) else 1


if __name__ == "__main__":
    sys.exit(main())
