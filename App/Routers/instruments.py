# App/Routers/instruments.py
from __future__ import annotations

from fastapi import APIRouter, Query, HTTPException
from pathlib import Path
import pandas as pd
from typing import Dict, List, Any, Optional

router = APIRouter(prefix="/instruments", tags=["Instruments"])

# --- Paths (robust) ----------------------------------------------------------
# Render par working dir /opt/render/project/src hota hai.
# Is file ke relative 2 levels upar project root maan ke data/ pakdenge.
BASE_DIR = Path(__file__).resolve().parents[2]   # project root
DATA_DIR = BASE_DIR / "data"
CSV_FILE = DATA_DIR / "instruments.csv"          # <--- yahi file padhenge

# --- In-memory cache ---------------------------------------------------------
_cache: Dict[str, Any] = {"rows": None, "cols": None, "count": 0}


# --- Utilities ---------------------------------------------------------------
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _load_csv(force: bool = False) -> pd.DataFrame:
    """CSV ko memory me laao; columns normalize karo; ‘index’ rows bhi contain rahein."""
    if _cache["rows"] is not None and not force:
        return _cache["rows"]

    if not CSV_FILE.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_FILE}")

    # Dhan dump me commas/quotes ho sakte hain – default engine ok; errors='ignore'
    df = pd.read_csv(CSV_FILE, dtype=str, low_memory=False)
    df = _normalize_columns(df)

    _cache["rows"] = df
    _cache["cols"] = list(df.columns)
    _cache["count"] = len(df)
    return df


def _like(df: pd.DataFrame, col: str, text: str) -> pd.Series:
    col = col.lower()
    if col not in df.columns:
        # missing columns ko safely handle karein
        return pd.Series([False] * len(df))
    return df[col].fillna("").str.contains(text, case=False, na=False)


# --- Debug / Maintenance -----------------------------------------------------
@router.get("/_debug")
def debug() -> Dict[str, Any]:
    """File, path, rows/cols aur head sample dikhao."""
    info: Dict[str, Any] = {
        "csv_abspath": str(CSV_FILE),
        "csv_exists": CSV_FILE.exists(),
        "cached": _cache["rows"] is not None,
    }
    try:
        df = _load_csv(force=False)
        head_sample = df.head(3).to_dict(orient="records")
        info.update({
            "count": len(df),
            "cols": _cache["cols"],
            "head": head_sample,
        })
    except Exception as e:
        info.update({"error": str(e)})
    return info


@router.post("/_refresh")
def refresh() -> Dict[str, Any]:
    """Cache clear + reload CSV."""
    _cache["rows"] = None
    _cache["cols"] = None
    _cache["count"] = 0
    df = _load_csv(force=True)
    return {"ok": True, "count": len(df)}


# --- Public APIs -------------------------------------------------------------
@router.get("")
def list_all(limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    df = _load_csv()
    data = df.head(limit).to_dict(orient="records")
    return {"count": len(data), "data": data}


@router.get("/indices")
def list_indices(q: Optional[str] = None, limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    df = _load_csv()

    # Dhan dump me index rows identify karne ke liye typical hints:
    # instrument_type == 'INDEX'  ya series == 'INDEX'  ya name me 'NIFTY', 'SENSEX', etc.
    mask = pd.Series([False] * len(df))
    for col in ["instrument_type", "series"]:
        if col in df.columns:
            mask = mask | (df[col].str.upper().fillna("") == "INDEX")

    # Fallback: name/symbol me well-known tokens
    fallback = pd.Series([False] * len(df))
    for col in ["name", "symbol", "trading_symbol", "description"]:
        if col in df.columns:
            fallback = fallback | df[col].str.contains(
                r"(NIFTY|BANKNIFTY|FINNIFTY|MIDCPNIFTY|SENSEX|BANKEX|NSE|BSE)",
                case=False, na=False
            )

    mask = mask | fallback
    df_idx = df[mask].copy()

    if q:
        # free text – common columns par search
        text = q.strip()
        any_match = (
            _like(df_idx, "name", text) |
            _like(df_idx, "symbol", text) |
            _like(df_idx, "trading_symbol", text) |
            _like(df_idx, "description", text)
        )
        df_idx = df_idx[any_match]

    data = df_idx.head(limit).to_dict(orient="records")
    return {"count": len(data), "data": data}


@router.get("/search")
def generic_search(q: str, limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    df = _load_csv()
    q = q.strip()
    # Multi-column OR search
    cols = [c for c in ["symbol", "name", "trading_symbol", "description", "instrument_type", "series"] if c in df.columns]
    if not cols:
        return {"count": 0, "data": []}

    mask = pd.Series([False] * len(df))
    for c in cols:
        mask = mask | df[c].fillna("").str.contains(q, case=False, na=False)
    res = df[mask].head(limit).to_dict(orient="records")
    return {"count": len(res), "data": res}


@router.get("/by-id")
def by_id(security_id: str) -> Dict[str, Any]:
    df = _load_csv()
    # Security id column names jo commonly aate hain
    candidates = ["security_id", "securityid", "sec_id", "instrument_token", "token"]
    col = next((c for c in candidates if c in df.columns), None)
    if not col:
        raise HTTPException(status_code=404, detail="security_id column not present in CSV")

    row = df[df[col] == str(security_id)]
    if row.empty:
        raise HTTPException(status_code=404, detail="Not Found")
    return row.head(1).to_dict(orient="records")[0]
