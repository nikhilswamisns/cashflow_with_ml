from __future__ import annotations
from typing import Optional
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4
import os
import sqlite3

_env_path = os.environ.get('DATABASE_PATH')
DB_PATH = Path(_env_path) if _env_path else Path(__file__).parent.parent / 'data' / 'cashflow.db'

def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = _get_conn()
    conn.executescript('\n        CREATE TABLE IF NOT EXISTS runs (\n            run_id TEXT PRIMARY KEY,\n            run_date TEXT NOT NULL,\n            created_at TEXT NOT NULL,\n            opening_cash_amount TEXT,\n            opening_cash_date TEXT,\n            is_first_run INTEGER DEFAULT 1,\n            matrix_json TEXT,\n            validation_json TEXT,\n            preflight_json TEXT\n        );\n\n        CREATE TABLE IF NOT EXISTS uploads (\n            upload_id TEXT PRIMARY KEY,\n            run_id TEXT,\n            source_name TEXT NOT NULL,\n            filename TEXT NOT NULL,\n            uploaded_at TEXT NOT NULL,\n            record_count INTEGER DEFAULT 0,\n            records_json TEXT\n        );\n\n        CREATE TABLE IF NOT EXISTS opening_cash (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            amount TEXT NOT NULL,\n            as_of_date TEXT NOT NULL,\n            entered_by TEXT NOT NULL,\n            entered_at TEXT NOT NULL\n        );\n    ')
    conn.commit()
    conn.close()

def create_run(run_date: date, is_first_run: bool=True) -> str:
    run_id = str(uuid4())
    conn = _get_conn()
    conn.execute('INSERT INTO runs (run_id, run_date, created_at, is_first_run) VALUES (?, ?, ?, ?)', (run_id, run_date.isoformat(), datetime.now(timezone.utc).isoformat(), 1 if is_first_run else 0))
    conn.commit()
    conn.close()
    return run_id

def list_runs() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute('SELECT run_id, run_date, created_at, opening_cash_amount, is_first_run FROM runs ORDER BY created_at DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_run(run_id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute('SELECT * FROM runs WHERE run_id = ?', (run_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_run_matrix(run_id: str, matrix_json: str, validation_json: str, preflight_json: str) -> None:
    conn = _get_conn()
    conn.execute('UPDATE runs SET matrix_json=?, validation_json=?, preflight_json=? WHERE run_id=?', (matrix_json, validation_json, preflight_json, run_id))
    conn.commit()
    conn.close()

def set_run_opening_cash(run_id: str, amount: Decimal, as_of: date) -> None:
    conn = _get_conn()
    conn.execute('UPDATE runs SET opening_cash_amount=?, opening_cash_date=? WHERE run_id=?', (str(amount), as_of.isoformat(), run_id))
    conn.commit()
    conn.close()

def save_upload(run_id: str, source_name: str, filename: str, records: list) -> str:
    upload_id = str(uuid4())
    conn = _get_conn()
    records_json = json.dumps([{'record_id': str(r.record_id), 'source': r.source, 'record_type': r.record_type, 'ingested_at': r.ingested_at.isoformat(), 'as_of_date': r.as_of_date.isoformat(), 'confidence': r.confidence.value, 'payload': r.payload, 'raw_ref': r.raw_ref} for r in records])
    conn.execute('INSERT INTO uploads (upload_id, run_id, source_name, filename, uploaded_at, record_count, records_json) VALUES (?, ?, ?, ?, ?, ?, ?)', (upload_id, run_id, source_name, filename, datetime.now(timezone.utc).isoformat(), len(records), records_json))
    conn.commit()
    conn.close()
    return upload_id

def save_snapshot(run_id: str, source_name: str, filename: str, snapshot: dict) -> str:
    """Store a raw Zoho snapshot (v10 engine input) with its run."""
    upload_id = str(uuid4())
    conn = _get_conn()
    conn.execute('INSERT INTO uploads (upload_id, run_id, source_name, filename, uploaded_at, record_count, records_json) VALUES (?, ?, ?, ?, ?, ?, ?)', (upload_id, run_id, source_name, filename, datetime.now(timezone.utc).isoformat(), sum(len(v) for v in snapshot.values() if isinstance(v, list)), json.dumps([snapshot], default=str)))
    conn.commit()
    conn.close()
    return upload_id

def get_uploads_for_run(run_id: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute('SELECT * FROM uploads WHERE run_id = ? ORDER BY uploaded_at DESC', (run_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_effective_uploads_for_run(run_id: str) -> list[dict]:
    conn = _get_conn()
    sources = conn.execute("SELECT DISTINCT source_name FROM uploads WHERE source_name != 'zoho_snapshot'").fetchall()
    source_names = [s['source_name'] for s in sources]
    uploads = []
    for s_name in source_names:
        row = conn.execute('SELECT * FROM uploads WHERE run_id = ? AND source_name = ? ORDER BY uploaded_at DESC LIMIT 1', (run_id, s_name)).fetchone()
        if not row:
            row = conn.execute('SELECT * FROM uploads WHERE source_name = ? ORDER BY uploaded_at DESC LIMIT 1', (s_name,)).fetchone()
        if row:
            uploads.append(dict(row))
    conn.close()
    return uploads

def get_latest_run_id() -> Optional[str]:
    conn = _get_conn()
    row = conn.execute('SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 1').fetchone()
    conn.close()
    return row['run_id'] if row else None

def get_latest_upload_timestamps() -> dict[str, datetime]:
    conn = _get_conn()
    rows = conn.execute('SELECT source_name, MAX(uploaded_at) as latest FROM uploads GROUP BY source_name').fetchall()
    result = {}
    for row in rows:
        result[row['source_name']] = datetime.fromisoformat(row['latest'])
    oc_row = conn.execute('SELECT entered_at FROM opening_cash ORDER BY entered_at DESC LIMIT 1').fetchone()
    if oc_row:
        result['opening_cash'] = datetime.fromisoformat(oc_row['entered_at'])
    conn.close()
    return result

def get_latest_opening_cash() -> dict | None:
    conn = _get_conn()
    row = conn.execute('SELECT * FROM opening_cash ORDER BY entered_at DESC LIMIT 1').fetchone()
    conn.close()
    return dict(row) if row else None

def save_opening_cash(amount: Decimal, as_of: date, entered_by: str) -> None:
    conn = _get_conn()
    conn.execute('INSERT INTO opening_cash (amount, as_of_date, entered_by, entered_at) VALUES (?, ?, ?, ?)', (str(amount), as_of.isoformat(), entered_by, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

def get_most_recent_ending_cash() -> Decimal | None:
    conn = _get_conn()
    row = conn.execute('SELECT matrix_json FROM runs WHERE matrix_json IS NOT NULL ORDER BY created_at DESC LIMIT 1').fetchone()
    conn.close()
    if not row or not row['matrix_json']:
        return None
    try:
        matrix_data = json.loads(row['matrix_json'])
        weeks = matrix_data.get('weeks', [])
        if weeks:
            last_week = weeks[-1]
            return Decimal(str(last_week.get('ending_cash', '0')))
    except Exception:
        pass
    return None
