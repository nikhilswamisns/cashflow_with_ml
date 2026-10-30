"""Train / test the ML timing models from the Zoho history workbook.

    python tools\\train_ml.py                       train from the newest ml_data\\Zoho_history_*.xlsx
    python tools\\train_ml.py --file D:\\x.xlsx      train from a specific workbook
    python tools\\train_ml.py --backtest            also run the ML-vs-rules backtest and print the result
    python tools\\train_ml.py --backtest-only       just the backtest

Get a fresh workbook first (read-only Zoho pull, 5 years):  python tools\\export_history.py --days 1825
then copy exports\\Zoho_history_*.xlsx into the ml_data folder.  Run from the app folder with the venv active.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.train import latest_history_file, train  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--backtest-only", action="store_true")
    a = ap.parse_args()
    path = Path(a.file) if a.file else latest_history_file()
    if path is None:
        sys.exit("No history workbook found. Put Zoho_history_*.xlsx in the ml_data folder or use --file.")
    print(f"History file: {path}")
    if not a.backtest_only:
        meta = train(path)
        print(json.dumps(meta, indent=2))
    if a.backtest or a.backtest_only:
        from app.ml.backtest import run_backtest
        rep = run_backtest(path)
        for kind, v in rep.items():
            print(f"\n== {kind}")
            for name in ("rule", "ml"):
                print(f"  {name:5s}", v["average"][name])


if __name__ == "__main__":
    main()
