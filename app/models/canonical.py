from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class DataConfidence(str, Enum):
    VERIFIED_LIVE = 'verified_live'
    'Matched directly to a file-upload or live source record.'
    MANUAL_ENTRY = 'manual_entry'
    'Human typed it in — e.g. Opening Cash Position.'
    PERIODIC_ESTIMATE = 'periodic_estimate'
    'Trailing-average / run-rate held flat; source is stale or absent.'
    FIXED_ASSUMPTION = 'fixed_assumption'
    'Contractual / known fixed dollar amount (e.g. rent, salaries).'
    ESTIMATE_BILLS_GAP = 'estimate_bills_gap'
    'Closed PO with no matching bill on file — true balance unknown (Section 4.6).'
    PLACEHOLDER = 'placeholder_needs_trueup'
    'Newly appended week; no data yet. All cells 0 until a data refresh.'

class CanonicalRecord(BaseModel):
    record_id: UUID = Field(default_factory=uuid4)
    source: str
    record_type: str
    ingested_at: datetime
    as_of_date: date
    confidence: DataConfidence
    payload: dict[str, Any]
    raw_ref: Optional[str] = None
    "Pointer back to source row/file for audit trail (e.g. 'row 14 of ar_2026-08-14.csv')."
    model_config = {'frozen': True}

class OpeningCash(BaseModel):
    amount: Decimal
    as_of_date: date
    entered_by: str
    source: str = 'manual'
    model_config = {'frozen': True}

class Run(BaseModel):
    run_id: UUID = Field(default_factory=uuid4)
    run_date: date
    'The forecast_start_friday for this run.'
    created_at: datetime
    input_snapshot_ids: list[UUID]
    'Every CanonicalRecord batch used — immutable reference.'
    matrix: Optional[dict] = None
    'Section 5 output (WeeklyMatrix serialized). None until build completes.'
    validation_result: Optional[dict] = None
    'Section 7 output. None until validation runs.'
    preflight_result: Optional[dict] = None
    'Section 8 output captured at run time.'
    opening_cash_amount: Optional[Decimal] = None
    opening_cash_date: Optional[date] = None

def safe_parse_date(val: Any) -> date:
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if not val:
        return date.today()
    s = str(val).strip()
    if 'T' in s:
        s = s.split('T')[0]
    elif ' ' in s:
        s = s.split(' ')[0]
    try:
        return date.fromisoformat(s)
    except Exception:
        pass
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%d/%m/%Y', '%d/%m/%y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return date.today()

def safe_parse_datetime(val: Any) -> datetime:
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        from datetime import timezone
        return datetime(val.year, val.month, val.day, tzinfo=timezone.utc)
    if not val:
        from datetime import timezone
        return datetime.now(timezone.utc)
    s = str(val).strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass
    from datetime import timezone
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return datetime.now(timezone.utc)
