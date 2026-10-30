"""Machine-learning layer for the cash-flow engine.

The deterministic v10 engine stays the source of truth.  This package only replaces three *timing* guesses
(when a customer invoice / sales order is paid to us, and when we pay a vendor bill) with values learned from the
5-year Zoho history, and adds probability bands (P10/P50/P90) around the forecast.  Everything is switched
by  "ml": {"enabled": true}  in app/config/forecast_rules.json  - with it off the engine behaves exactly as before.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = ROOT / "data" / "ml_models"
MODEL_FILE = MODEL_DIR / "timing_models.joblib"
CARD_FILE = MODEL_DIR / "model_card.json"
HISTORY_DIR = ROOT / "ml_data"          # drop Zoho_history_*.xlsx here (tools/export_history.py writes to exports/)
