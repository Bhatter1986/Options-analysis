# App/Routers/instruments.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd
import time

router = APIRouter(prefix="/instruments", tags=["instruments"])

# --------------------------------------------------------------------
# CSV location: prefer repo copy. We DO NOT fetch externally here.
# --------------------------------------------------------------------
LOCAL_CSV = Path("data/instruments.csv")

# In-memory cache
_df_cache: Optional[pd.DataFrame] = None
_last_loaded_ts: Optional[float] = None
_last_loaded_path: Optional[str] = None


def _csv_exists() -> bool:
    return LOCAL_CSV.exists() and LOCAL_CSV.is_file()


def _load_df(force: bool = False) -> pd.DataFrame:
    """
    Load instruments CSV with robust dtypes and basic validation.
    Cached until explicitly refreshed.
    """
    global _df_cache, _last_loaded_ts, _last_loaded_path

    if not _csv_exists():
        raise FileNotFoundError(f"CSV not found at {LOCAL_CSV}")

    if (not force) and (_df_cache is not None):
        return _df_cache

    # Read as strings to preserve IDs and avoid numeric problems
    df = pd.read_csv(
        LOCAL_CSV,
        dtype=str,
        keep_default_na=False,
        na_filter=False,
    )

    # Normalize expected columns (rename if user provided capitals etc.)
    expected = ["security_id", "symbol_name", "underlying_symbol", "segment", "instrument_type"]
    lower_map = {c.lower(): c for c in df.columns}
    for col in expected:
        if col not in lower_map:
            raise ValueError(
                f"CSV missing required column '{col}'. "
                f"Found columns: {list(df.columns)}"
            )
    # Reorder + normalize to expected names
    df = df[[lower_map[c] for c in expected]]
    df.columns = expected

    # Strip whitespace
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    # Cache
    _df_cache = df
    _last_loaded_ts = time.time()
    _last_loaded_path = str(LOCAL_CSV)
    return _df_cache


def _rows_dict(df: pd.DataFrame) -> List[Dict[str, Any]]:
    return df.to_dict(orient="records")


def _contains_ci(series: pd.Series, q: str) -> pd.Series:
    q = q.strip().lower()
    return series.str.lower().str.contains(q, na=False)


# --------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------
@router.get("/_debug")
def instruments_debug() -> Dict[str, Any]:
    """
    Report where CSV is loaded from and size/columns.
    Forces a light read to reflect current status.
    """
    exists = _csv_exists()
    info: Dict[str, Any] = {
        "exists": exists,
        "path": str(LOCAL_CSV),
        "rows": 0,
        "cols": [],
        "ready": False,
    }
    if not exists:
        return info

    try:
        df = _load_df(force=True)
        info["rows"] = int(df.shape[0])
        info["cols"] = list(df.columns)
        info["ready"] = info["rows"] > 0
        info["loaded_at"] = _last_loaded_ts
    except Exception as e:
        info["error"] = str(e)
    return info


@router.post("/_refresh")
def instruments_refresh() -> Dict[str, Any]:
    """
    Drop cache and reload from disk.
    """
    global _df_cache
    _df_cache = None
    try:
        df = _load_df(force=True)
        return {
            "ok": True,
            "rows": int(df.shape[0]),
            "cols": list(df.columns),
            "path": str(LOCAL_CSV),
            "reloaded": True,
        }
    except Exception as e:
        return {"ok": False, "reloaded": False, "detail": str(e), "path": str(LOCAL_CSV)}


@router.get("")
def instruments_list(limit: int = Query(0, ge=0, le=10_000)) -> Dict[str, Any]:
    """
    Return all instruments (optionally capped by limit).
    """
    try:
        df = _load_df()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Instrument CSV not present on server")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV load failed: {e}")

    if limit and limit > 0:
        df = df.head(limit)

    return {"data": _rows_dict(df)}


@router.get("/indices")
def instruments_indices(q: Optional[str] = Query(None, description="Filter text (case-insensitive)")) -> Dict[str, Any]:
    """
    Return only index rows (instrument_type == 'INDEX'), optionally filtered by q.
    """
    try:
        df = _load_df()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV load failed: {e}")

    df_idx = df[df["instrument_type"].str.upper() == "INDEX"]

    if q:
        mask = (
            _contains_ci(df_idx["symbol_name"], q)
            | _contains_ci(df_idx["underlying_symbol"], q)
            | _contains_ci(df_idx["security_id"], q)
        )
        df_idx = df_idx[mask]

    return {"data": _rows_dict(df_idx)}


@router.get("/search")
def instruments_search(
    q: str = Query(..., min_length=1, description="Search in symbol_name, underlying_symbol, security_id (CI)"),
    limit: int = Query(25, ge=1, le=500),
) -> Dict[str, Any]:
    """
    Case-insensitive substring search over key text fields.
    """
    try:
        df = _load_df()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV load failed: {e}")

    mask = (
        _contains_ci(df["symbol_name"], q)
        | _contains_ci(df["underlying_symbol"], q)
        | _contains_ci(df["security_id"], q)
    )
    out = df[mask].head(limit)
    return {"data": _rows_dict(out)}


@router.get("/by-id")
def instruments_by_id(security_id: str = Query(..., description="Exact security_id match")) -> Dict[str, Any]:
    """
    Return a single row (exact security_id). security_id is treated as string.
    """
    try:
        df = _load_df()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV load failed: {e}")

    # exact string match
    row = df[df["security_id"] == str(security_id)]

    if row.empty:
        raise HTTPException(status_code=404, detail="Not Found")

    return _rows_dict(row.head(1))[0]
