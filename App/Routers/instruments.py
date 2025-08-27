from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd
import time

router = APIRouter(prefix="/instruments", tags=["instruments"])

# ---- CSV path preference: repo copy > /tmp fallback
LOCAL_CSV = Path("data/instruments.csv")
TMP_CSV   = Path("/tmp/instruments.csv")
CSV_PATH  = LOCAL_CSV if LOCAL_CSV.exists() else TMP_CSV

# ---- In-memory cache
_df_cache: Optional[pd.DataFrame] = None
_last_loaded: Optional[float] = None

def _load_df(force: bool = False) -> pd.DataFrame:
    global _df_cache, _last_loaded
    if not force and _df_cache is not None:
        return _df_cache
    if not CSV_PATH.exists():
        # graceful empty frame
        _df_cache = pd.DataFrame()
        _last_loaded = time.time()
        return _df_cache
    df = pd.read_csv(CSV_PATH)
    # Normalize columns that are commonly used
    # Try to be tolerant about casing / variants
    colmap = {c.lower(): c for c in df.columns}
    def pick(*names):
        for n in names:
            if n in colmap:
                return colmap[n]
        return None
    # Ensure these logical names exist (create if absent)
    sid = pick("security_id","secid","id")
    sym = pick("symbol_name","symbol","name")
    und_sym = pick("underlying_symbol","underlying","root")
    seg = pick("segment","seg")
    inst = pick("instrument_type","instrument","type")
    # Standardize view for endpoints
    std = {}
    if sid and sid not in ("security_id"):
        std["security_id"] = df[sid].astype(str)
    if sym and sym not in ("symbol_name"):
        std["symbol_name"] = df[sym].astype(str)
    if und_sym and und_sym not in ("underlying_symbol"):
        std["underlying_symbol"] = df[und_sym].astype(str)
    if seg and seg not in ("segment"):
        std["segment"] = df[seg].astype(str)
    if inst and inst not in ("instrument_type"):
        std["instrument_type"] = df[inst].astype(str)
    for k,v in std.items():
        df[k] = v
    # stringify security_id for robust matching
    if "security_id" in df.columns:
        df["security_id"] = df["security_id"].astype(str)
    _df_cache = df
    _last_loaded = time.time()
    return _df_cache

def _rows_dict(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    # Only return primitive-serializable dtypes
    return df.fillna("").to_dict(orient="records")

@router.get("/_debug")
def debug_status() -> Dict[str, Any]:
    df = _load_df(force=False)
    exists = CSV_PATH.exists()
    return {
        "exists": exists,
        "path": str(CSV_PATH),
        "rows": 0 if df is None else int(len(df)),
        "cols": [] if df is None or df.empty else list(df.columns),
        "ready": exists and df is not None and not df.empty,
        "loaded_at": _last_loaded,
    }

@router.post("/_refresh")
def force_refresh() -> Dict[str, Any]:
    df = _load_df(force=True)
    return {
        "ok": True,
        "path": str(CSV_PATH),
        "rows": int(len(df)),
        "cols": list(df.columns),
    }

@router.get("")
def list_instruments(offset: int = 0, limit: int = 200) -> Dict[str, Any]:
    df = _load_df()
    if df.empty:
        return {"data": []}
    end = max(0, min(len(df), offset + limit))
    start = max(0, min(offset, end))
    return {"data": _rows_dict(df.iloc[start:end])}

@router.get("/indices")
def list_indices(q: Optional[str] = Query(None)) -> Dict[str, Any]:
    df = _load_df()
    if df.empty:
        return {"data": []}
    mask = pd.Series([False] * len(df))
    if "instrument_type" in df.columns:
        mask = mask | (df["instrument_type"].astype(str).str.upper() == "INDEX")
    if "segment" in df.columns:
        mask = mask | (df["segment"].astype(str).str.upper() == "I")
    f = df[mask]
    if q:
        ql = str(q).lower()
        cols = [c for c in ("symbol_name","underlying_symbol") if c in f.columns]
        if cols:
            cond = False
            for c in cols:
                cond = (f[c].astype(str).str.lower().str.contains(ql)) | cond
            f = f[cond]
    return {"data": _rows_dict(f)}

@router.get("/search")
def search(q: str, limit: int = 50) -> Dict[str, Any]:
    df = _load_df()
    if df.empty:
        return {"data": []}
    ql = q.lower()
    cols = [c for c in ("security_id","symbol_name","underlying_symbol","instrument_type","segment") if c in df.columns]
    if not cols:
        return {"data": []}
    cond = False
    for c in cols:
        cond = cond | df[c].astype(str).str.lower().str.contains(ql)
    out = df[cond].head(limit)
    return {"data": _rows_dict(out)}

@router.get("/by-id")
def by_id(security_id: str) -> Dict[str, Any]:
    df = _load_df()
    if df.empty or "security_id" not in df.columns:
        raise HTTPException(status_code=404, detail="Not Found")
    row = df[df["security_id"].astype(str) == str(security_id)]
    if row.empty:
        raise HTTPException(status_code=404, detail="Not Found")
    return _rows_dict(row.head(1))[0]
