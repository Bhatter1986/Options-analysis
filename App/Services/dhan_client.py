# App/Services/dhan_client.py
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List, Dict, Optional

# Optional pandas cache for speed; fallback to csv if pandas not installed
try:
    import pandas as pd  # type: ignore
    _HAS_PD = True
except Exception:
    import csv
    _HAS_PD = False

# --- Config: CSV location
# Prefer env override; else default "data/instruments.csv"
INSTRUMENTS_CSV = os.getenv("INSTRUMENTS_CSV", "data/instruments.csv")

# --- Simple hot-reload cache
_df_cache = None
_df_mtime: Optional[float] = None

def _load_df():
    """Load instruments CSV with hot-reload on mtime change."""
    global _df_cache, _df_mtime
    p = Path(INSTRUMENTS_CSV)
    if not p.exists():
        # try repo-relative fallbacks
        for guess in [Path("App/Data/instruments.csv"), Path("App/data/instruments.csv"), Path("instruments.csv")]:
            if guess.exists():
                p = guess
                break
    if not p.exists():
        raise FileNotFoundError(f"Instruments CSV not found at {INSTRUMENTS_CSV}")

    mtime = p.stat().st_mtime
    if _df_cache is not None and _df_mtime == mtime:
        return _df_cache

    if _HAS_PD:
        df = pd.read_csv(p)
        # normalize common column names
        cols = {c.lower(): c for c in df.columns}
        # Ensure expected logical names
        df.rename(columns={
            cols.get("segment", "segment"): "segment",
            cols.get("tradingsymbol", "tradingsymbol"): "tradingsymbol",
            cols.get("symbol", "symbol"): "symbol",
            cols.get("name", "name"): "name",
            cols.get("token", "token"): "token",
            cols.get("exchange", "exchange"): "exchange",
        }, inplace=True)
        _df_cache = df
    else:
        # csv fallback to list[dict]
        with p.open("r", newline="", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        _df_cache = reader  # list of dicts
    _df_mtime = mtime
    return _df_cache

# --- Public helpers used by routers

def get_instruments_csv(limit: int = 1000) -> List[Dict]:
    """Return first N instruments as list of dicts (for quick view)."""
    df = _load_df()
    if _HAS_PD:
        return df.head(limit).to_dict(orient="records")
    return df[:limit]

def get_instruments_by_segment(segment: str, limit: int = 5000) -> List[Dict]:
    """Filter by segment (e.g. 'NSE_EQ', 'NSE_FNO', 'BSE_EQ')."""
    seg = (segment or "").strip().upper()
    df = _load_df()
    if _HAS_PD:
        if "segment" not in df.columns:
            raise ValueError("CSV missing 'segment' column")
        out = df[df["segment"].astype(str).str.upper() == seg]
        return out.head(limit).to_dict(orient="records")
    # csv fallback
    out = [r for r in df if str(r.get("segment", "")).upper() == seg]
    return out[:limit]

def search_instruments(q: str, limit: int = 50) -> List[Dict]:
    """Case-insensitive search across tradingsymbol / name / symbol."""
    query = (q or "").strip().lower()
    if not query:
        return []
    df = _load_df()
    if _HAS_PD:
        def _has(s):
            s = s.fillna("").astype(str).str.lower()
            return s.str.contains(query, na=False)
        cols = {c.lower(): c for c in df.columns}
        mask = False
        for key in ["tradingsymbol", "symbol", "name"]:
            col = cols.get(key)
            if col:
                mask = _has(df[col]) | mask
        out = df[mask]
        return out.head(limit).to_dict(orient="records")
    # csv fallback
    results = []
    for r in df:
        ts = str(r.get("tradingsymbol", "")).lower()
        sy = str(r.get("symbol", "")).lower()
        nm = str(r.get("name", "")).lower()
        if query in ts or query in sy or query in nm:
            results.append(r)
            if len(results) >= limit:
                break
    return results
