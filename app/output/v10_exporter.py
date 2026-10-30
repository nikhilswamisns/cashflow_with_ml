"""Write a Forecast (app/engine/v10_engine.py) into the v10 workbook layout.

The workbook is built on app/templates/v10_template.xlsx so every sheet, row,
column, colour and number format matches the v10 canonical. Static assumption
sheets are kept as they are; the dynamic sheets are rewritten from the forecast:

  Cash Flow Model ....... dates, month bands, every row as a live formula (as v10)
  General Info .......... run date + opening-cash build-up (rows 43-46) + manual entries (rows 48+)
  Revenue Detail ........ weekly receipt blocks (SUMIFS keys: col A source, col F week)
  COGS Detail ........... weekly payment blocks (SUMIFS keys: col C category, col G week)
  Credit Card Payments .. Block A charges, live card inputs, Block B statements, Block C
  Overview .............. bridge, restatements, KPIs, 3-week position, open items
"""
from __future__ import annotations

import io
from copy import copy
from datetime import date
from typing import Optional

import openpyxl
from openpyxl.utils import get_column_letter as L

from app.engine.v10_engine import (CARD_ROWS, COGS_3100, COGS_3101, COGS_3102, TEMPLATE, Forecast, fmt_md,
                                   money)

MONEY = '\\$#,##0.00;"($"#,##0.00\\);\\-'


def _style_of(ws, coord):
    c = ws[coord]
    return {"font": copy(c.font), "fill": copy(c.fill), "border": copy(c.border),
            "alignment": copy(c.alignment), "number_format": c.number_format}


def _apply(cell, st):
    if st:
        cell.font, cell.fill, cell.border = copy(st["font"]), copy(st["fill"]), copy(st["border"])
        cell.alignment, cell.number_format = copy(st["alignment"]), st["number_format"]


def _clear_from(ws, start_row: int) -> None:
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row >= start_row:
            ws.unmerge_cells(str(rng))
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)


