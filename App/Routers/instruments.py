# App/Services/dhan_client.py
from __future__ import annotations

import os
import io
import time
import csv
import threading
from typing import List, Dict, Iterable, Optional
import requests

# ---------------------------
# CONFIG
# ---------------------------
# If you already keep a local cached CSV, set its path here
LOCAL_CSV = os.getenv("DHAN_LOCAL_CSV", "data/instruments_dhan.csv")

# If you want to fetch directly from a URL, provide it via env:
# e.g. DHAN_INSTRUMENTS_URL=https://images.dhan.co/api-data/api-scrip-master.csv
REMOTE_CSV_URL = os.getenv("DHAN_INSTRUMENTS_URL")

# cache TTL seconds
CACHE_TTL = int(os.getenv("INSTRUMENTS_CACHE_TTL", "3600"))

# ---------------------------
# INTERNAL CACHE
# ---------------------------
_cache_lock = threading.Lock()
_cache_loaded_at: float = 0.0
_cache_rows: List[Dict[str, str]] = []

# ---------------------------
# HELPERS
# ---------------------------
def _load_from_local(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]

def _load_from_remote(url: str) -> List[Dict[str, str]]:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    content = r.content
    # Dhan scrip master is CSV with header
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    return [row for row in reader]

def _ensure_cache() -> None:
    global _cache_rows, _cache_loaded_at
    with _cache_lock:
        now = time.time()
        if _cache_rows and (now - _cache_loaded_at) < CACHE_TTL:
            return  # still fresh

        rows: List[Dict[str, str]] = []
        # prefer remote if provided; else local file
        if REMOTE_CSV_URL:
            try:
                rows = _load_from_remote(REMOTE_CSV_URL)
            except Exception:
                # fallback to local if available
                rows = _load_from_local(LOCAL_CSV)
        else:
            rows = _load_from_local(LOCAL_CSV)

        _cache_rows = rows or []
        _cache_loaded_at = now

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().upper()

# ---------------------------
# PUBLIC API (used by routers)
# ---------------------------
def get_instruments_csv(segment: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Return full Dhan instruments list (optionally filtered by segment).
    Segment examples (as per Dhan CSV header fields): 'NSE', 'BSE', 'FNO'
    """
    _ensure_cache()
    rows = list(_cache_rows)
    if segment:
        seg = _norm(segment)
        # common column names in Dhan scrip master:
        # 'EXCHANGE' or 'ExchangeSegment' depending on version
        def match(row: Dict[str, str]) -> bool:
            return _norm(row.get("EXCHANGE") or row.get("ExchangeSegment")) == seg
        rows = [r for r in rows if match(r)]
    return rows

def get_instruments() -> List[Dict[str, str]]:
    """Backward-compatible name, returns all rows."""
    return get_instruments_csv()

def get_instruments_by_segment(segment: str) -> List[Dict[str, str]]:
    """
    Adapter kept for routers that import this older name.
    Simply calls get_instruments_csv(segment).
    """
    return get_instruments_csv(segment)

def search_instruments(q: str, segment: Optional[str] = None, limit: int = 50) -> List[Dict[str, str]]:
    """
    Case-insensitive search on SYMBOL / DESCRIPTION fields within optional segment.
    """
    qn = _norm(q)
    if not qn:
        return []

    rows = get_instruments_csv(segment)
    def hit(row: Dict[str, str]) -> bool:
        sym = _norm(row.get("SYMBOL") or row.get("Symbol") or row.get("TRADING_SYMBOL"))
        name = _norm(row.get("NAME") or row.get("SecurityName") or row.get("Description"))
        return (qn in sym) or (qn in name)

    out: List[Dict[str, str]] = []
    for r in rows:
        if hit(r):
            out.append(r)
            if len(out) >= limit:
                break
    return out
