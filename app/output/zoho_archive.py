"""Archive the Zoho data behind every forecast run, inside the project folder.

Each sync (Zoho live pull or snapshot upload) creates one folder:

    <archive dir>/Cash_Flow_Forecast_<forecast date>_generated_<local date>_<HHMM>/
        Zoho_data.xlsx          one sheet per dataset (invoices, sales orders, POs, bills, cash, cards, card txns)
                                plus a Summary sheet with counts and totals
        zoho_snapshot.json      the exact input the forecast was built from (can be re-run via
                                POST /api/forecast/run-from-snapshot)
        forecast_rules.json     the rules file in force at the time
        manifest.json           run id, forecast date, pull time, counts, totals
        Cash_Flow_Forecast_<date>_exported_<local date>_<HHMM>.xlsx   every export of this run is saved here too

<archive dir> = ZOHO_ARCHIVE_DIR from .env, or <project>/zoho_data_archive when it is not set.

Archiving never blocks a sync or an export: any error is logged and the forecast is still returned.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARCHIVE_DIR = "zoho_data_archive"


def archive_root() -> Path:
    """Where run folders are written.

    Set ZOHO_ARCHIVE_DIR in .env to change it (absolute path, or a path relative to the project folder).
    Not set -> <project>/zoho_data_archive."""
    try:
        import dotenv
        dotenv.load_dotenv(PROJECT_ROOT / ".env", override=False)
    except Exception:
        pass
    raw = (os.getenv("ZOHO_ARCHIVE_DIR") or "").strip().strip('"').strip("'")
    if not raw:
        return PROJECT_ROOT / DEFAULT_ARCHIVE_DIR
    p = Path(os.path.expandvars(raw)).expanduser()
    return p if p.is_absolute() else PROJECT_ROOT / p
RULES_FILE = PROJECT_ROOT / "app" / "config" / "forecast_rules.json"

DATASETS = [  # (snapshot key, sheet name, amount field used for the Summary total)
    ("invoices", "Invoices", "balance"),
    ("sales_orders", "Sales Orders", "uninvoiced"),
    ("purchase_orders", "Purchase Orders", "unbilled"),
    ("bills", "Bills", "balance"),
    ("cash_accounts", "Cash Accounts", "balance"),
    ("card_accounts", "Card Accounts", "balance"),
    ("card_transactions", "Card Transactions", "credit"),
]


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _folder_name(forecast_date: date, when: datetime) -> str:
    return f"Cash_Flow_Forecast_{forecast_date:%Y-%m-%d}_generated_{when:%Y-%m-%d_%H%M}"


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    k = 2
    while (path.parent / f"{path.name}_{k}").exists():
        k += 1
    return path.parent / f"{path.name}_{k}"


def _summary(snap: dict) -> dict:
    out = {}
    for key, _, amt in DATASETS:
        rows = snap.get(key) or []
        out[key] = {"count": len(rows), "total": round(sum(float(r.get(amt) or 0) for r in rows if isinstance(r, dict)), 2),
                    "total_of": amt}
    return out


def _cell(v):
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return v


def _write_workbook(path: Path, snap: dict, manifest: dict) -> None:
    wb = openpyxl.Workbook()
    head_fill, head_font = PatternFill("solid", fgColor="1F4E79"), Font(bold=True, color="FFFFFF")
    ws = wb.active
    ws.title = "Summary"
    rows = [("Forecast date (week 1)", manifest["forecast_date"]),
            ("Zoho data pulled (UTC)", manifest.get("pulled_at_utc") or ""),
            ("Archived (local time)", manifest["archived_at_local"]),
            ("Run id", manifest["run_id"]),
            ("Source", manifest.get("source_label") or manifest.get("source") or ""),
            ("Zoho org", manifest.get("zoho_org") or ""), ("", "")]
    for r in rows:
        ws.append(list(r))
    ws.append(["Dataset", "Records", "Total", "Total of field"])
    for c in ws[ws.max_row]:
        c.fill, c.font = head_fill, head_font
    for key, sheet, _ in DATASETS:
        s = manifest["datasets"][key]
        ws.append([sheet, s["count"], s["total"], s["total_of"]])
    cyc = snap.get("card_cycle") or {}
    if cyc:
        ws.append([])
        ws.append(["Card cycle pulled", f"{cyc.get('start')} to {cyc.get('close')}"])
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 28, 34
    ws.column_dimensions["C"].width, ws.column_dimensions["D"].width = 18, 16
    for row in ws.iter_rows(min_row=9, min_col=3, max_col=3):
        for c in row:
            c.number_format = "#,##0.00"

    for key, sheet, _ in DATASETS:
        recs = [r for r in (snap.get(key) or []) if isinstance(r, dict)]
        ws = wb.create_sheet(sheet)
        cols: list[str] = []
        for r in recs:
            for k in r:
                if k not in cols:
                    cols.append(k)
        if not cols:
            ws.append(["No records in this pull"])
            continue
        ws.append(cols)
        for c in ws[1]:
            c.fill, c.font = head_fill, head_font
        for r in recs:
            ws.append([_cell(r.get(k)) for k in cols])
        for i, k in enumerate(cols, 1):
            width = max([len(str(k))] + [len(str(_cell(r.get(k)) or "")) for r in recs[:200]])
            ws.column_dimensions[get_column_letter(i)].width = min(max(10, width + 2), 60)
        ws.freeze_panes = "A2"
    wb.save(path)


def archive_snapshot(run_id: str, snap: dict, forecast_date: date, source: str = "", label: str = "",
                     when: Optional[datetime] = None) -> Optional[Path]:
    """Create the archive folder for one run. Returns the folder, or None if archiving failed."""
    try:
        when = when or _local_now()
        folder = _unique(archive_root() / _folder_name(forecast_date, when))
        folder.mkdir(parents=True, exist_ok=False)
        manifest = {
            "run_id": run_id,
            "forecast_date": forecast_date.isoformat(),
            "pulled_at_utc": snap.get("pulled_at"),
            "archived_at_local": when.strftime("%Y-%m-%d %H:%M:%S (UTC%z)").strip(),
            "source": source, "source_label": label,
            "snapshot_source": snap.get("source"),
            "zoho_org": snap.get("organization_id") or snap.get("org_id"),
            "datasets": _summary(snap),
            "exports": [],
        }
        (folder / "zoho_snapshot.json").write_text(json.dumps(snap, indent=2, ensure_ascii=False, default=str),
                                                   encoding="utf-8")
        if RULES_FILE.exists():
            shutil.copy2(RULES_FILE, folder / "forecast_rules.json")
        _write_workbook(folder / "Zoho_data.xlsx", snap, manifest)
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Zoho data for run %s archived to %s", run_id, folder)
        return folder
    except Exception:  # never block a sync because of the archive
        logger.exception("Could not archive the Zoho data for run %s", run_id)
        return None


def find_run_folder(run_id: str) -> Optional[Path]:
    root = archive_root()
    if not root.exists():
        return None
    for m in sorted(root.glob("*/manifest.json")):
        try:
            if json.loads(m.read_text(encoding="utf-8")).get("run_id") == run_id:
                return m.parent
        except Exception:
            continue
    return None


def save_export(run_id: str, forecast_date: date, content: bytes, snap: Optional[dict] = None) -> Optional[Path]:
    """Save an exported forecast next to the Zoho data it was built from.

    Runs synced before this feature existed get their folder created here, from the snapshot saved in the database."""
    try:
        folder = find_run_folder(run_id)
        if folder is None and snap is not None:
            folder = archive_snapshot(run_id, snap, forecast_date, "zoho_snapshot", "archived at export (saved run)")
        if folder is None:
            return None
        now = _local_now()
        path = _unique_file(folder / f"Cash_Flow_Forecast_{forecast_date:%Y-%m-%d}_exported_{now:%Y-%m-%d_%H%M}.xlsx")
        path.write_bytes(content)
        mpath = folder / "manifest.json"
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        manifest.setdefault("exports", []).append({"file": path.name, "exported_at_local": now.strftime("%Y-%m-%d %H:%M:%S")})
        mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
    except Exception:
        logger.exception("Could not save the export of run %s to the archive", run_id)
        return None


def _unique_file(path: Path) -> Path:
    if not path.exists():
        return path
    k = 2
    while (path.with_name(f"{path.stem}_{k}{path.suffix}")).exists():
        k += 1
    return path.with_name(f"{path.stem}_{k}{path.suffix}")
