from __future__ import annotations
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from app.models.canonical import CanonicalRecord, DataConfidence

class HistoricalWorkbookImporter:

    def __init__(self, xlsx_path: str | Path):
        self.path = Path(xlsx_path)
        if not self.path.exists():
            raise FileNotFoundError(f'Historical workbook not found: {self.path}')

    def import_all(self) -> list[CanonicalRecord]:
        import openpyxl
        wb_values = openpyxl.load_workbook(self.path, data_only=True)
        wb_formulas = openpyxl.load_workbook(self.path, data_only=False)
        records: list[CanonicalRecord] = []
        records.extend(self._extract_revenue_detail(wb_values))
        records.extend(self._extract_cogs_detail(wb_values))
        records.extend(self._extract_expense_assumptions(wb_values))
        records.extend(self._extract_general_info(wb_values))
        return records

    def _ingest_ts(self) -> datetime:
        mtime = self.path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc)

    def _as_of_from_filename(self) -> date:
        match = re.search('(\\d{4}-\\d{2}-\\d{2})', self.path.stem)
        if match:
            return date.fromisoformat(match.group(1))
        return date.today()

    def _safe_decimal(self, val: Any) -> Decimal | None:
        if val is None:
            return None
        try:
            return Decimal(str(val).replace(',', '').replace('$', '').strip())
        except InvalidOperation:
            return None

    def _safe_date(self, val: Any) -> date | None:
        if isinstance(val, date):
            return val
        if isinstance(val, str):
            for fmt in ('%Y-%m-%d', '%m/%d/%Y'):
                try:
                    return datetime.strptime(val.strip(), fmt).date()
                except ValueError:
                    continue
        return None

    def _extract_revenue_detail(self, wb: Any) -> list[CanonicalRecord]:
        records = []
        if 'Revenue Detail' not in wb.sheetnames:
            return records
        ws = wb['Revenue Detail']
        ts = self._ingest_ts()
        as_of = self._as_of_from_filename()
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            label = str(row[0]).strip() if row[0] else ''
            due_date = self._safe_date(row[1]) if len(row) > 1 else None
            amount = self._safe_decimal(row[2]) if len(row) > 2 else None
            if not label or amount is None:
                continue
            records.append(CanonicalRecord(source='historical_revenue_detail', record_type='invoice', ingested_at=ts, as_of_date=as_of, confidence=DataConfidence.PERIODIC_ESTIMATE, payload={'label': label, 'due_date': due_date.isoformat() if due_date else None, 'balance': str(amount)}, raw_ref=f'Revenue Detail tab, {self.path.name}'))
        return records

    def _extract_cogs_detail(self, wb: Any) -> list[CanonicalRecord]:
        records = []
        if 'COGS Detail' not in wb.sheetnames:
            return records
        ws = wb['COGS Detail']
        ts = self._ingest_ts()
        as_of = self._as_of_from_filename()
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            label = str(row[0]).strip() if row[0] else ''
            vendor = str(row[1]).strip() if len(row) > 1 and row[1] else ''
            amount = self._safe_decimal(row[2]) if len(row) > 2 else None
            due_date = self._safe_date(row[3]) if len(row) > 3 else None
            if not label or amount is None:
                continue
            records.append(CanonicalRecord(source='historical_cogs_detail', record_type='purchase_order', ingested_at=ts, as_of_date=as_of, confidence=DataConfidence.PERIODIC_ESTIMATE, payload={'label': label, 'vendor': vendor, 'total': str(amount), 'due_date': due_date.isoformat() if due_date else None}, raw_ref=f'COGS Detail tab, {self.path.name}'))
        return records

    def _extract_expense_assumptions(self, wb: Any) -> list[CanonicalRecord]:
        records = []
        if 'Expense Assumptions' not in wb.sheetnames:
            return records
        ws = wb['Expense Assumptions']
        ts = self._ingest_ts()
        as_of = self._as_of_from_filename()
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            coa_code = str(row[0]).strip() if row[0] else ''
            label = str(row[1]).strip() if len(row) > 1 and row[1] else ''
            amount = self._safe_decimal(row[2]) if len(row) > 2 else None
            if not label or amount is None:
                continue
            records.append(CanonicalRecord(source='historical_expense_assumptions', record_type='pl_line', ingested_at=ts, as_of_date=as_of, confidence=DataConfidence.PERIODIC_ESTIMATE, payload={'account_code': coa_code, 'account_name': label, 'monthly_amounts': {'historical': str(amount)}}, raw_ref=f'Expense Assumptions tab, {self.path.name}'))
        return records

    def _extract_general_info(self, wb: Any) -> list[CanonicalRecord]:
        records = []
        if 'General Info' not in wb.sheetnames:
            return records
        ws = wb['General Info']
        ts = self._ingest_ts()
        as_of = self._as_of_from_filename()
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            label = str(row[0]).strip().lower() if row[0] else ''
            value = row[1] if len(row) > 1 else None
            if 'opening cash' in label or 'cash position' in label:
                amount = self._safe_decimal(value)
                if amount is not None:
                    records.append(CanonicalRecord(source='historical_opening_cash', record_type='opening_cash', ingested_at=ts, as_of_date=as_of, confidence=DataConfidence.MANUAL_ENTRY, payload={'amount': str(amount), 'label': label}, raw_ref=f'General Info tab, {self.path.name}'))
        return records
