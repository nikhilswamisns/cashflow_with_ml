"""Make the cash-flow Excel file directly - no dashboard, no server, no Zoho API.

Same engine and the same Excel layout/template as the dashboard's  "Export"  button.

  A) from Zoho EXPORT files you downloaded (folder with AR_Aging..., Invoice.csv, Sales_Order.xlsx, ... see
     tools/snapshot_from_exports.py for the list):
       python tools\\make_forecast.py --exports "C:\\path\\to\\exports_folder" --date 2026-10-09

  B) from a snapshot .json that already exists (e.g. data\\snapshot_2026-09-25_from_exports.json):
       python tools\\make_forecast.py --snapshot data\\snapshot_2026-09-25_from_exports.json

Options
  --ml on|off|both   on  = ML-timed payment weeks (default)          off = your old fixed rules only
                     both = writes both files so you can compare
  --bands            also write a small  ..._ML_range.xlsx  with the P10/P50/P90 ending-cash range and the lines ML moved
  --outlook          also write  13-Week_Cash_Outlook_<date>.xlsx : a clean next-13-weeks (about 3 months) summary with a
                     chart, rules vs ML ending cash and the P10-P90 range. This is the part where ML is most reliable.
  --weeks N          length of that outlook in weeks (default 13)
  --share            also write  ..._ML_SHARE.xlsx : the full 52-week ML workbook with a "READ ME - Reliability" sheet first and
                     weeks 1-13 / weeks 14-52 labelled on the Cash Flow Model sheet, ready to send to someone else
  --out FOLDER       where to save (default: the 'output' folder in the project)

Files written:  Cash_Flow_Forecast_<date>.xlsx        (rules only - same name as before)
                Cash_Flow_Forecast_<date>_ML.xlsx     (with ML timing)
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


def friday_on_or_before(d: date) -> date:
    return d - timedelta(days=(d.weekday() - 4) % 7)


def load_snapshot(a) -> dict:
    if a.snapshot:
        return json.loads(Path(a.snapshot).read_text(encoding="utf-8"))
    if not a.exports:
        sys.exit("Give --exports <folder> (with --date) or --snapshot <file.json>. See --help.")
    from snapshot_from_exports import build
    run_date = friday_on_or_before(date.fromisoformat(a.date)) if a.date else friday_on_or_before(date.today())
    print(f"Reading Zoho export files from {a.exports}  (week 1 = Friday {run_date})")
    return build(Path(a.exports), run_date)


def build_forecast(snap: dict, ml_on: bool):
    from app.engine.v10_engine import RULES, V10Engine
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    rules.setdefault("ml", {})["enabled"] = ml_on
    f = V10Engine(snap, rules=copy.deepcopy(rules)).run()
    warn = [e for e in f.exceptions if str(e).startswith("ML timing")]
    if ml_on and warn:
        sys.exit("ERROR: " + warn[0] + "\nTrain the model first:  python tools\\train_ml.py")
    return f


def write_bands(f, path: Path) -> None:
    from openpyxl import Workbook
    from app.ml.montecarlo import cash_bands
    mc = (f.rules.get("ml") or {}).get("montecarlo", {})
    b = cash_bands(f, simulations=int(mc.get("simulations", 2000)), seed=int(mc.get("seed", 42)),
                   party_correlation=float(mc.get("party_correlation", 0.5)))
    wb = Workbook()
    ws = wb.active
    ws.title = "Ending cash range"
    ws.append(["Week ending", "Ending cash (ML timing)", "P10 (payments later)", "P50", "P90 (payments earlier)"])
    for i, w in enumerate(b["weeks"]):
        ws.append([w, b["deterministic"][i], b["p10"][i], b["p50"][i], b["p90"][i]])
    ws.append([])
    ws.append([b["note"]])
    for col, width in zip("ABCDE", (14, 24, 22, 14, 24)):
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=2, min_col=2, max_col=5):
        for c in row:
            c.number_format = '#,##0;[Red]-#,##0'
    ws2 = wb.create_sheet("Lines moved by ML")
    ws2.append(["Type", "Reference", "Customer / vendor", "Amount", "Week in forecast", "Expected date", "Earliest likely (P10)",
                "Latest likely (P90)", "Shift vs fixed rule (days)"])
    rows = [r for r in f.revenue + f.cogs if r.ml]
    rows.sort(key=lambda r: -abs(r.amount * r.ml["shift_days"]))
    for r in rows:
        ws2.append([r.source, r.ref, r.party, r.amount, r.week, r.ml["p50"], r.ml["p10"], r.ml["p90"], r.ml["shift_days"]])
    for col, width in zip("ABCDEFGHI", (22, 16, 32, 14, 16, 14, 18, 18, 20)):
        ws2.column_dimensions[col].width = width
    wb.save(path)


ROW_OPEN, ROW_REV, ROW_COGS = 4, 15, 21
ROWS_OPEX = (33, 48, 61, 73, 84, 91)          # operations, marketing, selling, finance & admin, IT, non-operating
ROWS_BORROW = (94, 95, 96)                    # credit card payments, loan repayments, credit card charges
ROW_END = 98


def write_outlook(rules_f, ml_f, path: Path, weeks: int = 13) -> None:
    """Clean next-N-weeks summary: values come straight from the engine (same numbers as the Excel model sheet)."""
    from openpyxl import Workbook
    from openpyxl.chart import LineChart, Reference
    from openpyxl.styles import Alignment, Font, PatternFill
    from app.ml.montecarlo import cash_bands

    n = min(weeks, len(ml_f.fridays))
    V = ml_f.values
    g = lambda row, i: float(V.get(row, [0] * 60)[i] or 0)
    mc = (ml_f.rules.get("ml") or {}).get("montecarlo", {})
    b = cash_bands(ml_f, simulations=int(mc.get("simulations", 2000)), seed=int(mc.get("seed", 42)),
                   party_correlation=float(mc.get("party_correlation", 0.5)))
    wb = Workbook()
    ws = wb.active
    ws.title = f"{n}-Week Outlook"
    bold = Font(bold=True)
    head = PatternFill("solid", fgColor="DDEBF7")
    ws["A1"] = f"Cash outlook - next {n} weeks (about {round(n / 4.345)} months), week 1 = Friday {ml_f.run_date:%d %b %Y}"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = ("Payment timing of open invoices / sales orders is learned from the 5-year Zoho history. Ending cash with ML timing is the main line; "
                "the range shows how much it moves if payments come earlier or later than expected.")
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells("A2:L2")
    ws.row_dimensions[2].height = 32
    cols = ["Week", "Week ending (Fri)", "Receipts", "Inventory / COGS paid", "Operating expenses", "Loan & card payments",
            "Net cash flow", "Ending cash (with ML)", "Median case (P50)", "Low case (P10)", "High case (P90)", "Ending cash (old fixed rules)"]
    for j, c in enumerate(cols, 1):
        cell = ws.cell(4, j, c)
        cell.font = bold
        cell.fill = head
        cell.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
    ws.row_dimensions[4].height = 34
    for i in range(n):
        rev, cogs = g(ROW_REV, i), g(ROW_COGS, i)
        opex = sum(g(r, i) for r in ROWS_OPEX)
        borrow = sum(g(r, i) for r in ROWS_BORROW)
        end = g(ROW_END, i)
        ws.append([i + 1, ml_f.fridays[i], rev, -cogs, -opex, -borrow, end - g(ROW_OPEN, i), end, b["p50"][i], b["p10"][i], b["p90"][i],
                   float(rules_f.values[ROW_END][i])])
    last = 4 + n
    ws.cell(last + 2, 1, "Opening cash").font = bold
    ws.cell(last + 2, 3, g(ROW_OPEN, 0))
    lo_i = min(range(n), key=lambda i: g(ROW_END, i))
    ws.cell(last + 3, 1, "Lowest cash point (ML timing)").font = bold
    ws.cell(last + 3, 3, g(ROW_END, lo_i))
    ws.cell(last + 3, 4, f"week {lo_i + 1}  ({ml_f.fridays[lo_i]:%d %b %Y})")
    ws.cell(last + 4, 1, f"Ending cash, week {n}").font = bold
    ws.cell(last + 4, 3, g(ROW_END, n - 1))
    for row in ws.iter_rows(min_row=5, max_row=last + 4, min_col=3, max_col=12):
        for c in row:
            if isinstance(c.value, (int, float)):
                c.number_format = '#,##0;[Red]-#,##0'
    for r in range(5, last + 1):
        ws.cell(r, 2).number_format = "dd-mmm-yy"
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 16
    for col in "CDEFGHIJKL":
        ws.column_dimensions[col].width = 17
    ws.freeze_panes = "C5"

    ch = LineChart()
    ch.title = "Ending cash - next weeks"
    ch.height, ch.width = 9, 24
    for col in (8, 9, 10, 11, 12):
        ch.add_data(Reference(ws, min_col=col, min_row=4, max_row=last), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=2, min_row=5, max_row=last))
    ch.y_axis.number_format = "#,##0"
    ws.add_chart(ch, f"A{last + 7}")

    w2 = wb.create_sheet("Lines moved by ML")
    w2.append(["Type", "Reference", "Customer / vendor", "Amount", "Week in forecast", "Expected pay date", "Earliest likely (P10)",
               "Latest likely (P90)", "Days earlier (-) / later (+) than old rule"])
    for c in w2[1]:
        c.font = bold
        c.fill = head
        c.alignment = Alignment(wrap_text=True)
    horizon_end = ml_f.fridays[n - 1]
    moved = [r for r in ml_f.revenue + ml_f.cogs if r.ml and r.week <= horizon_end]
    moved.sort(key=lambda r: -abs(r.amount * r.ml["shift_days"]))
    for r in moved:
        w2.append([r.source, r.ref, r.party, r.amount, r.week, r.ml["p50"], r.ml["p10"], r.ml["p90"], r.ml["shift_days"]])
    for col, width in zip("ABCDEFGHI", (22, 16, 34, 14, 16, 18, 20, 20, 24)):
        w2.column_dimensions[col].width = width
    for r in range(2, w2.max_row + 1):
        w2.cell(r, 4).number_format = '#,##0.00'
        for c in (5, 6, 7, 8):
            w2.cell(r, c).number_format = "dd-mmm-yy"

    w3 = wb.create_sheet("How reliable is this")
    for line in [
        "How far ahead can this be trusted? (measured on past data, Sep 2025 - Jun 2026, model trained only on data before each test date)",
        "",
        "Weeks 1-8  (months 1-2):   customer invoices - typical error about 5 days; roughly 2 in 3 land within 1 week of the real payment week.",
        "Weeks 5-13 (months 2-3):   sales orders - typical error about 5-7 days; roughly 6 in 10 within 1 week (small sample, uses final ship dates).",
        "After about 13 weeks:      no open invoices/orders exist that far ahead, so ML does not time anything there. Those weeks rest on the fixed",
        "                           assumptions (payroll, rent, card, run-rates) and should be read as a planning estimate.",
        "Already-overdue invoices:  ML does not improve them (both methods are about 27 days off). Use your collections knowledge for these.",
        "",
        "Reading the lines: 'Ending cash (with ML)' puts every invoice on its single most likely date. Late payments have a longer tail than early",
        "ones, so the Median case (P50) is often LOWER than that line in the first weeks. For a prudent view use the Median / Low case columns.",
        "",
        "What this measures: WHEN cash arrives. It does not predict customers who stop paying, disputes, or amounts.",
        "The low/high case is timing risk of the ML-timed invoices and orders only; payroll and other fixed rows are not randomised.",
        "Largest single effect: SERVPRO. History shows it pays about 11 days after invoice, far earlier than the old 45-days-after-ship rule.",
        "Confirm that arrangement with the client before relying on it.",
    ]:
        w3.append([line])
    w3["A1"].font = bold
    w3.column_dimensions["A"].width = 150
    wb.save(path)


def make_shareable(xlsx_bytes: bytes, f, path: Path, ml_weeks: int = 13) -> None:
    """Full-year ML workbook + a READ ME sheet + week labels, so a reader knows only the first 13 weeks are ML-timed/reliable.
    Only empty cells (row 5 of the model sheet) and the new sheet are touched - no formula or number is changed."""
    import io
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter as L

    wb = load_workbook(io.BytesIO(xlsx_bytes))
    n = len(f.fridays)
    k = min(ml_weeks, n)
    end13 = f.fridays[k - 1]
    green, amber = PatternFill("solid", fgColor="C6EFCE"), PatternFill("solid", fgColor="FFE699")
    ws = wb["Cash Flow Model"]
    first, split, last = 3, 3 + k, 3 + n - 1            # column of week 1, of week k+1, of last week
    assert all(ws.cell(5, c).value is None for c in range(first, last + 1)), "row 5 is not empty in this template"
    ws.merge_cells(start_row=5, start_column=first, end_row=5, end_column=split - 1)
    ws.merge_cells(start_row=5, start_column=split, end_row=5, end_column=last)
    a, b = ws.cell(5, first), ws.cell(5, split)
    a.value = f"WEEKS 1-{k} (to {end13:%d %b %Y}): ML-timed receipts - most reliable, use for decisions"
    b.value = f"WEEKS {k + 1}-{n}: assumption-based (flat run-rate), NOT ML - planning estimate only. See 'READ ME - Reliability'"
    for c, fill in ((a, green), (b, amber)):
        c.fill = fill
        c.font = Font(bold=True, size=10)
        c.alignment = Alignment(horizontal="left", vertical="center")
    for col in range(first, split):
        ws.cell(2, col).fill = green
    for col in range(split, last + 1):
        ws.cell(2, col).fill = amber

    lines = [r for r in f.revenue if r.week in f.fridays]
    after = [r for r in lines if f.fridays.index(r.week) >= k]
    rev = f.values[15]
    cogs = f.values[21]
    other = f.values[9]
    rr_week = max(set(round(v) for v in other[k:] if v), key=[round(v) for v in other[k:] if v].count) if any(other[k:]) else 0
    n_ml = sum(1 for r in f.revenue + f.cogs if r.ml)
    ws2 = wb.create_sheet("READ ME - Reliability", 0)
    rows = [
        ("How to read this forecast", "title"),
        (f"Cash flow forecast, {n} weeks. Week 1 = Friday {f.run_date:%d %b %Y}. Receipt timing uses machine learning on the 5-year Zoho history.", ""),
        (f"Zoho data used: open invoices, sales orders, purchase orders and bills as pulled on the run date. ML trained on payment history to Oct 2026.", ""),
        ("", ""),
        (f"SHORT VERSION", "h"),
        (f"Weeks 1-{k} (through {end13:%d %b %Y}):  reliable - ML-timed. Use these weeks for cash decisions.", "g"),
        (f"Weeks {k + 1}-{n}:  planning estimate only. Not ML-timed and not tested. Read as direction, not as a prediction.", "a"),
        ("", ""),
        ("WHY ONLY THE FIRST 13 WEEKS", "h"),
        (f"1. ML only times documents that already exist. It moves open invoices and sales orders to the week it expects the cash, using how each customer "
         f"really paid in the past. Those documents fall due within about 3 months: {len(lines) - len(after)} of {len(lines)} receipt lines in this run land in weeks 1-{k}; "
         f"only {len(after)} line(s) ({sum(r.amount for r in after):,.0f}) land after.", ""),
        (f"2. After week {k}, the receipts shown come from a flat run-rate assumption (Other Resellers, about {rr_week:,.0f} per week), taken from the 13-month P&L - "
         f"not from invoices and not from ML. Weeks {k + 1}-{n} receipts total {sum(rev[k:]):,.0f}, of which {sum(other[k:]):,.0f} is that assumption.", ""),
        (f"3. Costs after week {k} are only what is already in Zoho (purchase orders and bills). Weeks {k + 1}-{n} carry {sum(cogs[k:]):,.0f} of inventory cost against "
         f"{sum(rev[k:]):,.0f} of assumed receipts, so late-year ending cash probably looks better than it will turn out. This applies to the old fixed-rule forecast too.", ""),
        (f"4. Nothing here forecasts future sales, new orders, price changes or customer losses.", ""),
        ("", ""),
        ("EVIDENCE (backtest on past data, Sep 2025 - Jun 2026; model trained only on data before each test date)", "h"),
        ("Forecast of ...                              Typical date error (ML)    Placed within 1 week: ML vs old fixed rule", ""),
        ("Customer invoices, weeks 1-4 ahead            about 5 days                 64%  vs  53%", ""),
        ("Customer invoices, weeks 5-8 ahead            about 5 days                 67%  vs  47%", ""),
        ("Sales orders, weeks 5-13 ahead                about 5-7 days               56-69%  vs  0-13%   (small sample, uses final ship dates)", ""),
        ("Beyond 13 weeks                               not tested - no open invoices/orders that far ahead", ""),
        ("Invoices already overdue                      about 27 days (no better than old rule)", ""),
        ("", ""),
        ("WHAT THE WEEK-1-13 NUMBERS DO NOT COVER", "h"),
        ("Customers who stop paying, disputes and credit notes; amounts (ML changes only the WEEK a receipt lands); payroll, rent, card and other fixed rows (unchanged).", ""),
        ("The old fixed-rule forecast and the ML forecast have the same total receipts - only the timing differs.", ""),
        ("", ""),
        ("ONE ASSUMPTION TO CONFIRM", "h"),
        ("Most of the timing change comes from SERVPRO. History shows it pays about 11 days after the invoice date (stable for 7 quarters), far earlier than the old "
         "45-days-after-ship rule. Confirm with the client that this arrangement is real before relying on it.", ""),
        ("", ""),
        (f"Lines timed by ML in this run: {n_ml}.   Each shows 'ML: expected <date> (P10, P90)' in the Basis column of Revenue Detail.", ""),
        ("A separate file gives a low / median / high range for ending cash (timing risk of the ML-timed lines only).", ""),
    ]
    fills = {"g": green, "a": amber, "h": PatternFill("solid", fgColor="DDEBF7")}
    for i, (text, kind) in enumerate(rows, 1):
        c = ws2.cell(i, 1, text)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if kind == "title":
            c.font = Font(bold=True, size=15)
        elif kind:
            c.font = Font(bold=True)
            c.fill = fills[kind]
    ws2.column_dimensions["A"].width = 150
    for i, (text, kind) in enumerate(rows, 1):
        ws2.row_dimensions[i].height = max(15, 15 * (len(text) // 135 + 1))
    wb.active = 0
    wb.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exports")
    ap.add_argument("--date")
    ap.add_argument("--snapshot")
    ap.add_argument("--ml", choices=["on", "off", "both"], default="on")
    ap.add_argument("--bands", action="store_true")
    ap.add_argument("--outlook", action="store_true")
    ap.add_argument("--weeks", type=int, default=13)
    ap.add_argument("--share", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "output"))
    a = ap.parse_args()

    from app.output.v10_exporter import export_forecast
    snap = load_snapshot(a)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for ml_on in ([False, True] if a.ml == "both" else [a.ml == "on"]):
        f = build_forecast(snap, ml_on)
        name = f"Cash_Flow_Forecast_{f.run_date:%Y-%m-%d}{'_ML' if ml_on else ''}.xlsx"
        path = out / name
        xbytes = export_forecast(f)
        path.write_bytes(xbytes)
        if ml_on and a.share:
            sp = out / f"Cash_Flow_Forecast_{f.run_date:%Y-%m-%d}_ML_SHARE.xlsx"
            make_shareable(xbytes, f, sp)
            print(f"Saved {sp}   (full {len(f.fridays)} weeks + READ ME sheet: weeks 1-13 reliable, rest planning estimate)")
        n_ml = sum(1 for r in f.revenue + f.cogs if r.ml)
        print(f"Saved {path}" + (f"   ({n_ml} lines timed by ML)" if ml_on else "   (fixed rules)"))
        if ml_on and a.bands:
            bp = out / f"Cash_Flow_Forecast_{f.run_date:%Y-%m-%d}_ML_range.xlsx"
            write_bands(f, bp)
            print(f"Saved {bp}")
    if a.outlook:
        rules_f, ml_f = build_forecast(snap, False), build_forecast(snap, True)
        op = out / f"13-Week_Cash_Outlook_{ml_f.run_date:%Y-%m-%d}.xlsx" if a.weeks == 13 else out / f"{a.weeks}-Week_Cash_Outlook_{ml_f.run_date:%Y-%m-%d}.xlsx"
        write_outlook(rules_f, ml_f, op, a.weeks)
        print(f"Saved {op}   (next {a.weeks} weeks - the most reliable part)")
    print("Done. Open the .xlsx in Excel (Excel calculates the formulas on opening; save once if a viewer shows blanks).")


if __name__ == "__main__":
    main()