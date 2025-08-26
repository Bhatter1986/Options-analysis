# App/Routers/instruments.py
from __future__ import annotations

from fastapi import APIRouter, Query
from pathlib import Path
import pandas as pd
from typing import Dict, List, Any

router = APIRouter(prefix="/instruments", tags=["Instruments"])

# ---- Paths & cache -----------------------------------------------------------
DATA_DIR = Path("data")
CSV_FILE = DATA_DIR / "indices.csv"          # <-- we’ll read this file
_cache: Dict[str, Any] = {"rows": None, "cols": None, "count": 0}


# ---- Utils -------------------------------------------------------------------
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names to lowercase snake-ish for resilient access.
    No assumptions about exact header names from DhanHQ dump.
    """
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _pick_first_col(df: pd.DataFrame, candidates: List[str]) -> str | None:
    """
    Return the first column present from the candidate list (case-insensitive).
    """
    cols = list(df.columns)
    for c in candidates:
        c_low = c.lower()
        if c_low in cols:
            return c_low
    return None


def _load_csv_into_cache() -> Dict[str, Any]:
    """
    Read CSV into memory, store normalized rows + a search blob for quick filtering.
    Cache structure:
      rows: list[dict]
      cols: list[str]
      count: int
    """
    if not CSV_FILE.exists():
        raise FileNotFoundError(f"CSV not found at {CSV_FILE}")

    # Read with pandas; tolerate big files
    df = pd.read_csv(CSV_FILE, dtype=str, low_memory=False)
    df = _normalize_columns(df).fillna("")

    # Optional “friendly” fields if present
    security_id_col = _pick_first_col(df, ["security_id", "sec_id", "securityid"])
    symbol_col      = _pick_first_col(df, ["trading_symbol", "symbol", "name", "instrument_name"])
    exch_seg_col    = _pick_first_col(df, ["exchange_segment", "exch_seg", "segment", "exchange"])

    # Prepare rows
    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        d = row.to_dict()

        # add normalized convenience keys if columns exist
        if security_id_col and "security_id" not in d:
            d["security_id"] = row[security_id_col]

        if symbol_col and "symbol" not in d:
            d["symbol"] = row[symbol_col]

        if exch_seg_col and "exchange_segment" not in d:
            d["exchange_segment"] = row[exch_seg_col]

        # pre-compute a search blob
        d["_blob"] = " ".join(str(v) for v in d.values()).lower()
        records.append(d)

    _cache["rows"] = records
    _cache["cols"] = list(df.columns)
    _cache["count"] = len(records)
    return _cache


def _ensure_cache() -> Dict[str, Any]:
    if _cache["rows"] is None:
        return _load_csv_into_cache()
    return _cache


# ---- Endpoints ---------------------------------------------------------------

@router.get("", summary="Info/health for instruments data")
def info() -> Dict[str, Any]:
    """
    Returns basic info about what is loaded. Useful for quick checks.
    """
    try:
        c = _ensure_cache()
        return {
            "ok": True,
            "count": c["count"],
            "columns": c["cols"],
            "csv_path": str(CSV_FILE),
            "loaded": c["rows"] is not None,
        }
    except FileNotFoundError as e:
        return {"ok": False, "detail": str(e)}


@router.post("/_refresh", summary="Reload CSV into memory")
def refresh() -> Dict[str, Any]:
    try:
        c = _load_csv_into_cache()
        return {"ok": True, "rows": c["count"]}
    except Exception as e:
        return {"ok": False, "detail": str(e)}


@router.get("/indices", summary="List indices with optional filters")
def list_indices(
    q: str | None = Query(None, description="Search string (matches any column)"),
    exchange_segment: str | None = Query(None, description="Optional exchange segment filter"),
    limit: int = Query(50, ge=1, le=500),
) -> Dict[str, Any]:
    """
    Returns index instruments from the local CSV.
    - q filters against a precomputed text blob of each row
    - exchange_segment (if present in CSV) narrows results
    """
    try:
        c = _ensure_cache()
    except FileNotFoundError:
        return {"count": 0, "data": []}

    rows = c["rows"]

    # Keep only rows that look like indices if we can infer it
    # Many Dhan master dumps have a column with 'index' in instrument_type/series/name.
    # We'll heuristically keep rows whose blob contains "index".
    index_only = [r for r in rows if "index" in r["_blob"]]

    if exchange_segment:
        es = exchange_segment.lower()
        index_only = [
            r
            for r in index_only
            if ("exchange_segment" in r and es in str(r["exchange_segment"]).lower())
            or (es in r["_blob"])
        ]

    if q:
        ql = q.lower()
        index_only = [r for r in index_only if ql in r["_blob"]]

    # Trim helper fields
    out = []
    for r in index_only[:limit]:
        d = {k: v for k, v in r.items() if k != "_blob"}
        out.append(d)

    return {"count": len(out), "data": out}


@router.get("/search", summary="Generic search across the CSV")
def generic_search(
    q: str = Query(..., description="Search string"),
    limit: int = Query(50, ge=1, le=500),
) -> Dict[str, Any]:
    try:
        c = _ensure_cache()
    except FileNotFoundError:
        return {"count": 0, "data": []}

    ql = q.lower()
    hits = [r for r in c["rows"] if ql in r["_blob"]]

    out = []
    for r in hits[:limit]:
        d = {k: v for k, v in r.items() if k != "_blob"}
        out.append(d)

    return {"count": len(out), "data": out}


@router.get("/by-id", summary="Lookup by security_id")
def by_id(security_id: str = Query(..., description="Security ID to match")) -> Dict[str, Any]:
    try:
        c = _ensure_cache()
    except FileNotFoundError:
        return {"detail": "Not Found"}

    sid = security_id.strip().lower()
    for r in c["rows"]:
        val = str(r.get("security_id", "")).lower()
        if val == sid:
            return {k: v for k, v in r.items() if k != "_blob"}

    return {"detail": "Not Found"}
