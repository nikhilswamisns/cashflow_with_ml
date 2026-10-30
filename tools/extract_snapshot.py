"""Save the newest Zoho snapshot stored in your dashboard database as a .json file (no Zoho, no server needed).

    python tools\\extract_snapshot.py                      newest run in data\\cashflow.db -> data\\snapshot_<date>_from_db.json
    python tools\\extract_snapshot.py --db data\\1111.db     use another database
    python tools\\extract_snapshot.py --list                show the runs that have a snapshot
    python tools\\extract_snapshot.py --run-id f595c788      a specific run (the first letters of its id are enough)
Then:  python tools\\make_forecast.py --snapshot data\\snapshot_<date>_from_db.json --ml both --outlook --bands
Only reads the database; never changes it. Standard library only.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "cashflow.db"))
    ap.add_argument("--run-id")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    db = Path(a.db)
    if not db.exists():
        sys.exit(f"Database not found: {db}")
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT r.run_id, r.run_date, r.created_at FROM runs r WHERE EXISTS "
        "(SELECT 1 FROM uploads u WHERE u.run_id=r.run_id AND u.source_name='zoho_snapshot') "
        "ORDER BY r.run_date DESC, r.created_at DESC").fetchall()
    if not rows:
        sys.exit("No run with a Zoho snapshot in this database.")
    if a.list:
        for rid, rd, ca in rows:
            print(f"{rd}   created {str(ca)[:16]}   run {rid[:8]}")
        return
    pick = next((r for r in rows if r[0].startswith(a.run_id)), None) if a.run_id else rows[0]
    if pick is None:
        sys.exit(f"Run {a.run_id} not found. Use --list.")
    rec = con.execute("SELECT records_json FROM uploads WHERE run_id=? AND source_name='zoho_snapshot' "
                      "ORDER BY uploaded_at DESC", (pick[0],)).fetchone()
    snap = json.loads(rec[0])[0]
    out = Path(a.out) if a.out else ROOT / "data" / f"snapshot_{snap.get('run_date', pick[1])}_from_db.json"
    out.write_text(json.dumps(snap), encoding="utf-8")
    print(f"Saved {out}")
    print(f"  week 1 = Friday {snap.get('run_date')},  pulled from Zoho {str(snap.get('pulled_at'))[:16]},  "
          f"{len(snap.get('invoices', []))} invoices, {len(snap.get('sales_orders', []))} sales orders, "
          f"{len(snap.get('bills', []))} bills")


if __name__ == "__main__":
    main()