from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel

class CadenceTier(str, Enum):
    LIVE = 'live'
    PERIODIC = 'periodic'
    FIXED = 'fixed'
    MANUAL = 'manual'

class InputRequirement(BaseModel):
    source_name: str
    cadence_tier: CadenceTier
    blocking: bool
    last_provided_at: Optional[datetime] = None
    staleness_threshold_days: int = 7
    description: str = ''
    'Human-readable description of what this input feeds into.'
    feeds: list[str] = []
    'Which rows/sections of the matrix this input populates.'

class PreflightResult(BaseModel):
    missing_blocking: list[InputRequirement]
    'Run cannot produce delivery-ready output without these.'
    missing_optional: list[InputRequirement]
    'Run proceeds with fallback/held-flat data; confidence flagged.'
    stale: list[InputRequirement]
    "Present but past cadence threshold — warn, don't block."

    def is_runnable(self) -> bool:
        return len(self.missing_blocking) == 0

    def human_readable_messages(self) -> list[str]:
        messages = []
        for req in self.missing_blocking:
            messages.append(f"[BLOCKING] Please upload updated {req.source_name.replace('_', ' ').title()} — none on file yet. Required before a run can compute: {', '.join(req.feeds) or 'associated matrix rows'}.")
        for req in self.missing_optional:
            messages.append(f"[OPTIONAL] {req.source_name.replace('_', ' ').title()} not provided. Run will proceed using fallback figures (confidence: PERIODIC_ESTIMATE). Upload a file if you have one.")
        for req in self.stale:
            days_ago = None
            if req.last_provided_at:
                from datetime import datetime, timezone
                delta = datetime.now(timezone.utc) - req.last_provided_at
                days_ago = delta.days
            days_str = f'{days_ago} days ago' if days_ago is not None else 'some time ago'
            messages.append(f"[STALE] {req.source_name.replace('_', ' ').title()} was last provided {days_str}; expected cadence is every {req.staleness_threshold_days} days. Run will proceed using the held-flat prior figure (confidence: PERIODIC_ESTIMATE) — upload a refresh if you have one.")
        return messages
