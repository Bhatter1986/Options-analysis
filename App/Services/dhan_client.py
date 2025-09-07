# App/Services/dhan_client.py
from __future__ import annotations

import io
import os
import time
import csv
import requests
from typing import Dict, Any, List, Optional

# --- Dhan CSV endpoints (official)
DHAN_CSV_COMPACT = "https://images.dhan.co/api-data/api-scrip-master.csv"
DHAN_CSV_DETAILED = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

# --- Simple in-process cache
_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = int(os.getenv("INSTRUMENTS_CACHE_TTL", "3600"))  # seconds (default 1h)

def _cache_get(key: str) -> Optional[Any]:
    item = _CACHE.get(key)
    if not item:
        return None
    if (time.time() - item["ts"]) > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return item["value"]

def _cache_set(key: str, value: Any) -> None:
    _CACHE[key] = {"ts": time.time(), "value": value}

def _fetch_csv(url: str) -> List[Dict[str, Any]]:
    """Download CSV text and return list of dict rows."""
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    text = r.text
    f = io.StringIO(text)
    reader = csv.DictReader(f)
    rows = [dict(row) for row in reader]
    return rows

def get_instruments_csv(detailed: bool = True, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Load instruments from Dhan CSV (detailed by default).
    Caches for _CACHE_TTL seconds.
    """
    key = f"instruments:{'detailed' if detailed else 'compact'}"
    if not force_refresh:
        cached = _cache_get(key)
        if cached is not None:
            return cached

    url = DHAN_CSV_DETAILED if detailed else DHAN_CSV_COMPACT
    rows = _fetch_csv(url)
    _cache_set(key, rows)
    return rows

def search_instruments(
    query: str,
    limit: int = 50,
    detailed: bool = True,
    fields_priority: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Case-insensitive contains search over a few useful columns.
    Default priority: DISPLAY_NAME, SEM_TRADING_SYMBOL, SYMBOL_NAME, UNDERLYING_SYMBOL
    """
    rows = get_instruments_csv(detailed=detailed)
    q = (query or "").strip().lower()
    if not q:
        return rows[:limit]

    # sensible defaults for detailed CSV column names
    fields_priority = fields_priority or [
        "DISPLAY_NAME",
        "SEM_TRADING_SYMBOL",
        "SYMBOL_NAME",
        "UNDERLYING_SYMBOL",
        "INSTRUMENT",
        "EXCH_ID",
        "SEGMENT",
        "SERIES",
    ]

    scored: List[tuple[int, Dict[str, Any]]] = []
    for r in rows:
        score = 0
        for i, col in enumerate(fields_priority):
            val = str(r.get(col, "")).lower()
            if q in val:
                # higher weight for earlier columns
                score += (len(fields_priority) - i) * 10
        if score > 0:
            scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:limit]]
