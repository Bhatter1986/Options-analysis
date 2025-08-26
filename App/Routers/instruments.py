# App/Routers/instruments.py
from __future__ import annotations

import io
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/instruments", tags=["instruments"])

# ---------- Config ----------
DATA_DIR = Path("data")
INDICES_CSV = DATA_DIR / "indices.csv"          # preferred (fast)
MASTER_CSV  = DATA_DIR / "instruments.csv"      # fallback (big)
CACHE_TTL_SECONDS = 300                         # soft TTL; manual refresh available

# Runtime cache
_cache: Dict[str, object] = {
    "df_all": None,           # pandas.DataFrame (full master if needed)
    "df_indices": None,       # pandas.DataFrame (only indices)
    "last_load": 0.0,
    "source": "",             # "indices.csv" | "instruments.csv"
}

# Column names vary between DhanHQ dumps. We’ll normalize into these:
#   name, security_id, instrument_type, exchange_segment, trading_symbol, series, description
COLUMN_ALIASES = {
    "name": {"NAME", "SYMBOL", "TRADING_SYMBOL", "TRADINGSYMBOL", "DISPLAY_NAME"},
    "security_id": {"SECURITY_ID", "SECURITYID", "SEC_ID", "ID"},
    "instrument_type": {"INSTRUMENT_TYPE", "INSTRUMENT", "TYPE"},
    "exchange_segment": {"EXCHANGE_SEGMENT", "SEGMENT", "EXCHANGESEGMENT"},
    "trading_symbol": {"TRADING_SYMBOL", "TRADINGSYMBOL", "SYMBOL"},
    "series": {"SERIES"},
    "description": {"DESCRIPTION", "DESC"},
}

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map any known alias to a stable set; keep original too (we only *add* normalized)."""
    cols_upper = {c.upper(): c for c in df.columns}
    def pick(keys: set[str]) -> Optional[str]:
        for k in keys:
            if k in cols_upper:
                return cols_upper[k]
        return None

    mapping = {}
    for target, aliases in COLUMN_ALIASES.items():
        src = pick(aliases)
        if src:
            mapping[target] = src

    # Create normalized columns if present
    for target, src in mapping.items():
        df[target] = df[src].astype(str)
    # Some CSVs don’t have NAME but have TRADING_SYMBOL; ensure name filled
    if "name" not in df.columns and "trading_symbol" in df.columns:
        df["name"] = df["trading_symbol"]
    # Ensure security_id numeric-like as string (no .0)
    if "security_id" in df.columns:
        df["security_id"] = (
            df["security_id"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )
    return df


def _load_indices_df(force: bool = False) -> pd.DataFrame:
    """Load indices into memory, preferring indices.csv; otherwise filter master."""
    now = time.time()
    if (
        not force
        and _cache["df_indices"] is not None
        and (now - float(_cache["last_load"])) < CACHE_TTL_SECONDS
    ):
        return _cache["df_indices"]  # type: ignore

    if INDICES_CSV.exists():
        df = pd.read_csv(INDICES_CSV)
        df = _normalize_columns(df)
        # Keep only instrument_type == INDEX when column exists
        if "instrument_type" in df.columns:
            df = df[df["instrument_type"].str.upper() == "INDEX"]
        source = "indices.csv"
    elif MASTER_CSV.exists():
        dfm = pd.read_csv(MASTER_CSV)
        dfm = _normalize_columns(dfm)
        if "instrument_type" in dfm.columns:
            df = dfm[dfm["instrument_type"].str.upper() == "INDEX"].copy()
        else:
            # Last-resort heuristic: many dumps have 'INDEX' word in DESCRIPTION/NAME
            mask = False
            for col in ("description", "name"):
                if col in dfm.columns:
                    mask = mask | dfm[col].str.upper().str.contains("INDEX", na=False)
            df = dfm[mask].copy()
        source = "instruments.csv"
    else:
        raise HTTPException(status_code=404, detail="No instruments CSV found in /data")

    # Minimal shape for API responses
    preferred_cols = [
        c for c in ["security_id", "name", "trading_symbol", "exchange_segment", "instrument_type", "series", "description"]
        if c in df.columns
    ]
    if "security_id" not in preferred_cols or "name" not in preferred_cols:
        # Guarantee keys for client
        df["security_id"] = df.get("security_id", pd.Series([], dtype=str))
        df["name"] = df.get("name", df.get("trading_symbol", pd.Series([], dtype=str)))

    df = df[preferred_cols].drop_duplicates().reset_index(drop=True)

    _cache["df_indices"] = df
    _cache["last_load"] = now
    _cache["source"] = source
    return df


def _load_master_df(force: bool = False) -> pd.DataFrame:
    now = time.time()
    if (
        not force
        and _cache["df_all"] is not None
        and (now - float(_cache["last_load"])) < CACHE_TTL_SECONDS
    ):
        return _cache["df_all"]  # type: ignore

    if MASTER_CSV.exists():
        df = pd.read_csv(MASTER_CSV)
        df = _normalize_columns(df)
        _cache["df_all"] = df
        _cache["last_load"] = now
        _cache["source"] = "instruments.csv"
        return df
    else:
        # Fall back to indices only if master missing
        return _load_indices_df(force=force)


# -------------------- Routes --------------------

@router.get("/indices")
def list_indices(
    q: Optional[str] = Query(None, description="search by name / trading_symbol (case-insensitive)"),
    exchange_segment: Optional[str] = Query(None, description="e.g. NSE_I, IDX_I, BSE_I"),
    limit: int = Query(50, ge=1, le=500),
):
    """
    Return index instruments from local CSV (fast). Example:

        /instruments/indices?q=nifty&limit=5
    """
    df = _load_indices_df()
    if q:
        s = q.strip().upper()
        mask = False
        for col in [c for c in ["name", "trading_symbol", "description"] if c in df.columns]:
            mask = mask | df[col].str.upper().str.contains(s, na=False)
        df = df[mask]

    if exchange_segment and "exchange_segment" in df.columns:
        df = df[df["exchange_segment"].str.upper() == exchange_segment.strip().upper()]

    out = df.head(limit).to_dict(orient="records")
    return {"count": len(out), "data": out, "source": _cache.get("source", "")}


@router.get("/search")
def generic_search(
    q: str = Query(..., min_length=1, description="search across all instruments"),
    exchange_segment: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    only_indices: bool = Query(False, description="limit search to indices only"),
):
    """
    Generic search across the master CSV (or indices if only_indices=true).
    """
    df = _load_indices_df() if only_indices else _load_master_df()
    s = q.strip().upper()
    mask = False
    for col in [c for c in ["name", "trading_symbol", "description"] if c in df.columns]:
        mask = mask | df[col].str.upper().str.contains(s, na=False)
    df = df[mask]

    if exchange_segment and "exchange_segment" in df.columns:
        df = df[df["exchange_segment"].str.upper() == exchange_segment.strip().upper()]

    out = df.head(limit).to_dict(orient="records")
    return {"count": len(out), "data": out, "source": _cache.get("source", "")}


@router.get("/by-id")
def by_id(security_id: str = Query(..., description="Dhan security_id as string")):
    """
    Lookup a single instrument by security_id (tries indices first, then master).
    """
    sid = str(security_id).strip()
    for loader in (_load_indices_df, _load_master_df):
        df = loader()
        if "security_id" in df.columns:
            row = df[df["security_id"] == sid]
            if not row.empty:
                return {"data": row.iloc[0].to_dict(), "source": _cache.get("source", "")}
    raise HTTPException(status_code=404, detail="Not Found")


@router.post("/_refresh")
def refresh_cache():
    """
    Manually reload CSVs and rebuild cache.
    """
    # Clear
    _cache["df_indices"] = None
    _cache["df_all"] = None
    _cache["last_load"] = 0.0
    # Reload
    di = _load_indices_df(force=True)
    # master is optional
    try:
        dm = _load_master_df(force=True)
        master_loaded = True
    except HTTPException:
        master_loaded = False
        dm = pd.DataFrame()
    return {
        "ok": True,
        "indices_rows": int(len(di)),
        "master_rows": int(len(dm)) if master_loaded else 0,
        "source": _cache.get("source", ""),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
