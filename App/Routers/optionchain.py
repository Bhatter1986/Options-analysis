from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd
import time

router = APIRouter(prefix="/optionchain", tags=["optionchain"])

# CSV yahi expect kar rahe hain:
LOCAL_CSV = Path("data/option_chain.csv")

_df_cache: Optional[pd.DataFrame] = None
_last_loaded_ts: Optional[float] = None

def _csv_exists() -> bool:
    return LOCAL_CSV.exists() and LOCAL_CSV.is_file()

def _load_df(force: bool = False) -> pd.DataFrame:
    global _df_cache, _last_loaded_ts
    if not _csv_exists():
        raise FileNotFoundError(f"CSV not found at {LOCAL_CSV}")
    if (not force) and (_df_cache is not None):
        return _df_cache

    df = pd.read_csv(LOCAL_CSV, dtype=str, keep_default_na=False, na_filter=False)
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    _df_cache = df
    _last_loaded_ts = time.time()
    return _df_cache

def _rows_dict(df: pd.DataFrame) -> List[Dict[str, Any]]:
    return df.to_dict(orient="records")

@router.get("/_debug")
def optionchain_debug() -> Dict[str, Any]:
    info: Dict[str, Any] = {"exists": _csv_exists(), "path": str(LOCAL_CSV), "rows": 0, "ready": False}
    if not info["exists"]:
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

@router.get("")
def optionchain_list(limit: int = Query(10, ge=1, le=500)) -> Dict[str, Any]:
    try:
        df = _load_df()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV load failed: {e}")
    return {"data": _rows_dict(df.head(limit))}
