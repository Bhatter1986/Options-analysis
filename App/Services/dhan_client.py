# App/Services/dhan_client.py
from __future__ import annotations

import csv
import io
import time
from typing import List, Dict, Any, Optional
import requests

DHAN_CSV_COMPACT = "https://images.dhan.co/api-data/api-scrip-master.csv"
DHAN_CSV_DETAILED = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

# Simple in-memory cache
_cache: Dict[str, Any] = {
    "detailed": None,     # List[Dict[str, Any]]
    "compact": None,      # List[Dict[str, Any]]
    "ts_detailed": 0.0,
    "ts_compact": 0.0,
}
# CSV ko baar-baar download na karne ke liye TTL
CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours


def _download_csv(url: str) -> List[Dict[str, Any]]:
    """Download CSV and return list of dict rows."""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    content = resp.content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    rows: List[Dict[str, Any]] = []
    for row in reader:
        # normalize keys: strip spaces
        normalized = { (k or "").strip(): (v or "").strip() for k, v in row.items() }
        rows.append(normalized)
    return rows


def get_instruments_csv(detailed: bool = True, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Fetch instruments from Dhan CSV (detailed by default).
    Caches in memory for CACHE_TTL_SECONDS.
    """
    now = time.time()
    key = "detailed" if detailed else "compact"
    ts_key = "ts_detailed" if detailed else "ts_compact"

    if (not force_refresh) and _cache[key] is not None and (now - _cache[ts_key] < CACHE_TTL_SECONDS):
        return _cache[key]  # type: ignore[return-value]

    url = DHAN_CSV_DETAILED if detailed else DHAN_CSV_COMPACT
    data = _download_csv(url)
    _cache[key] = data
    _cache[ts_key] = now
    return data


def search_instruments(
    query: str,
    detailed: bool = True,
    limit: int = 50,
    fields: Optional[list[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Simple case-insensitive contains search across a few useful columns.
    Default columns: SYMBOL_NAME, SEM_TRADING_SYMBOL, DISPLAY_NAME (or compact equivalents).
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    rows = get_instruments_csv(detailed=detailed, force_refresh=False)

    # sensible default columns (handle both detailed & compact variants)
    candidate_fields = fields or [
        "SYMBOL_NAME", "SEM_TRADING_SYMBOL", "DISPLAY_NAME",
        "SEM_SYMBOL_NAME", "SEM_CUSTOM_SYMBOL"  # sometimes present
    ]

    out: List[Dict[str, Any]] = []
    seen = 0
    for r in rows:
        for col in candidate_fields:
            val = r.get(col)
            if val and q in str(val).lower():
                out.append(r)
                seen += 1
                break
        if seen >= limit:
            break
    return out
