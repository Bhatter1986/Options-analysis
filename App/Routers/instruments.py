# App/Routers/instruments.py
from __future__ import annotations

from fastapi import APIRouter, Query
from pathlib import Path
from typing import Any, Dict, Optional, List

import pandas as pd

router = APIRouter(prefix="/instruments", tags=["Instruments"])

# --- Paths & cache ---
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[2]   # <repo root>
DATA_DIR = ROOT / "data"
CSV_FILE = DATA_DIR / "instruments.csv"          # <-- yahi read hoga
# ---- Utils ------------------------------------------------------------------
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase + underscore columns so header names become resilient."""
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _load_csv(force: bool = False) -> pd.DataFrame:
    """Load CSV once & cache. Auto-refresh if file mtime changes or force=True."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_FILE.exists():
        return pd.DataFrame()

    mtime = CSV_FILE.stat().st_mtime
    if force or _cache["df"] is None or _cache["ts"] != mtime:
        df = pd.read_csv(CSV_FILE)
        df = _normalize_columns(df)
        # keep security_id as string for exact match
        if "security_id" in df.columns:
            df["security_id"] = df["security_id"].astype(str)

        _cache.update(
            {"df": df, "ts": mtime, "rows": len(df), "cols": list(df.columns)}
        )
    return _cache["df"]


# ---- Debug & maintenance ----------------------------------------------------
@router.get("/_debug")
def debug() -> Dict[str, Any]:
    exists = CSV_FILE.exists()
    size = CSV_FILE.stat().st_size if exists else 0
    df = _load_csv()
    sample: List[Dict[str, Any]] = []
    if not df.empty:
        sample = df.head(3).to_dict(orient="records")
    return {
        "csv_path": str(CSV_FILE),
        "exists": exists,
        "size": size,
        "rows": int(_cache.get("rows", 0)),
        "cols": _cache.get("cols", []),
        "sample": sample,
    }


@router.post("/_refresh")
def refresh() -> Dict[str, Any]:
    df = _load_csv(force=True)
    return {"ok": True, "rows": len(df), "cols": list(df.columns)}


# ---- API: list, indices, search, by-id -------------------------------------
@router.get("")
def list_all(limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    df = _load_csv()
    if df.empty:
        return {"count": 0, "data": []}
    data = df.head(limit).to_dict(orient="records")
    return {"count": len(data), "data": data}


@router.get("/indices")
def list_indices(
    q: Optional[str] = None, limit: int = Query(50, ge=1, le=500)
) -> Dict[str, Any]:
    df = _load_csv()
    if df.empty:
        return {"count": 0, "data": []}

    # Match INDEX via common columns, else fallback to full-row text search
    mask = pd.Series(False, index=df.index)
    for col in ["instrument_type", "series", "instrument"]:
        if col in df.columns:
            mask |= df[col].astype(str).str.upper().str.contains(r"\bINDEX\b", na=False)

    df_idx = df[mask]
    if q:
        row_text = df_idx.astype(str).fillna("").agg(" ".join, axis=1)
        df_idx = df_idx[row_text.str.contains(q, case=False, na=False)]

    data = df_idx.head(limit).to_dict(orient="records")
    return {"count": len(data), "data": data}


@router.get("/search")
def generic_search(q: str, limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    df = _load_csv()
    if df.empty or not q:
        return {"count": 0, "data": []}
    row_text = df.astype(str).fillna("").agg(" ".join, axis=1)
    df2 = df[row_text.str.contains(q, case=False, na=False)]
    data = df2.head(limit).to_dict(orient="records")
    return {"count": len(data), "data": data}


@router.get("/by-id")
def by_id(security_id: str) -> Dict[str, Any]:
    df = _load_csv()
    if df.empty or "security_id" not in df.columns:
        return {"detail": "Not Found"}
    pick = df[df["security_id"].astype(str) == str(security_id)]
    if pick.empty:
        return {"detail": "Not Found"}
    return pick.head(1).to_dict(orient="records")[0]
