# App/Routers/instruments.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("instruments")
router = APIRouter(prefix="/instruments", tags=["instruments"])

# ----------------------------
# CSV paths (safe resolution)
# ----------------------------
# Try both repo root and data/ (works on Render & locally)
HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2] if (HERE.name == "instruments.py") else HERE
CANDIDATE_CSV = [
    PROJECT_ROOT / "instruments.csv",
    PROJECT_ROOT / "data" / "instruments.csv",
]

# In-memory cache
_df: Optional[pd.DataFrame] = None
_cols: List[str] = []
_csv_path: Optional[Path] = None


def _load_csv() -> pd.DataFrame:
    """Load instruments.csv from any of the candidate paths."""
    global _df, _cols, _csv_path

    for p in CANDIDATE_CSV:
        if p.exists():
            logger.info("Loading instruments from %s", p)
            df = pd.read_csv(p, dtype=str).fillna("")
            _df = df
            _cols = list(df.columns)
            _csv_path = p
            return df

    paths_str = ", ".join(str(p) for p in CANDIDATE_CSV)
    logger.error("instruments.csv not found in: %s", paths_str)
    raise FileNotFoundError(f"instruments.csv not found in: {paths_str}")


def _ensure_loaded() -> pd.DataFrame:
    return _df if _df is not None else _load_csv()


def _rows_to_dict(df: pd.DataFrame, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if limit is not None:
        df = df.head(limit)
    return df.to_dict(orient="records")


# ----------------------------
# Endpoints
# ----------------------------

@router.get("/_debug")
def debug() -> Dict[str, Any]:
    """
    Lightweight status — shows whether CSV is loaded and a preview of columns.
    """
    try:
        df = _ensure_loaded()
        return {
            "ok": True,
            "exists": True,
            "path": str(_csv_path) if _csv_path else None,
            "rows": int(df.shape[0]),
            "cols": list(df.columns),
            "ready": True,
        }
    except FileNotFoundError:
        return {"ok": False, "exists": False, "rows": 0, "cols": [], "ready": False}


@router.post("/_refresh")
def refresh() -> Dict[str, Any]:
    """
    Re-read the CSV from disk and refresh cache.
    """
    df = _load_csv()
    return {"ok": True, "rows": int(df.shape[0]), "path": str(_csv_path)}


@router.get("")
def list_instruments(limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    """
    First N instruments (default 50).
    """
    df = _ensure_loaded()
    return {"rows": _rows_to_dict(df, limit=limit)}


@router.get("/indices")
def list_indices(q: Optional[str] = Query(None, description="case-insensitive filter")) -> Dict[str, Any]:
    """
    Only indices (works for NSE/BSE master where indices are tagged).
    We try common patterns:
      - instrument_type == 'INDEX'
      - segment == 'I'
    """
    df = _ensure_loaded()

    # Broad filter for "index-ness"
    mask = (df.get("instrument_type", "") == "INDEX") | (df.get("segment", "") == "I")
    out = df[mask].copy()

    if q:
        ql = q.lower()
        cols = [c for c in ["symbol_name", "underlying_symbol"] if c in out.columns]
        if cols:
            mask_q = False
            for c in cols:
                mask_q = mask_q | out[c].str.lower().str.contains(ql, na=False)
            out = out[mask_q]

    return {"rows": _rows_to_dict(out)}


@router.get("/search")
def search(q: str = Query(..., min_length=1)) -> Dict[str, Any]:
    """
    Generic search across symbol_name / underlying_symbol / security_id (contains).
    """
    df = _ensure_loaded()
    ql = q.lower()

    mask = False
    if "symbol_name" in df.columns:
        mask = mask | df["symbol_name"].str.lower().str.contains(ql, na=False)
    if "underlying_symbol" in df.columns:
        mask = mask | df["underlying_symbol"].str.lower().str.contains(ql, na=False)
    if "security_id" in df.columns:
        mask = mask | df["security_id"].str.lower().str.contains(ql, na=False)

    out = df[mask] if isinstance(mask, pd.Series) else df.iloc[0:0]
    return {"rows": _rows_to_dict(out)}


@router.get("/by-id")
def by_id(security_id: str = Query(..., description="Exact security_id (string or number as string)")) -> Dict[str, Any]:
    """
    Return a single instrument row by exact security_id.
    """
    df = _ensure_loaded()
    if "security_id" not in df.columns:
        raise HTTPException(status_code=500, detail="CSV missing 'security_id' column")

    # string-safe equality match
    out = df[df["security_id"].astype(str) == str(security_id)]

    if out.empty:
        raise HTTPException(status_code=404, detail="Not Found")

    # Return the single row as object (not list)
    return out.iloc[0].to_dict()
