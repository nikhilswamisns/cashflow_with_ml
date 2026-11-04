"""Small in-process cache for slow, read-only ML results (the run comparison takes about 2 s).

The key must contain everything the result depends on. `fingerprint()` builds that from the run's data and the
files that change the forecast (rules, assumptions, the Excel template, the saved timing model), so an edit to any of
them gives a new key and the result is recomputed. Nothing is ever served stale.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Hashable

from app.ml import MODEL_FILE, ROOT

_FILES_THAT_CHANGE_RESULTS = [*sorted((ROOT / "app" / "config").glob("*.json")),
                              ROOT / "app" / "templates" / "v10_template.xlsx", MODEL_FILE]


def _stat(p: Path) -> tuple:
    try:
        s = p.stat()
        return (p.name, s.st_mtime_ns, s.st_size)
    except OSError:
        return (p.name, None, None)


def _digest(obj: Any) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def fingerprint(*data: Any, files: list[Path] | None = None) -> tuple:
    """Key for a result: a hash of the data it was computed from plus the stat of every file that affects it."""
    return (_digest(data), tuple(_stat(p) for p in (files if files is not None else _FILES_THAT_CHANGE_RESULTS)))


class ResultCache:
    """Keeps the last `size` results. One lock, so identical concurrent requests compute once and share it."""

    def __init__(self, size: int = 8):
        self.size = size
        self._items: OrderedDict[Hashable, Any] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_compute(self, key: Hashable, compute: Callable[[], Any]) -> Any:
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
            value = compute()                    # an error propagates and nothing is stored
            self._items[key] = value
            while len(self._items) > self.size:
                self._items.popitem(last=False)
            return value
