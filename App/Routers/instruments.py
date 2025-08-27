# App/Routers/instruments.py
from pathlib import Path
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/instruments", tags=["instruments"])

BASE_DIR  = Path(__file__).resolve().parent.parent.parent  # repo root
LOCAL_CSV = BASE_DIR / "data" / "instruments.csv"
TMP_CSV   = Path("/tmp/instruments.csv")

_df_cache: Optional[pd.DataFrame] = None

def _load_df(force: bool = False) -> pd.DataFrame:
    global _df_cache
    if _df_cache is not None and not force:
        return _df_cache

    csv_path = LOCAL_CSV if LOCAL_CSV.exists() else TMP_CSV
    if not csv_path.exists():
        raise HTTPException(status_code=500, detail=f"CSV not found at {csv_path}")

    df = pd.read_csv(csv_path, dtype=str).fillna("")
    _df_cache = df
    return df

@router.get("/_debug")
def instruments_debug():
    p = LOCAL_CSV if LOCAL_CSV.exists() else TMP_CSV
    exists = p.exists()
    rows = 0
    cols = []
    if exists:
        try:
            df = _load_df(force=True)
            rows = int(df.shape[0])
            cols = list(df.columns)
        except Exception:  # keep debug endpoint resilient
            pass
    return {"exists": exists, "path": str(p), "rows": rows, "cols": cols, "ready": bool(rows)}

def _rows_dict(df: pd.DataFrame) -> list[dict]:
    return df.to_dict(orient="records")

@router.get("")
def list_instruments(limit: int = 100):
    df = _load_df()
    return {"data": _rows_dict(df.head(limit))}

@router.get("/indices")
def list_indices(q: Optional[str] = None, limit: int = 100):
    df = _load_df()
    mask = (df["instrument_type"] == "INDEX")
    if q:
        ql = q.lower()
        mask &= df["symbol_name"].str.lower().str.contains(ql)
    out = df.loc[mask].head(limit)
    return {"data": _rows_dict(out)}

@router.get("/search")
def search_instruments(q: str, limit: int = 50):
    df = _load_df()
    ql = q.lower()
    mask = (
        df["symbol_name"].str.lower().str.contains(ql) |
        df["underlying_symbol"].str.lower().str.contains(ql)
    )
    out = df.loc[mask].head(limit)
    return {"data": _rows_dict(out)}

@router.get("/by-id")
def by_id(security_id: str):
    df = _load_df()
    row = df.loc[df["security_id"] == str(security_id)]
    if row.empty:
        raise HTTPException(status_code=404, detail="Not Found")
    return _rows_dict(row.head(1))[0]
