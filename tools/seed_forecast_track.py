"""Fill data/forecast_track.json from the runs already in the database (oldest first, same rule as live recording).

Usage:  python tools/seed_forecast_track.py [--since 2026-10-12]
Each run takes a few seconds (it computes the rules and ML lines once). Safe to repeat: the rule only ever keeps the
latest eligible prediction per week. Uses the model saved now (history through its own cut-off), so run it before a retrain.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402
from app.ml import track  # noqa: E402


def main() -> None:
    since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else "2026-10-12"
    runs = sorted((r for r in db.list_runs() if str(r["created_at"])[:10] >= since), key=lambda r: r["created_at"])
    print(f"{len(runs)} runs created since {since}")
    for r in runs:
        try:
            written = track.record_run(r["run_id"])
            print(f"  {str(r['created_at'])[:16]}  run_date {r['run_date']}  {r['run_id'][:8]}  wrote {written or '-'}")
        except Exception as e:  # noqa: BLE001
            print(f"  {str(r['created_at'])[:16]}  {r['run_id'][:8]}  skipped: {str(e)[:90]}")
    data = track.load()["weeks"]
    print("\nforecast_track.json now holds:")
    for w in sorted(data):
        p = data[w]
        print(f"  {w}  rules {p['rules']:>12,.0f}  ml {p['ml'] if p['ml'] is None else format(p['ml'], '12,.0f'):>12}  from run {p['run_id'][:8]} made {p['run_created'][:16]}")


if __name__ == "__main__":
    main()
