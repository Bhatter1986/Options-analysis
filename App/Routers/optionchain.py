# App/Routers/optionchain.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np
import time
from datetime import datetime

router = APIRouter(prefix="/optionchain", tags=["optionchain"])

CSV_PATH = Path("data/option_chain.csv")

_df_cache: Optional[pd.DataFrame] = None
_loaded_at: Optional[float] = None

# ----- helpers --------------------------------------------------------------

def _exists() -> bool:
    return CSV_PATH.exists() and CSV_PATH.is_file()

def _norm_expiry(v: str) -> str:
    """
    Convert many common date strings to YYYY-MM-DD.
    Supports: 2025-09-04, 04-09-2025, 04/09/2025, 4 Sep 2025, 04SEP2025, etc.
    """
    if v is None:
        return ""
    s = str(v).strip().upper().replace(".", " ").replace("_", " ")
    # fast paths
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    # 04SEP2025 / 4SEP2025
    try:
        return datetime.strptime(s, "%d%b%Y").strftime("%Y-%m-%d")
    except Exception:
        pass
    # 4 Sep 2025
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    # last resort: pandas parser
    try:
        return pd.to_datetime(s, dayfirst=True, errors="coerce").strftime("%Y-%m-%d")
    except Exception:
        return ""

def _load_df(force: bool = False) -> pd.DataFrame:
    global _df_cache, _loaded_at
    if not force and _df_cache is not None:
        return _df_cache
    if not _exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    # read all as string; avoid NA magic
    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False, na_filter=False)

    # find required columns with flexible names
    # required minimal: symbol, expiry, strike, option_type (CE/PE) + last_price/oi/iv (optional)
    colmap = {c.lower().strip(): c for c in df.columns}

    def pick(*cands: str) -> str:
        for c in cands:
            if c.lower() in colmap:
                return colmap[c.lower()]
        raise ValueError(f"Missing column (tried): {cands}")

    col_symbol = pick("symbol", "underlying", "underlying_symbol")
    col_expiry = pick("expiry", "expiry_date", "exp_date", "expiration")
    col_strike = pick("strike", "strike_price")
    col_type   = pick("option_type", "type", "cepe", "right")

    # optional numeric fields
    opt_cols = {
        "last_price": colmap.get("last_price") or colmap.get("ltp") or colmap.get("price"),
        "oi": colmap.get("oi") or colmap.get("open_interest"),
        "previous_oi": colmap.get("previous_oi") or colmap.get("prev_oi"),
        "volume": colmap.get("volume") or colmap.get("qty"),
        "implied_volatility": colmap.get("implied_volatility") or colmap.get("iv"),
        "change": colmap.get("change") or colmap.get("chg") or colmap.get("%change"),
    }

    # normalize
    out = pd.DataFrame({
        "symbol": df[col_symbol].astype(str).str.strip(),
        "expiry": df[col_expiry].astype(str).map(_norm_expiry),
        "strike": df[col_strike].astype(str).str.replace(",", "").str.strip(),
        "option_type": df[col_type].astype(str).str.strip().str.upper().replace({"CALL":"CE","PUT":"PE"}),
    })

    # ensure numeric strike
    with np.errstate(all="ignore"):
        out["strike"] = pd.to_numeric(out["strike"], errors="coerce")

    # attach optional numeric columns if present
    for k, src in opt_cols.items():
        if src:
            out[k] = pd.to_numeric(
                pd.to_numeric(pd.Series(df[src]).astype(str).str.replace(",", ""), errors="coerce"),
                errors="coerce"
            )

    # drop rows with no expiry/strike/type
    out = out[(out["expiry"] != "") & out["strike"].notna() & out["option_type"].isin(["CE", "PE"])]

    _df_cache = out.reset_index(drop=True)
    _loaded_at = time.time()
    return _df_cache

def _rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
    return df.to_dict(orient="records")

# ----- endpoints ------------------------------------------------------------

@router.get("/_debug")
def debug() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "exists": _exists(),
        "path": str(CSV_PATH),
        "rows": 0,
        "ready": False,
    }
    if not info["exists"]:
        return info
    try:
        df = _load_df(force=True)
        info["rows"] = int(df.shape[0])
        info["ready"] = info["rows"] > 0
        info["loaded_at"] = _loaded_at
        # first few expiries sample
        info["sample_expiries"] = sorted(df["expiry"].dropna().unique().tolist())[:6]
    except Exception as e:
        info["error"] = str(e)
    return info

@router.post("/_refresh")
def refresh() -> Dict[str, Any]:
    global _df_cache
    _df_cache = None
    try:
        df = _load_df(force=True)
        return {"ok": True, "rows": int(df.shape[0]), "path": str(CSV_PATH)}
    except Exception as e:
        return {"ok": False, "detail": str(e), "path": str(CSV_PATH)}

@router.get("/expiries")
def expiries(symbol: Optional[str] = Query(None)) -> Dict[str, Any]:
    try:
        df = _load_df()
    except Exception as e:
        raise HTTPException(500, f"load failed: {e}")
    if symbol:
        df = df[df["symbol"].str.upper() == str(symbol).strip().upper()]
    exps = sorted(df["expiry"].dropna().unique().tolist())
    return {"data": exps}

@router.get("/by-expiry")
def by_expiry(
    expiry: str = Query(..., description="YYYY-MM-DD (any CSV format will auto-normalize)"),
    symbol: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
) -> Dict[str, Any]:
    try:
        df = _load_df()
    except Exception as e:
        raise HTTPException(500, f"load failed: {e}")

    e_norm = _norm_expiry(expiry)
    if not e_norm:
        raise HTTPException(400, "Invalid expiry")

    q = df[df["expiry"] == e_norm]
    if symbol:
        q = q[q["symbol"].str.upper() == str(symbol).strip().upper()]

    return {"data": _rows(q.head(limit)), "expiry": e_norm, "count": int(q.shape[0])}

@router.get("")
def list_all(
    symbol: Optional[str] = Query(None),
    expiry: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
) -> Dict[str, Any]:
    try:
        df = _load_df()
    except Exception as e:
        raise HTTPException(500, f"load failed: {e}")

    if symbol:
        df = df[df["symbol"].str.upper() == str(symbol).strip().upper()]
    if expiry:
        e = _norm_expiry(expiry)
        if not e:
            raise HTTPException(400, "Invalid expiry")
        df = df[df["expiry"] == e]

    return {"data": _rows(df.head(limit))}