class V10Exporter:
    def __init__(self, f: Forecast, comparison=None):
        self.f = f
        self.comparison = comparison
        self.wb = openpyxl.load_workbook(TEMPLATE)
        self.n = len(f.fridays)
        self.cols = [L(3 + i) for i in range(self.n)]

    def export(self) -> bytes:
        self._general_info()
        self._cash_flow_model()
        self._revenue_detail()
        self._cogs_detail()
        self._credit_cards()
        self._overview()
        if self.comparison is not None:
            self._changes_since_run()
        self._legible_headings()
        from openpyxl.workbook.properties import CalcProperties
        self.wb.calculation = CalcProperties(fullCalcOnLoad=True)
        buf = io.BytesIO()
        self.wb.save(buf)
        return buf.getvalue()

    def _legible_headings(self) -> None:
        """White text on every dark-filled cell (navy / blue heading bands), all sheets.

        Only the font colour changes - bold, size and typeface are kept, and no text is touched."""
        for ws in self.wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    fill = c.fill
                    if fill is None or fill.fill_type != "solid" or fill.fgColor is None or fill.fgColor.type != "rgb":
                        continue
                    rgb = str(fill.fgColor.rgb or "")[-6:]
                    try:
                        r, g, b = (int(rgb[k:k + 2], 16) for k in (0, 2, 4))
                    except ValueError:
                        continue
                    if (0.299 * r + 0.587 * g + 0.114 * b) / 255 >= 0.45:
                        continue
                    fc = c.font.color
                    if fc is not None and fc.type == "rgb" and str(fc.rgb).upper().endswith("FFFFFF"):
                        continue
                    font = copy(c.font)
                    font.color = "FFFFFFFF"
                    c.font = font

    # -------------------------------------------------------- general info
    def _general_info(self) -> None:
        f, ws = self.f, self.wb["General Info"]
        ws["B3"] = f.run_date
        ws["B3"].number_format = "mm/dd/yy"
        ws["D3"] = f"First Friday of forecast (Zoho Books data pulled {f.pulled_at[:16].replace('T', ' ')} UTC)"
        for r, label in ((35, "IRS Taxes - Sept 15"), (39, "NJ State Tax - Sept 15")):
            ws.cell(r, 4).value = (f"Now history (before {fmt_md(f.run_date)} forecast start)"
                                   if date(f.run_date.year, 9, 15) < f.run_date else None)
        parts = " + ".join(f"{c['name']} {c['balance']:,.2f}" for c in f.cash_accounts)
        names = f.rules["opening_cash"]["zoho_cash_account_names"]
        short = [("CHK" if "CHK" in n.upper() else n) for n in names]
        ws["A44"] = f"Cash per live Zoho ({' + '.join(short)})"
        ws["B44"] = round(f.zoho_cash, 2)
        ws["D44"] = f"Book/ledger balance per Zoho Books: {parts}"
        adj = f.manual_adjustments
        ws["A45"] = adj[0]["label"] if len(adj) == 1 else ("Manual adjustments (see note)" if adj else "Manual adjustment - none")
        ws["B45"] = round(sum(a["amount"] for a in adj), 2)
        ws["D45"] = " | ".join(f"{a['label']} {a['amount']:,.2f} (entered by {a['entered_by']}, as of {a['as_of']}). {a.get('note', '')}"
                               for a in adj) or "No manual adjustment on file."
        ws["B46"] = "=B44+B45"
        ws["B4"] = "=B46"
        ws["D4"] = ("Opening cash = live Zoho cash (B44) + manual adjustment (B45). Build-up in rows 44-46. "
                    "One-off amounts in the weekly rows: MANUAL ENTRIES block from row 48.")
        self._manual_entries_block(ws)
        for r in self.f.rules.get("hidden_cfm_rows", []):
            self.wb["Cash Flow Model"].row_dimensions[r].hidden = True

    def _manual_entries_block(self, ws) -> None:
        """General Info rows 48+: one line per manual entry; the Cash Flow Model cell links to column B."""
        f = self.f
        head, lab, val, note = (_style_of(ws, "A43"), _style_of(ws, "A44"), _style_of(ws, "B44"), _style_of(ws, "D44"))
        for rr in range(48, max(ws.max_row, 48) + 1):
            for cc in range(1, 7):
                ws.cell(rr, cc).value = None
        ws["A48"] = "MANUAL ENTRIES - one-off amounts entered by hand (column B feeds the Cash Flow Model by formula)"
        _apply(ws["A48"], head)
        for j, h in enumerate(("Description", "Amount", "Cash Flow Model row", "Week ending", "Status / source / note")):
            c = ws.cell(49, 1 + j, h)
            _apply(c, head)
        if not f.manual_entries:
            ws["A50"] = "None"
            _apply(ws["A50"], lab)
            return
        for m in f.manual_entries:
            r = m["gi_row"]
            ws.cell(r, 1, m.get("label", ""))
            ws.cell(r, 2, m["amount"])
            ws.cell(r, 3, m["cfm_row"])
            ws.cell(r, 4, m["week"])
            ws.cell(r, 5, f"{m['status']}. Source: {m.get('source', '')}. Entered by {m.get('entered_by', '')} "
                          f"{m.get('entered_on', '')}. {m.get('note', '')}")
            for cc, st in ((1, lab), (2, val), (3, lab), (4, lab), (5, note)):
                _apply(ws.cell(r, cc), st)
            ws.cell(r, 2).number_format = MONEY
            ws.cell(r, 4).number_format = "mm/dd/yy"
            ws.cell(r, 5).alignment = copy(ws.cell(r, 5).alignment)
        if (ws.column_dimensions["E"].width or 0) < 60:
            ws.column_dimensions["E"].width = 90

    # ----------------------------------------------------- cash flow model
    def _cash_flow_model(self) -> None:
        f, ws, n, C = self.f, self.wb["Cash Flow Model"], self.n, self.cols
        first, last = f.fridays[0], f.fridays[-1]
        ws["A1"] = f"AI CASH FLOW MODEL  |  Weekly Forecast  |  {first:%b %Y} – {last:%b %Y}"
        base_hdr = _style_of(ws, "C2")
        base_mon = _style_of(ws, "C3")
        styles = {r: _style_of(ws, f"C{r}") for r in range(4, 99)}
        for rng in list(ws.merged_cells.ranges):
            if rng.min_row == 3:
                ws.unmerge_cells(str(rng))
        for col in range(3, max(ws.max_column, 3 + n) + 1):
            for r in range(2, 99):
                ws.cell(r, col).value = None
        # dates + month bands
        start = 0
        for i, x in enumerate(f.fridays):
            c = ws.cell(2, 3 + i, x)
            _apply(c, base_hdr)
            c.number_format = "mm/dd/yy"
            if i == n - 1 or f.fridays[i + 1].month != x.month:
                ws.cell(3, 3 + start, f"{f.fridays[start]:%b %Y}")
                _apply(ws.cell(3, 3 + start), base_mon)
                if i > start:
                    ws.merge_cells(start_row=3, start_column=3 + start, end_row=3, end_column=3 + i)
                start = i + 1

        def put(r, i, v):
            c = ws.cell(r, 3 + i, v)
            _apply(c, styles.get(r))

        sumifs_rev = "=SUMIFS('Revenue Detail'!$E:$E,'Revenue Detail'!$A:$A,\"{k}\",'Revenue Detail'!$F:$F,{c}2)"
        sumifs_cogs = "=SUMIFS('COGS Detail'!$F:$F,'COGS Detail'!$C:$C,\"{k}\",'COGS Detail'!$G:$G,{c}2)"
        # 1 Oct 2026 layout: row 10 = 1100.3 Amazon; everything from Adjustments down is one row below Version 10
        rows_with_zero = {7, 38, 54, 65, 67, 69, 82}
        for i in range(n):
            c, p = C[i], (C[i - 1] if i else None)
            put(4, i, "='General Info'!$B$4" if i == 0 else f"={p}98")
            put(8, i, sumifs_rev.format(k="SERVPRO*", c=c))
            put(10, i, sumifs_rev.format(k="Amazon*", c=c))
            put(14, i, sumifs_rev.format(k="A/R*", c=c))
            put(18, i, sumifs_cogs.format(k=COGS_3100, c=c))
            put(19, i, sumifs_cogs.format(k=COGS_3101, c=c))
            put(20, i, sumifs_cogs.format(k=COGS_3102, c=c))
            for r in rows_with_zero:
                put(r, i, 0)
            put(15, i, f"=SUM({c}7:{c}14)")
            put(21, i, f"=({c}18+{c}19+{c}20)")
            put(33, i, "=" + "+".join(f"{c}{r}" for r in range(24, 33)))
            put(35, i, f"={c}15-{c}21-{c}33")
            put(48, i, "=" + "+".join(f"{c}{r}" for r in range(38, 48)))
            put(61, i, "=" + "+".join(f"{c}{r}" for r in range(51, 61)))
            put(73, i, "=" + "+".join(f"{c}{r}" for r in range(64, 73)))
            put(84, i, "=" + "+".join(f"{c}{r}" for r in range(76, 84)))
            put(91, i, f"={c}87+{c}88+{c}89+{c}90")
            put(94, i, f"='Credit Card Payments'!{c}61")
            put(96, i, f"='Credit Card Payments'!{c}28")
            put(98, i, f"={c}4+{c}15-{c}21-{c}33-{c}48-{c}61-{c}73-{c}84-{c}91-{c}94-{c}95+{c}96")
        sched_rows = set(f.cfm) | {11, 12, 13, 24, 25, 26, 27, 28, 29, 30, 31, 32, 39, 40, 41, 42, 43, 44, 45, 46, 47,
                                   51, 52, 53, 55, 56, 57, 58, 59, 60, 64, 66, 68, 70, 71, 72, 76, 77, 78, 79, 80, 81,
                                   83, 87, 88, 89, 90, 95}
        for r in sched_rows:
            cells = f.cfm.get(r, [(0.0, None)] * n)
            for i, (_, formula) in enumerate(cells):
                put(r, i, formula if formula else 0)

    # ------------------------------------------------------ revenue detail
    def _revenue_detail(self) -> None:
        f, ws = self.f, self.wb["Revenue Detail"]
        st = {k: _style_of(ws, k) for k in ("A15", "A16", "B16", "C16", "D16", "E16", "F16", "A17", "B17", "C17",
                                            "D17", "E17", "F17", "D33", "E33", "A13", "H143", "H144", "I144", "K145",
                                            "H145", "J156", "K156")}
        ws["B4"] = fmt_md(f.run_date)
        ws["B5"] = "='General Info'!$B$4"
        ws["C5"] = f"Opening cash for this run (General Info B4: Zoho cash + logged manual adjustments), as of {fmt_md(f.run_date)}"
        ws["A13"] = (f"Live invoice / sales-order block pulled from Zoho Books {f.pulled_at[:10]}. "
                     "RECEIPTS use the Friday ON OR AFTER the due date (drafts: their due date; SERVPRO sales orders: "
                     "ship date +45; Amazon sales orders: ship date +30; reseller sales orders: ship date +21; no ship date: "
                     "order date + terms, UNVERIFIED). Source column A routes each line: SERVPRO* -> Cash Flow Model row 8, "
                     "Amazon* -> row 10, A/R* -> row 14. "
                     "Anything already due before week 1 is swept into week 1. Sales orders are forecast at their "
                     "UNINVOICED remainder only, so a draft invoice and its sales order are never both counted.")
        _clear_from(ws, 15)
        r = 15
        by_week: dict[date, list] = {}
        for x in f.revenue:
            by_week.setdefault(x.week, []).append(x)
        for wk in sorted(by_week):
            items = sorted(by_week[wk], key=lambda x: -x.amount)
            ws.cell(r, 1, f"WEEK ENDING {fmt_md(wk)}" + ("" if wk in f.fridays else "   (after the forecast window — not in totals)"))
            _apply(ws.cell(r, 1), st["A15"])
            r += 1
            for j, h in enumerate(("Source", "Ref #", "Customer", "Basis", "Amount", "Week key")):
                ws.cell(r, 1 + j, h)
                _apply(ws.cell(r, 1 + j), st[f"{'ABCDEF'[j]}16"])
            r += 1
            first = r
            for x in items:
                vals = (x.source, x.ref, x.party, x.basis, x.amount, wk if wk in f.fridays else None)
                for j, v in enumerate(vals):
                    ws.cell(r, 1 + j, v)
                    _apply(ws.cell(r, 1 + j), st[f"{'ABCDEF'[j]}17"])
                r += 1
            ws.cell(r, 4, "Week total (event-driven)")
            ws.cell(r, 5, f"=SUM(E{first}:E{r - 1})")
            _apply(ws.cell(r, 4), st["D33"])
            _apply(ws.cell(r, 5), st["E33"])
            r += 2
        # held for client review (no week key -> excluded from every total)
        ws.cell(r, 1, "HELD FOR CLIENT REVIEW — open items from v10, NOT in any week total (no week key). "
                      "They will be added once the client confirms.")
        _apply(ws.cell(r, 1), st["A15"])
        r += 1
        for j, h in enumerate(("Source", "Ref #", "Customer", "Reason held", "Amount", "Would land w/e")):
            ws.cell(r, 1 + j, h)
            _apply(ws.cell(r, 1 + j), st[f"{'ABCDEF'[j]}16"])
        r += 1
        for x in f.held or []:
            for j, v in enumerate((f"HELD — {x.source}", x.ref, x.party, x.basis, x.amount, fmt_md(x.week))):
                ws.cell(r, 1 + j, v)
                _apply(ws.cell(r, 1 + j), st[f"{'ABCDEF'[j]}17"])
            r += 1
        if not f.held:
            ws.cell(r, 1, "None")
            r += 1
        r += 1
        ws.cell(r, 1, "(The REALISED audit block sits in columns H–N, deliberately clear of columns A–F, so it can never be picked up by the Cash Flow Model SUMIFS.)")
        r += 1
        ws.cell(r, 8, "REALISED SINCE THE PRIOR FORECAST — invoices open in the prior run and no longer open in Zoho. "
                      "Audit trail only; the cash is already inside the opening balance.")
        _apply(ws.cell(r, 8), st["H143"])
        r += 1
        for j, h in enumerate(("Ref", "Customer", "Status (prior run)", "Prior balance", "Note")):
            ws.cell(r, 8 + j, h)
            _apply(ws.cell(r, 8 + j), st["I144"])
        r += 1
        if f.realised_since_prior:
            for x in f.realised_since_prior:
                for j, v in enumerate((x.ref, x.party, x.status, x.amount, x.basis)):
                    ws.cell(r, 8 + j, v)
                    _apply(ws.cell(r, 8 + j), st["H145"])
                ws.cell(r, 11).number_format = MONEY
                r += 1
        else:
            ws.cell(r, 8, self._no_prior_text(f, "collected"))
            r += 1

    # --------------------------------------------------------- cogs detail
    def _cogs_detail(self) -> None:
        f, ws = self.f, self.wb["COGS Detail"]
        st = {k: _style_of(ws, k) for k in ("A48", "A49", "G49", "A50", "E50", "F50", "G50", "E54", "F54", "A100",
                                            "A101", "A102", "F102", "A132")}
        ws["A3"] = ("Rule: each bill / purchase order is paid on the week-ending Friday ON OR BEFORE its due date; anything "
                    "overdue at the run date is swept into week 1. Bills use the remaining BALANCE (unpaid, overdue, "
                    "partially paid). Purchase orders (Issued/Open, Draft, Partially billed) use the UNBILLED amount; due "
                    "date = delivery date (or PO date when no delivery date, UNVERIFIED) + the Zoho supplier Payment Terms "
                    "(Assumptions & Rules row 13; Due on Receipt = 0). C.H. Robinson / Zim -> Inbound Freight (3101); US "
                    "Customs -> Inbound Duty (3102); all other supplier bills -> COGS (3100). Prudent (3PL), the Amex loan "
                    "fee, tax bills and bills posted only to non-COGS accounts are listed in the EXCLUDED block and carry no "
                    "week key. Column G is the week key read by Cash Flow Model rows 18-20.")
        _clear_from(ws, 5)
        r = 5
        by_week: dict[date, list] = {}
        for x in f.cogs:
            by_week.setdefault(x.week, []).append(x)
        hdr = ("PO/Bill #", "Vendor", "Category", "Status", "Basis", "Amount", "Week key")
        for wk in sorted(by_week):
            ws.cell(r, 1, f"WEEK ENDING {fmt_md(wk)}" + ("" if wk in f.fridays else "   (after the forecast window — not in totals)"))
            _apply(ws.cell(r, 1), st["A48"])
            r += 1
            for j, h in enumerate(hdr):
                ws.cell(r, 1 + j, h)
                _apply(ws.cell(r, 1 + j), st["G49" if j == 6 else "A49"])
            r += 1
            first = r
            for x in sorted(by_week[wk], key=lambda x: (x.source != "Bill", x.ref)):
                for j, v in enumerate((x.ref, x.party, x.category, x.status, x.basis, x.amount,
                                       wk if wk in f.fridays else None)):
                    ws.cell(r, 1 + j, v)
                    _apply(ws.cell(r, 1 + j), st["F50" if j == 5 else ("G50" if j == 6 else "A50")])
                r += 1
            ws.cell(r, 5, "Week total")
            ws.cell(r, 6, f"=SUM(F{first}:F{r - 1})")
            _apply(ws.cell(r, 5), st["E54"])
            _apply(ws.cell(r, 6), st["F54"])
            r += 2
        # paid since prior run
        ws.cell(r, 1, "PAID SINCE THE PRIOR FORECAST — bills unpaid in the prior run and no longer unpaid in Zoho. "
                      "Cash is already in the opening balance, so these carry no week key and are excluded from every total.")
        _apply(ws.cell(r, 1), st["A100"])
        r += 1
        for j, h in enumerate(hdr[:6]):
            ws.cell(r, 1 + j, h)
            _apply(ws.cell(r, 1 + j), st["A101"])
        r += 1
        if f.paid_since_prior:
            for x in f.paid_since_prior:
                for j, v in enumerate((x.ref, x.party, x.category or "", x.status, x.basis, x.amount)):
                    ws.cell(r, 1 + j, v)
                    _apply(ws.cell(r, 1 + j), st["F102" if j == 5 else "A102"])
                r += 1
        else:
            ws.cell(r, 1, self._no_prior_text(f, "paid"))
            r += 1
        r += 1
        ws.cell(r, 1, "EXCLUDED — posted to an account already carried as a run-rate / scheduled elsewhere (no week key)")
        _apply(ws.cell(r, 1), st["A132"])
        r += 1
        for j, h in enumerate(hdr[:6]):
            ws.cell(r, 1 + j, h)
            _apply(ws.cell(r, 1 + j), st["A101"])
        r += 1
        for x in f.excluded_bills:
            for j, v in enumerate((x.ref, x.party, "", x.status, x.basis, x.amount)):
                ws.cell(r, 1 + j, v)
                _apply(ws.cell(r, 1 + j), st["F102" if j == 5 else "A102"])
            r += 1

    # ------------------------------------------------------- credit cards
    def _credit_cards(self) -> None:
        f, ws, n, C = self.f, self.wb["Credit Card Payments"], self.n, self.cols
        card = f.card
        hdr_style = _style_of(ws, "C2")
        row_styles = {r: _style_of(ws, f"C{r}") for r in range(4, 62)}
        for col in range(3, max(ws.max_column, 3 + n) + 1):
            for r in list(range(2, 29)) + [61]:
                ws.cell(r, col).value = None
        for i, x in enumerate(f.fridays):
            c = ws.cell(2, 3 + i, x)
            _apply(c, hdr_style)
            c.number_format = "mm/dd/yy"
            ws.cell(4, 3 + i, 0)
            _apply(ws.cell(4, 3 + i), row_styles[4])
            for cc_row, cfm_row in CARD_ROWS:
                ws.cell(cc_row, 3 + i, f"='Cash Flow Model'!{C[i]}{cfm_row}")
                _apply(ws.cell(cc_row, 3 + i), row_styles[cc_row])
            out = "='Expense Assumptions'!$E$43*$B$41" if card["outbound_card"][i] else 0
            ws.cell(27, 3 + i, out)
            _apply(ws.cell(27, 3 + i), row_styles[27])
            ws.cell(28, 3 + i, f"=SUM({C[i]}4:{C[i]}27)")
            _apply(ws.cell(28, 3 + i), row_styles[28])
            ws.cell(61, 3 + i, f"=SUMIF($C$45:$C$57,{C[i]}$2,$F$45:$F$57)")
            _apply(ws.cell(61, 3 + i), row_styles[61])
        plat, corp = card.get("platinum"), card.get("corp")
        close0 = card["cycles"][0]["close"]
        post = card.get("post_close")
        paid = card.get("paid_since_close", 0.0) or 0.0
        ws["A31"] = (f"Business Platinum statement still due (cycle close {fmt_md(close0)})" if paid > 0.005
                     else f"Business Platinum balance at cycle close {fmt_md(close0)}")
        ws["B31"] = card.get("platinum_at_close", card["platinum_balance"])
        ws["C31"] = ((f"Balance at the close {card.get('platinum_close_balance', 0):,.2f} less {paid:,.2f} paid since the "
                      f"close (live balance {card['platinum_balance']:,.2f} less net charges after the close, B34)")
                     if post and paid > 0.005 else
                     f"Live Zoho card account {plat['name'] if plat else '(not found)'} {card['platinum_balance']:,.2f} "
                     f"less net charges posted after the close (B34)" if post else
                     f"Live Zoho card account {plat['name'] if plat else '(not found)'} - charges after the close not in "
                     "this pull, so this may include next-cycle charges")
        sb = card.get("statement_bills") or []
        carry = card.get("carry_to_next", 0.0) or 0.0
        if sb:
            ws["A31"] = f"Business Platinum statement — open Amex bill in Zoho A/P (cycle close {fmt_md(close0)})"
            ws["C31"] = (f"Zoho bill {', '.join(x['number'] for x in sb)}, balance {card['statement_bill_due']:,.2f}, due "
                         f"{', '.join(x['due'].isoformat() for x in sb)}. Creating the bill shows as a payment on the card; "
                         "no cash has left until the bill is paid (row 94).")
        st31 = {col: _style_of(ws, f"{col}31") for col in "ABC"}
        ws["A34"] = f"Platinum charges posted after the {fmt_md(close0)} close (actual)"
        ws["B34"] = (round(card.get("post_close_net", post["net"] if post else 0.0), 2)
                     if post or card.get("statement_bills") else 0)
        ws["C34"] = (f"{post['count']} card transaction{'s' if post['count'] != 1 else ''} "
                     f"{post['from'].isoformat()} to {post['to'].isoformat()}"
                     + (f"; payments in that period {post['payments']:,.2f} (taken off the statement still due, B31)"
                   if post["payments"] else "")
                + (f"; less {card.get('overpaid_since_close', 0):,.2f} paid beyond the statement"
                   if card.get("overpaid_since_close") else "")
                     + "; owed on the next statement (Block B, 2nd cycle)" if post else
                     "Not pulled (older snapshot) - re-fetch Zoho")
        if sb:
            ws["A34"] = "Platinum balance not on the Amex statement bill — owed on the next statement"
            ws["C34"] = (f"Live Zoho Platinum balance {card['platinum_balance']:,.2f} = "
                         f"{post['net'] if post else 0:,.2f} net charges posted after the {fmt_md(close0)} close"
                         + (f" ({post['count']} transactions {post['from'].isoformat()} to {post['to'].isoformat()})" if post else "")
                         + f" + {carry:,.2f} left on the card at the close beyond the Amex statement bill")
        for col in "ABC":
            _apply(ws[f"{col}34"], st31[col])
        ws["A32"] = "CORP Cash Rewards-7747 residual balance"
        ws["B32"] = card["corp_residual"]
        cb = card.get("corp_row")
        ws["C32"] = (f"Live Zoho card account {corp['name'] if corp else '(not found)'}"
                     + (f" less unpaid statement bill {cb['basis'].split()[-1]}" if cb else "")
                     + "; rolls into the next Platinum-cycle statement")
        ws["A33"] = "CORP statement bill (unpaid in Zoho A/P)" if cb else "CORP statement bill — none unpaid in Zoho A/P"
        ws["B33"] = round(cb["total"], 2) if cb else 0
        ws["C33"] = (f"Zoho bill, due {cb['due'].isoformat()}" if cb else "No unpaid 'CORP Credit Card' bill at the run date")
        obs = card["share_obs"]
        for k in range(3):
            ws.cell(36 + k, 1, f"   {obs[k]['label']}" if k < len(obs) else None)
            ws.cell(36 + k, 2, obs[k]["amount"] if k < len(obs) else None)
        ws["B39"] = f"=AVERAGE(B36:B{35 + min(len(obs), 3)})"
        ws["A44"] = ("Partly card-funded account (Outbound Freight 2107): Cash Flow Model row 30 carries accrual x "
                     "(1 - card share) as direct cash-out on the 1st Friday and accrual x card share on the 2nd Friday. The "
                     "card share (row 27 above, 2nd Friday) is added back by Cash Flow Model row 96 in that same week and "
                     "leaves as cash inside its statement via row 94. Net: the full accrual is paid once.")
        # Block B
        for k, cyc in enumerate(card["cycles"]):
            r = 45 + k
            ws.cell(r, 1, cyc["close"])
            ws.cell(r, 2, cyc["due"])
            ws.cell(r, 3, f"=MAX($C$2,B{r}-MOD(WEEKDAY(B{r},2)-5,7))" if k == 0 and card.get("statement_bills")
                    else f"=B{r}-MOD(WEEKDAY(B{r},2)-5,7)")
            ws.cell(r, 4, "=$B$31" if k == 0 else ("=$B$32+$B$34" if k == 1 else 0))
            ws.cell(r, 5, 0 if k == 0 else
                    f'=SUMIFS($C$28:${C[-1]}$28,$C$2:${C[-1]}$2,">"&A{r - 1},$C$2:${C[-1]}$2,"<="&A{r})')
            ws.cell(r, 6, f"=D{r}+E{r}")
            ws.cell(r, 7, cyc["basis"])
        r = 57
        if cb:
            ws.cell(r, 1, None)
            ws.cell(r, 2, cb["due"])
            ws.cell(r, 3, f"=B{r}-MOD(WEEKDAY(B{r},2)-5,7)")
            ws.cell(r, 4, 0)
            ws.cell(r, 5, 0)
            ws.cell(r, 6, "=$B$33")
            ws.cell(r, 7, cb["basis"])
        else:
            for col in range(1, 8):
                ws.cell(r, col).value = None
            ws.cell(r, 6, "=$B$33")
            ws.cell(r, 7, "No unpaid CORP statement bill")
        ws["F58"] = "=SUM(F45:F57)"
        ws["A64"] = ("Owed on the cards (open Amex statement bill + live Platinum balance + CORP residual)"
                     if card.get("statement_bills") else
                     "Opening card balance (Platinum at close + charges after the close + CORP residual)")
        ws["B64"] = "=$B$31+$B$32+$B$34"
        ws["B65"] = f"=SUM($C$28:${C[-1]}$28)"
        ws["B67"] = f"=SUM($C$61:${C[-1]}$61)-$B$33"
        ws["A68"] = f"Residual unpaid at horizon (last cycle, due after {fmt_md(f.fridays[-1])})"
        # itemization
        cyc = f"{card['cycles'][0]['close']:%b %d}"
        st_item = {k: _style_of(ws, k) for k in ("A73", "B73", "C73", "B92", "C92", "B95", "C95")}
        _clear_from(ws, 71)
        items = card["itemization"]
        code_of = self._code_map()
        ws.cell(71, 1, f"ACTUAL STATEMENT ITEMIZATION — Business Platinum, cycle ending {cyc} (live card transaction pull)")
        ws.cell(72, 1, "Account")
        ws.cell(72, 2, "Vendor / Description")
        ws.cell(72, 3, "Amount")
        if not items:
            ws.cell(73, 1, "Card transactions were not available from Zoho for this cycle (or failed the plausibility "
                           "check) - itemization not shown. The card statements above use the live card balances; the "
                           "outbound-freight card share uses the last known cycle. See the Overview open items.")
            ws.cell(75, 1, "Block A links live to the Cash Flow Model, so a change to any expense assumption flows "
                           "through to the card statements and to row 94.")
            return
        r = 73
        for name, amt in items:
            ws.cell(r, 1, code_of.get(name.lower(), "—"))
            ws.cell(r, 2, name)
            ws.cell(r, 3, amt)
            for col, k in ((1, "A73"), (2, "B73"), (3, "C73")):
                _apply(ws.cell(r, col), st_item[k])
            r += 1
        last = r - 1
        net = sum(a for _, a in items)
        close_bal = card.get("platinum_close_balance", card.get("platinum_at_close", card["platinum_balance"]))
        paid_after = card.get("paid_since_close", 0.0) or 0.0
        opening_prev = round(close_bal - net + card.get("cycle_payments", 0.0), 2)
        rows = [("Net cycle activity (charges less credits)", f"=SUM(C73:C{last})" if items else 0),
                ("Opening balance carried in at prior close (derived)", opening_prev),
                ("Less payments made in cycle", -card.get("cycle_payments", 0.0)),
                ((f"BALANCE AT THE {fmt_md(card['cycles'][0]['close'])} CLOSE (Zoho book)" if card.get("statement_bills")
                  else f"STATEMENT TOTAL DUE {fmt_md(card['cycles'][0]['due'])}"), f"=C{r}+C{r + 1}+C{r + 2}")]
        sb = card.get("statement_bills") or []
        if sb:
            carry = card.get("carry_to_next", 0.0) or 0.0
            billed_after = sum(x["total"] for x in sb if x["date"] and x["date"] > card["cycles"][0]["close"])
            paid_on_bill = round(sum(x["total"] - x["balance"] for x in sb), 2)
            direct = round(paid_after - billed_after, 2)
            extra = []
            if abs(direct) > 0.005:
                extra.append(("Less paid on the card since the close (not via the bill)", -direct))
            if paid_on_bill > 0.005:
                extra.append(("Less paid on the Amex bill so far", -paid_on_bill))
            extra.append(("Less left on the card beyond the Amex bill (carried to next statement, B34)", -carry))
            first = r + 3
            rows += extra + [("AMEX STATEMENT BILL STILL DUE (row 94)", f"=SUM(C{first}:C{first + len(extra)})"),
                             ("Check: ties to the Platinum input above", f"=C{first + len(extra) + 1}-$B$31")]
        elif paid_after > 0.005:
            rows += [("Less paid since the close", -paid_after), ("STILL DUE (row 94)", f"=C{r + 3}+C{r + 4}"),
                     ("Check: ties to the Platinum input above", f"=C{r + 5}-$B$31")]
        else:
            rows += [("Check: ties to the Platinum input above", f"=C{r + 3}-$B$31")]
        for k, (lab, val) in enumerate(rows):
            ws.cell(r + k, 2, lab)
            ws.cell(r + k, 3, val)
            strong = lab.startswith(("STATEMENT TOTAL", "STILL DUE", "AMEX STATEMENT BILL", "BALANCE AT THE"))
            _apply(ws.cell(r + k, 2), st_item["B95" if strong else "B92"])
            _apply(ws.cell(r + k, 3), st_item["C95" if strong else "C92"])
        ws.cell(r + len(rows) + 2, 1, "Block A links live to the Cash Flow Model, so a change to any expense assumption flows through "
                          "to the card statements and to row 94. Row 96 adds the card-funded charges back in the week they "
                          "are incurred, so they hit cash only when the statement is paid.")

    @staticmethod
    def _no_prior_text(f, verb: str) -> str:
        p = f.prior_info
        if not p:
            return "No prior forecast on file — nothing to compare."
        wk = fmt_md(p["week1"]) if p.get("week1") else "?"
        return (f"None — nothing open in the prior forecast (week 1 = {wk}, Zoho pulled {p.get('pulled_at', '')} UTC) "
                f"has been {verb} since.")

    def _code_map(self) -> dict[str, str]:
        ws = self.wb["Expense Assumptions"]
        m = {}
        for r in range(3, 47):
            code, name = ws.cell(r, 1).value, ws.cell(r, 2).value
            if code and name:
                m[str(name).lower()] = str(code)
        cfm = self.wb["Cash Flow Model"]
        for r in range(7, 90):
            code, name = cfm.cell(r, 1).value, cfm.cell(r, 2).value
            if code and name:
                m[str(name).strip().lower()] = str(code)
        m.update({"meals and entertainment": "4112", "office supplies and equipment": "6111",
                  "outbound freight costs": "2107", "misc operations expenses": "2105", "drawings": "Drawings"})
        return m

    # ------------------------------------------------------------- overview
    def _overview(self) -> None:
        f, ws, k = self.f, self.wb["Overview"], self.f.kpis
        st = {c: _style_of(ws, c) for c in ("A1", "A2", "A6", "A7", "A8", "B8", "A9", "B9", "C9", "A24", "B25",
                                           "C25", "A34", "A35", "B35", "C35", "B61", "A62", "B62", "A77", "B77",
                                           "A78", "B78")}
        _clear_from(ws, 1)
        r = 1

        def line(cells, style_keys, height=None):
            nonlocal r
            for j, (v, sk) in enumerate(zip(cells, style_keys)):
                if v is None and sk is None:
                    continue
                c = ws.cell(r, 1 + j, v)
                _apply(c, st.get(sk))
            r += 1

        line([f"GUTSTER TOOLS — CASH FLOW FORECAST OVERVIEW"], ["A1"])
        line([f"Week ending {f.run_date:%d %B %Y}", None, f"Run date {f.run_date:%d %B %Y}"], ["A2", None, "A2"])
        line(["Zoho org 695133731", None, "Cash basis: book/ledger, not bank feed"], ["A2", None, "A2"])
        line([f"Built from a read-only Zoho Books pull ({f.pulled_at[:16].replace('T', ' ')} UTC)."], ["A2"])
        r += 1
        line(["WEEK-1 INTERNAL CASH BRIDGE (w/e " + f"{f.run_date:%d %b %Y})"], ["A6"])
        line(["Week-1 bridge from opening cash to ending cash; every figure links live to the Cash Flow Model."], ["A7"])
        line(["Item", "Amount", "Source"], ["A8", "B8", "B8"])
        bridge = [("Opening Cash Position", "='Cash Flow Model'!C4", "General Info!B4 — Zoho cash + manual adjustment (row 45)"),
                  ("+ Total Revenue", "='Cash Flow Model'!C15", "row 15 — SERVPRO (row 8), Amazon (row 10), A/R (row 14), run-rates"),
                  ("− Total COGS", "=-'Cash Flow Model'!C21", "row 21 — bills and open POs by due date"),
                  ("− Total Operations", "=-'Cash Flow Model'!C33", "row 33"),
                  ("− Total Marketing", "=-'Cash Flow Model'!C48", "row 48"),
                  ("− Total Selling", "=-'Cash Flow Model'!C61", "row 61"),
                  ("− Total Finance & Admin", "=-'Cash Flow Model'!C73", "row 73"),
                  ("− Total IT", "=-'Cash Flow Model'!C84", "row 84"),
                  ("− Total Non-Operating", "=-'Cash Flow Model'!C91", "row 91"),
                  ("− Credit Card Payment Due", "=-'Cash Flow Model'!C94", "row 94"),
                  ("− Loan Repayment", "=-'Cash Flow Model'!C95", "row 95 — General Info B31 on the last Friday + Duckbill B32 on the 1st Friday + manual entries (General Info row 50 on)"),
                  ("+ CC Charges Deferred (non-cash)", "='Cash Flow Model'!C96", "row 96 — Block A weekly card charges"),
                  ("Ending Cash Position", "='Cash Flow Model'!C98", "row 98")]
        for a, b, c in bridge:
            line([a, b, c], ["A9", "B9", "C9"])
        r += 1
        line(["RESTATEMENTS / RULE NOTES THIS RUN — differences from the v10 canonical treatment"], ["A6"])
        line(["Item", "Amount", "Reason"], ["A24", "B25", "C25"])
        for a, b, c in self._restatements():
            line([a, b, c], ["A9", "B9", "C9"])
        r += 1
        line(["KEY PERFORMANCE INDICATORS"], ["A6"])
        line(["KPI", "Value", "Source / basis"], ["A8", "B8", "B8"])
        neg = k["negative_weeks"]
        adj_total = sum(a["amount"] for a in f.manual_adjustments)
        kp = [("Opening cash", money(f.opening_cash), f"General Info!B4 = Zoho cash {money(f.zoho_cash)} + manual adjustments {money(adj_total)}"),
              ("Manual adjustment in opening cash", money(adj_total), "; ".join(f"{a['label']} (entered by {a['entered_by']})" for a in f.manual_adjustments) or "none"),
              ("Manual entries in the weekly rows", money(sum(m["amount"] for m in f.manual_entries if m["applied"])),
               "; ".join(f"{m.get('label', '')} {money(m['amount'])} row {m['cfm_row']} w/e {fmt_md(m['week']) if m['week'] else '-'}"
                         f" ({'applied' if m['applied'] else 'not applied'})" for m in f.manual_entries) or "none"),
              ("Cash collected this week (wk 1)", money(f.values[15][0]), "Cash Flow Model!C15"),
              ("Cash expenses paid this week (wk 1)", money(f.values[4][0] + f.values[15][0] - f.values[98][0]), "C4 + C15 − C98"),
              ("Weeks until cash goes negative", f"negative from w/e {fmt_md(k['first_negative'])}" if neg else "Never negative in the window", "Cash Flow Model row 98"),
              ("Negative weeks in the window", f"{len(neg)}" + (f" — {fmt_md(neg[0])} to {fmt_md(neg[-1])}" if neg else ""), "row 98"),
              ("Forecast trough", f"{money(k['trough'])} at w/e {fmt_md(k['trough_week'])}", "row 98 minimum"),
              ("Cash position recovers to positive", f"w/e {fmt_md(k['recovers'])}" if k["recovers"] and k["trough"] < 0 else "n/a", "row 98, first non-negative week after the trough"),
              (f"Horizon end (w/e {fmt_md(f.fridays[-1])})", money(k["horizon_end"]), "row 98, final column"),
              ("Open A/R", f"{k['open_ar_count']} unpaid invoices, {money(k['open_ar'])}", "Zoho invoices status unpaid (sent / overdue / partially paid)"),
              ("Draft invoices in the forecast", f"{k['draft_count']} invoices, {money(k['draft_total'])}", "Zoho invoices status draft; each netted against its sales order"),
              ("Uninvoiced sales-order balance in the forecast", f"{k['so_count']} orders, {money(k['so_total'])}", "sales order total less invoiced amount; held orders excluded"),
              ("Total Zoho A/P", f"{money(k['ap_total'])} ({k['ap_count']} unpaid bills)", "Zoho bills status unpaid"),
              ("Next card payment due", f"{fmt_md(f.card['cycles'][0]['due'])} — {money(f.card['cycles'][0]['total'])} (Platinum), lands w/e {fmt_md(f.card['cycles'][0]['lands'])}", "Credit Card Payments Block B"),
              ("Current card balance (liability, excluded from cash)", money(sum(c['balance'] for c in f.card_accounts)), " + ".join(f"{c['name']} {money(c['balance'])}" for c in f.card_accounts))]
        for a, b, c in kp:
            line([a, b, c], ["A35", "B35", "C35"])
        r += 1
        line(["FORECAST POSITION — THREE NEAR WEEKS (live references, never hardcoded)"], ["A6"])
        line([None] + [f"Week {i + 1} — {fmt_md(f.fridays[i])}" for i in range(3)], [None, "B61", "B61", "B61"])
        rows = [("Opening Cash", 4), ("Revenue", 15), ("COGS", 21), ("Operations", 33), ("Marketing", 48),
                ("Selling", 61), ("Finance & Admin", 73), ("IT", 84), ("Non-Operating", 91), ("CC Payment Due", 94),
                ("Loan Repayment", 95), ("CC Charges Deferred", 96), ("Ending Cash", 98)]
        for lab, cr in rows:
            line([lab] + [f"='Cash Flow Model'!{self.cols[i]}{cr}" for i in range(3)], ["A62", "B62", "B62", "B62"])
        r += 1
        def block(title, items):
            nonlocal r
            line([title], ["A6"])
            line(["Owner", "Item"], ["A77", "B77"])
            for it in items:
                line([it["owner"], it["item"]], ["A78", "B78"])
                ws.merge_cells(start_row=r - 1, start_column=2, end_row=r - 1, end_column=4)
            r += 1

        block("OPEN ITEMS", f.v10_open_items)
        block("FIXED IN THIS RUN — CHANGES vs VERSION 10 AND WHY (for approval)", f.fixed_items)
        block("ADDITIONAL ITEMS FOR CLIENT REVIEW (not fixed in this run)", f.open_items)

    def _restatements(self) -> list[tuple]:
        f = self.f
        out = list(f.restatements)
        for x in f.held:
            out.append((f"{x.ref} held for client review", x.amount, "Not in any week total — see Revenue Detail 'HELD' block"))
        return out or [("None", 0, "No differences from the v10 treatment")]


    # --------------------------------------------------- changes since run
    def _changes_since_run(self) -> None:
        """Sheet 11: what changed in Zoho between the run's pull and the latest refresh pull (same week 1).

        The main sheets stay as the run; this sheet shows the refreshed position and every change."""
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        c = self.comparison
        ws = self.wb.create_sheet("Changes Since Run")
        ws.sheet_view.showGridLines = False
        navy, blue, grey, amber = "1B3A5C", "2E6DA4", "F2F2F2", "FFF2CC"
        thin = Side(style="thin", color="D9D9D9")
        box = Border(left=thin, right=thin, top=thin, bottom=thin)
        bold = Font(bold=True)
        r = 1

        def head(text, fill=navy, size=11):
            nonlocal r
            ws.cell(r, 1, text).font = Font(bold=True, size=size, color="FFFFFF")
            for col in range(1, 11):
                ws.cell(r, col).fill = PatternFill("solid", fgColor=fill)
            r += 1

        def cols(labels):
            nonlocal r
            for j, h in enumerate(labels, 1):
                cell = ws.cell(r, j, h)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor=blue)
                cell.alignment = Alignment(wrap_text=True, vertical="center")
                cell.border = box
            r += 1

        def money(cell, v):
            cell.value = None if v is None else round(float(v) + 0.0, 2)
            cell.number_format = MONEY
            return cell

        def when(iso):
            return (iso or "")[:16].replace("T", " ") + (" UTC" if iso else "")

        ws.cell(r, 1, "CHANGES SINCE RUN — what changed in Zoho between the forecast pull and the refresh pull").font = Font(bold=True, size=14)
        r += 1
        ws.cell(r, 1, f"Week 1: w/e {fmt_md(c.week1)}.   Run (forecast) pull: {when(c.run_pulled_at)}.   Refresh pull: {when(c.refresh_pulled_at)}.")
        r += 1
        ws.cell(r, 1, "All other sheets show the forecast as run. This sheet shows the refreshed position and every change, "
                      "built with the same rules and the same week 1, so every difference comes from Zoho data.").alignment = Alignment(wrap_text=False)
        r += 1
        for note in c.notes:
            cell = ws.cell(r, 1, note)
            cell.font = Font(bold=True, color="9C0006")
            r += 1
        r += 1

        head("A. SUMMARY")
        cols(["Item", "Run", "Refresh", "Change"])
        for label, a, b, kind in c.summary:
            ws.cell(r, 1, label).border = box
            if kind in ("money", "count"):
                for j, v in ((2, a), (3, b), (4, (b or 0) - (a or 0))):
                    cell = money(ws.cell(r, j), v) if kind == "money" else ws.cell(r, j, v)
                    cell.border = box
                    if j == 4 and abs((b or 0) - (a or 0)) > 0.005:
                        cell.fill = PatternFill("solid", fgColor=amber)
            else:
                ws.cell(r, 2, a).border = box
                ws.cell(r, 3, b).border = box
                d = ws.cell(r, 4, "" if a == b else "changed")
                d.border = box
                if a != b:
                    d.fill = PatternFill("solid", fgColor=amber)
            r += 1
        r += 1

        head("B. ENDING CASH BY WEEK — first 13 weeks")
        cols(["Week ending", "Run", "Refresh", "Change"])
        for wk, a, b in c.weekly:
            ws.cell(r, 1, wk).number_format = "mm/dd/yy"
            money(ws.cell(r, 2), a)
            money(ws.cell(r, 3), b)
            d = money(ws.cell(r, 4), b - a)
            if abs(b - a) > 0.005:
                d.fill = PatternFill("solid", fgColor=amber)
            for j in range(1, 5):
                ws.cell(r, j).border = box
            r += 1
        r += 1

        head("C. BRIDGE — why horizon-end cash changed")
        cols(["Group", "Cause", "Effect on cash", "Note"])
        for group, label, amt, note in c.bridge:
            ws.cell(r, 1, group)
            ws.cell(r, 2, label)
            money(ws.cell(r, 3), amt)
            ws.cell(r, 4, note)
            if "net" in label:
                for j in range(1, 5):
                    ws.cell(r, j).font = bold
                    ws.cell(r, j).fill = PatternFill("solid", fgColor=grey)
            for j in range(1, 5):
                ws.cell(r, j).border = box
                ws.cell(r, j).alignment = Alignment(wrap_text=True, vertical="top")
            r += 1
        ws.cell(r, 2, "Total = change in horizon-end cash").font = bold
        money(ws.cell(r, 3), c.bridge_total).font = bold
        ws.cell(r, 4, f"Horizon-end cash moved by {c.horizon_change:,.2f}")
        r += 2

        head("D. EVERY CHANGE, BY AREA")
        ws.cell(r, 1, f"Effect on cash = change in the forecast's cash over the {len(self.f.fridays)} weeks (+ more cash, − less cash). "
                      "'No cash effect' = status only; 'Timing only' = same amount, different week.")
        r += 1
        order = ["Opening cash", "Invoices", "Sales orders", "Purchase orders", "Bills", "Linked changes", "Credit cards",
                 "Manual entries"]
        for area in order + [a for a in c.blocks if a not in order]:
            rows = c.blocks.get(area)
            if rows is None:
                continue
            head(f"{area.upper()} — {len(rows)} change(s)", fill=blue)
            if not rows:
                ws.cell(r, 1, "No changes")
                r += 2
                continue
            cols(["Ref", "Customer / vendor", "Change", "Details", "Run amount", "Run week(s)", "Refresh amount",
                  "Refresh week(s)", "Effect on cash", "Note"])
            for x in rows:
                vals = [x["ref"], x["party"], x["change"], x["details"], None, x["before_weeks"], None,
                        x["after_weeks"], None, x["note"]]
                for j, v in enumerate(vals, 1):
                    cell = ws.cell(r, j, v)
                    cell.border = box
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                money(ws.cell(r, 5), x["before_amount"])
                money(ws.cell(r, 7), x["after_amount"])
                eff = x["cash_effect"]
                if eff is not None:
                    e = money(ws.cell(r, 9), eff)
                    if abs(eff) > 0.005:
                        e.fill = PatternFill("solid", fgColor=amber)
                r += 1
            r += 1
        head("UNCATEGORIZED BANK ITEMS", fill=blue)
        ws.cell(r, 1, "Not available yet - uncategorized bank transactions are not pulled from Zoho in this version.")
        r += 1
        for col, wdt in zip("ABCDEFGHIJ", (34, 30, 26, 60, 15, 16, 15, 16, 15, 34)):
            ws.column_dimensions[col].width = wdt
        ws.freeze_panes = "A2"

def export_forecast(f: Forecast, comparison=None) -> bytes:
    """comparison: app.engine.compare.Comparison of this run with its latest refresh pull -> adds the
    "Changes Since Run" sheet. The other sheets always show the run itself."""
    return V10Exporter(f, comparison).export()
