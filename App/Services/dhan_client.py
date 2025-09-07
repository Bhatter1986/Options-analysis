# App/Services/dhan_client.py
import os
import time
import csv
import io
import requests
from typing import List, Dict, Optional

INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-script-master-detailed.csv",
)
TTL = int(os.getenv("INSTRUMENTS_TTL_SEC", "86400"))

_cache_data: Optional[List[Dict[str, str]]] = None
_cache_at: float = 0.0

def _need_refresh() -> bool:
    if _cache_data is None:
        return True
    return (time.time() - _cache_at) > TTL

def get_instruments_csv() -> List[Dict[str, str]]:
    """Download + cache Dhan instruments CSV -> list of dicts."""
    global _cache_data, _cache_at
    if not _need_refresh():
        return _cache_data or []

    resp = requests.get(INSTRUMENTS_URL, timeout=60)
    resp.raise_for_status()
    text = resp.text
    f = io.StringIO(text)
    reader = csv.DictReader(f)
    rows: List[Dict[str, str]] = []
    for r in reader:
        # Normalize keys (strip spaces)
        norm = { (k or "").strip(): (v or "").strip() for k, v in r.items() }
        rows.append(norm)

    _cache_data = rows
    _cache_at = time.time()
    return rows

def get_instruments() -> List[Dict[str, str]]:
    """Return all instruments (cached)."""
    return get_instruments_csv()

def get_instruments_by_segment(exchange_segment: str) -> List[Dict[str, str]]:
    """
    Filter by exchange segment.
    Typical segments in CSV column may be like: 'NSE', 'NSE_FNO', 'BSE', etc.
    Adjust key name if your CSV uses a different header.
    """
    seg = (exchange_segment or "").strip().lower()
    data = get_instruments_csv()
    out: List[Dict[str, str]] = []
    # Try common header names
    cand_keys = ["exchange_segment", "Segment", "segment", "EXCHANGE_SEGMENT"]
    for row in data:
        # find first present key
        key = next((k for k in cand_keys if k in row), None)
        if not key:
            continue
        if (row.get(key, "").strip().lower() == seg):
            out.append(row)
    return out

def search_instruments(q: str) -> List[Dict[str, str]]:
    """
    Case-insensitive substring search on a few common columns:
    SYMBOL / TRADING_SYMBOL / SECURITY_ID / SECURITY_NAME
    """
    query = (q or "").strip().lower()
    if not query:
        return []
    data = get_instruments_csv()
    cols = ["SYMBOL", "TRADING_SYMBOL", "TRADING SYMBOL", "SECURITY_ID", "SECURITY NAME", "SECURITY_NAME", "NAME"]
    out: List[Dict[str, str]] = []
    for row in data:
        for c in cols:
            if c in row and query in (row[c] or "").lower():
                out.append(row)
                break
    return out
