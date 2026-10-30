from __future__ import annotations
from datetime import date, datetime
from typing import Protocol, runtime_checkable
from app.models.canonical import CanonicalRecord
from app.models.preflight import CadenceTier

@runtime_checkable
class DataSourceAdapter(Protocol):
    source_name: str
    cadence_tier: CadenceTier

    def fetch(self, as_of: date) -> list[CanonicalRecord]:
        ...

    def last_updated(self) -> datetime | None:
        ...

    def is_stale(self, as_of: date) -> bool:
        ...
