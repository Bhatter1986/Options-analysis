from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd
import time

router = APIRouter(prefix="/instruments", tags=["instruments"])

# ---- Always use repo copy (data/instruments.csv)
CSV_PATH = Path("data/instruments.csv")

# ---- In-memory cache
_df_cache: Optional[pd.DataFrame] = None
_last_loaded: Optional[float] = None

def _load_df(force: bool = False) -> pd.DataFrame:
    global _df_cache, _last_loaded
    if not force and _df_cache is not None:
        return _df_cache
    if not CSV_PATH.exists():
        raise HTTPException(status_code=500, detail=f"{CSV_PATH} not found")
    _df_cache = pd.read_csv(CSV_PATH)
    _last_loaded = time.time()
    return _df_cache

def _rows_dict(df: pd.DataFrame) -> List[Dict[str, Any]]:
    return df.to_dict(orient="records")

@router.get("/_debug")
def debug_status():
    return {
        "exists": CSV_PATH.exists(),
        "path": str(CSV_PATH),
        "rows": len(_df_cache) if _df_cache is not None else 0,
        "cols": list(_df_cache.columns) if _df_cache is not None else [],
        "ready": _df_cache is not None
    }

@router.get("")
def list_instruments(limit: int = 50):
    df = _load_df()
    return {"data": _rows_dict(df.head(limit))}

@router.get("/indices")
def indices(q: Optional[str] = None):
    df = _load_df()
    df = df[df["instrument_type"] == "INDEX"]
    if q:
        df = df[df["symbol_name"].str.contains(q, case=False)]
    return {"data": _rows_dict(df)}

@router.get("/search")
def search(q: str):
    df = _load_df()
    df = df[df["symbol_name"].str.contains(q, case=False) | df["underlying_symbol"].str.contains(q, case=False)]
    return {"data": _rows_dict(df.head(50))}

@router.get("/by-id")
def by_id(security_id: int):
    df = _load_df()
    row = df[df["security_id"] == security_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Not Found")
    return _rows_dict(row.head(1))[0]
