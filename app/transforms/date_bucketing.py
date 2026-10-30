from __future__ import annotations
from datetime import date, timedelta

def next_friday(d: date) -> date:
    days_until_friday = (4 - d.weekday()) % 7
    return d + timedelta(days=days_until_friday)

def prev_friday(d: date) -> date:
    days_since_friday = (d.weekday() - 4) % 7
    return d - timedelta(days=days_since_friday)

def bucket_ar_to_week_ending_friday(due_date: date, forecast_start_friday: date) -> date:
    week_friday = next_friday(due_date)
    return max(week_friday, forecast_start_friday)

def bucket_po_to_week_ending_friday(due_date: date, forecast_start_friday: date) -> date:
    week_friday = prev_friday(due_date)
    return max(week_friday, forecast_start_friday)

def weekly_fridays(start_friday: date, n: int) -> list[date]:
    if start_friday.weekday() != 4:
        raise ValueError(f"start_friday must be a Friday, got {start_friday} ({start_friday.strftime('%A')}). Use next_friday() to find the next Friday from any date.")
    return [start_friday + timedelta(weeks=i) for i in range(n)]
