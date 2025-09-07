# App/Services/dhan_client.py

from __future__ import annotations

import os
import csv
import time
import io
import requests
from functools import lru_cache
from typing import Dict, List, Any, Optional, Iterable

# ------------------------------
# Config
# ------------------------------
DETAILED_CSV_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
COMPACT_CSV_URL  = "https://images.dhan.co/api-data/api-scrip-master.csv"
SEGMENT_CSV_URL  = "https://api.dhan.co/v2/instrument/{exchange_segment}"  # returns CSV
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")  # required for /v2/instrument/*
DEFAULT_TIMEOUT = 30

# ------------------------------
# Tiny TTL cache (in-memory)
# ------------------------------
class _TTLCache:
    def __init__(self, ttl_sec: int):
        self.ttl = ttl_sec
        self._store: Dict[str, Any] = {}
        self._ts: Dict[str, float] = {}

    def get(self, key: str):
        now = time.time()
        if key in self._store and now - self._ts.get(key, 0) < self.ttl:
            return self._store[key]
        return None

    def set(self, key: str, val: Any):
        self._store[key] = val
        self._ts[key] = time.time()

_inmem_cache = _TTLCache(ttl_sec=60 * 30)  # 30 min

# ------------------------------
# HTTP helpers
# ------------------------------
def _get(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
    h = {"Accept": "*/*"}
    if headers:
        h.update(headers)
    r = requests.get(url, headers=h, timeout=timeout)
    r.raise_for_status()
    return r

def _auth_headers() -> Dict[str, str]:
    if not DHAN_ACCESS_TOKEN:
        # Public CSVs work without token; but /v2/* needs token.
        return {}
    return {"Authorization": f"Bearer {DHAN_ACCESS_TOKEN}"}

def _parse_csv_bytes(b: bytes) -> List[Dict[str, str]]:
    text = b.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    return [row for row in reader]

# ------------------------------
# Public: Instruments (CSV – detailed)
# ------------------------------
def get_instruments_csv(force_refresh: bool = False) -> List[Dict[str, str]]:
    """
    Download Dhan detailed instrument CSV and cache it for 30 minutes.
    """
    cache_key = "instruments_detailed_csv"
    if not force_refresh:
        cached = _inmem_cache.get(cache_key)
        if cached is not None:
            return cached

    resp = _get(DETAILED_CSV_URL)
    rows = _parse_csv_bytes(resp.content)
    _inmem_cache.set(cache_key, rows)
    return rows

# ------------------------------
# Public: Segment-wise instruments (CSV from /v2/instrument/{segment})
# Example segments (see Annexure): NSE_DERIVATIVES -> "NSE_DERIVATIVES", etc.
# ------------------------------
def get_instruments_by_segment(exchange_segment: str, force_refresh: bool = False) -> List[Dict[str, str]]:
    """
    Fetch CSV for a specific exchange_segment (e.g. NSE_DERIVATIVES).
    Requires DHAN_ACCESS_TOKEN.
    """
    cache_key = f"segment_csv::{exchange_segment.upper()}"
    if not force_refresh:
        cached = _inmem_cache.get(cache_key)
        if cached is not None:
            return cached

    url = SEGMENT_CSV_URL.format(exchange_segment=exchange_segment)
    resp = _get(url, headers=_auth_headers())
    rows = _parse_csv_bytes(resp.content)
    _inmem_cache.set(cache_key, rows)
    return rows

# ------------------------------
# Public: Search instruments quickly (by SYMBOL / DISPLAY_NAME)
# ------------------------------
def search_instruments(query: str, limit: int = 20) -> List[Dict[str, str]]:
    q = (query or "").strip().lower()
    if not q:
        return []
    rows = get_instruments_csv()
    out: List[Dict[str, str]] = []
    for r in rows:
        sym = (r.get("SM_SYMBOL_NAME") or r.get("SYMBOL_NAME") or "").lower()
        disp = (r.get("SEM_CUSTOM_SYMBOL") or r.get("DISPLAY_NAME") or "").lower()
        if q in sym or q in disp:
            out.append(r)
            if len(out) >= limit:
                break
    return out

# ------------------------------
# Public: Expiry list for an underlying symbol (e.g. 'NIFTY', 'BANKNIFTY')
# We derive from the detailed CSV to avoid extra calls.
# ------------------------------
def get_expiry_list(symbol: str, exchange: str = "NSE") -> List[str]:
    """
    Return sorted list of unique expiry dates (YYYY-MM-DD) for the given underlying symbol
    in Derivatives on specified exchange (default NSE).
    """
    sym = (symbol or "").upper().strip()
    rows = get_instruments_csv()
    exp: set[str] = set()
    for r in rows:
        # Filter only Derivatives on exchange with OPTION rows
        exch = (r.get("SEM_EXM_EXCH_ID") or r.get("EXCH_ID") or "").upper()
        seg  = (r.get("SEM_SEGMENT") or r.get("SEGMENT") or "").upper()
        inst = (r.get("SEM_EXCH_INSTRUMENT_TYPE") or r.get("INSTRUMENT_TYPE") or "").upper()
        undl = (r.get("UNDERLYING_SYMBOL") or "").upper()
        ed   = (r.get("SEM_EXPIRY_DATE") or r.get("SM_EXPIRY_DATE") or "").strip()

        # Derivatives ≈ 'D' segment; some rows have empty INST for equities
        if exch == exchange.upper() and seg == "D" and undl == sym and ed:
            exp.add(ed)

    return sorted(exp)

# ------------------------------
# Public: Option Chain (CSV-based skeleton)
# Builds calls/puts grid for a given underlying (and optional expiry)
# ------------------------------
def get_option_chain_raw(symbol: str, expiry: Optional[str] = None, exchange: str = "NSE") -> Dict[str, Any]:
    """
    Build a lightweight option chain structure from the CSV master.
    This returns meta (underlying, expiry) and two arrays: calls, puts.
    Each item has trading_symbol, strike, option_type, expiry, lot_size.
    NOTE: LTP/Greeks are not included here (add via your market-quote flow if needed).
    """
    sym = (symbol or "").upper().strip()
    rows = get_instruments_csv()

    # If expiry not given, choose nearest (min) from available list
    all_exp = get_expiry_list(sym, exchange=exchange)
    if not all_exp:
        return {"symbol": sym, "expiry": None, "calls": [], "puts": []}
    chosen_exp = expiry or all_exp[0]

    calls: List[Dict[str, Any]] = []
    puts:  List[Dict[str, Any]] = []

    for r in rows:
        exch = (r.get("SEM_EXM_EXCH_ID") or r.get("EXCH_ID") or "").upper()
        seg  = (r.get("SEM_SEGMENT") or r.get("SEGMENT") or "").upper()
        undl = (r.get("UNDERLYING_SYMBOL") or "").upper()
        ed   = (r.get("SEM_EXPIRY_DATE") or r.get("SM_EXPIRY_DATE") or "").strip()
        optt = (r.get("SEM_OPTION_TYPE") or r.get("OPTION_TYPE") or "").upper()
        strike = r.get("SEM_STRIKE_PRICE") or r.get("STRIKE_PRICE") or ""
        lot = r.get("SEM_LOT_UNITS") or r.get("LOT_SIZE") or ""
        tsym = r.get("SEM_TRADING_SYMBOL") or r.get("TRADING_SYMBOL") or r.get("DISPLAY_NAME") or ""

        if exch != exchange.upper() or seg != "D" or undl != sym:
            continue
        if not optt or not ed or ed != chosen_exp:
            continue

        try:
            strike_val = float(strike) if str(strike).strip() else None
        except Exception:
            strike_val = None

        item = {
            "trading_symbol": tsym,
            "strike": strike_val,
            "option_type": optt,  # CE / PE
            "expiry": ed,
            "lot_size": int(float(lot)) if str(lot).strip() else None,
        }

        if optt == "CE":
            calls.append(item)
        elif optt == "PE":
            puts.append(item)

    # Sort by strike
    calls.sort(key=lambda x: (x["strike"] is None, x["strike"]))
    puts.sort(key=lambda x: (x["strike"] is None, x["strike"]))

    return {
        "symbol": sym,
        "expiry": chosen_exp,
        "calls": calls,
        "puts": puts,
        "source": "csv-master",
    }
