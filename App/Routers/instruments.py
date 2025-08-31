from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List
from pathlib import Path
import csv
import json

router = APIRouter(prefix="/instruments", tags=["Instruments"])

CSV_PATH       = Path("data/instruments.csv")
WATCHLIST_JSON = Path("data/watchlist.json")           # legacy (backend private)
PUBLIC_JSON    = Path("public/data/watchlist.json")    # optional (static served)

# sensible defaults (used if "step" missing)
DEFAULT_STEPS = {
    "IDX_I": 50,   # NIFTY-type indices
    "NSE_I": 50,
    "IDX_FO": 50,
    "NSE_E": 10,   # equities
    "BSE_E": 10,
}
# known ID-specific overrides (optional)
ID_STEPS = {
    13: 50,   # NIFTY 50 (ID)
    25: 100,  # BANKNIFTY (ID)
}

def _norm_row(id_: int, name: str, seg: str, step_raw: str | int | None) -> Dict[str, Any]:
    seg = (seg or "").strip()
    name = (name or "").strip()
    step: int
    try:
        step = int(step_raw) if step_raw not in (None, "",) else 0
    except Exception:
        step = 0
    if not step:
        step = ID_STEPS.get(id_) or DEFAULT_STEPS.get(seg, 50)
    return {"id": id_, "name": name, "segment": seg, "step": step}

def _load_from_csv() -> List[Dict[str, Any]]:
    if not CSV_PATH.exists():
        return []
    items: List[Dict[str, Any]] = []
    try:
        with CSV_PATH.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # expect at least: id,name,segment ; optional: step
            for row in reader:
                if not isinstance(row, dict):
                    continue
                try:
                    id_ = int((row.get("id") or "0").strip() or "0")
                except Exception:
                    id_ = 0
                name = (row.get("name") or "").strip()
                seg  = (row.get("segment") or "").strip()
                step = row.get("step")
                if name and seg:
                    items.append(_norm_row(id_, name, seg, step))
        return items
    except Exception as e:
        raise HTTPException(500, f"CSV load failed: {e}")

def _load_from_json(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        raw = obj.get("items", [])
        items: List[Dict[str, Any]] = []
        for x in raw:
            if not isinstance(x, dict):
                continue
            try:
                id_ = int(x.get("id", 0) or 0)
            except Exception:
                id_ = 0
            name = str(x.get("name", "")).strip()
            seg  = str(x.get("segment", "")).strip()
            step = x.get("step")
            if name and seg:
                items.append(_norm_row(id_, name, seg, step))
        return items
    except Exception as e:
        raise HTTPException(500, f"JSON load failed ({path}): {e}")

def _load_instruments() -> List[Dict[str, Any]]:
    """
    Priority:
      1) data/instruments.csv  (recommended)
      2) data/watchlist.json   (legacy backend)
      3) public/data/watchlist.json (optional static)
    """
    items = _load_from_csv()
    if not items:
        items = _load_from_json(WATCHLIST_JSON)
    if not items:
        items = _load_from_json(PUBLIC_JSON)
    if not items:
        raise HTTPException(500, "No instruments found in CSV/JSON.")
    return items

@router.get("")
def list_instruments():
    items = _load_instruments()
    return {"status": "success", "data": items}

@router.get("/filter")
def filter_instruments(q: str = Query("", description="case-insensitive contains match")):
    items = _load_instruments()
    ql = q.lower().strip()
    if not ql:
        return {"status": "success", "data": items}
    filtered = [x for x in items if ql in x["name"].lower()]
    return {"status": "success", "data": filtered}
