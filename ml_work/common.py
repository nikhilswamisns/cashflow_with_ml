"""Shared loading helpers for the ML work."""
from pathlib import Path
import warnings
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "ml_data" / "Zoho_history_2021-10-01_to_2026-10-07.xlsx"
OUT = Path(__file__).resolve().parent / "outputs"


def load_history() -> dict[str, pd.DataFrame]:
    return pd.read_excel(HISTORY, sheet_name=None)
