# App/Services/dhan_client.py
from __future__ import annotations
import os
import time
import csv
import io
import requests
from typing import List, Dict, Any, Optional

# --------------------------------------------------------------------
# Config from ENV
# --------------------------------------------------------------------
INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-script-master-detailed.csv",
)
INSTRUMENTS_TTL_SEC = int(os.getenv("INSTRUMENTS_TTL_SEC", "86400"))

DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# Simple in-memory cache for instruments CSV
_instruments_cache: Dict[str, Any] = {"ts": 0.0, "rows": None}


# --------------------------------------------------------------------
# Instruments CSV Loader
# --------------------------------------------------------------------
def _download_csv_text(url: str, timeout: int = 30) -> str:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    text = resp.text
    if not text:
        raise RuntimeError("Empty CSV from instruments URL")
    return text

def _parse_csv(text: str) -> List[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict[str, Any]] = []
    for row in reader:
        rows.append({(k or "").strip(): (v.strip() if isinstance(v, str) else v)
                     for k, v in row.items()})
    return rows

def get_instruments_csv(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Returns the instruments master as list[dict].
    Cached for INSTRUMENTS_TTL_SEC seconds.
    """
    now = time.time()
    if (
        not force_refresh
        and _instruments_cache["rows"] is not None
        and (now - float(_instruments_cache["ts"])) < INSTRUMENTS_TTL_SEC
    ):
        return _instruments_cache["rows"]  # type: ignore

    text = _download_csv_text(INSTRUMENTS_URL)
    rows = _parse_csv(text)
    _instruments_cache["rows"] = rows
    _instruments_cache["ts"] = now
    return rows


# --------------------------------------------------------------------
# Dhan endpoints (stubs for now; wire real API later)
# --------------------------------------------------------------------
def get_option_chain(symbol: str, expiry: Optional[str] = None) -> Dict[str, Any]:
    # TODO: Implement real DhanHQ API call
    return {"ok": True, "symbol": symbol, "expiry": expiry, "data": []}

def get_market_quote(symbol: str) -> Dict[str, Any]:
    # TODO: Implement real DhanHQ API call
    return {"ok": True, "symbol": symbol, "ltp": None, "bid": None, "ask": None}

def get_marketfeed(symbols: List[str]) -> Dict[str, Any]:
    # TODO: Implement real DhanHQ API call
    return {"ok": True, "symbols": symbols, "feed": []}

def get_historical(symbol: str, timeframe: str = "1d", limit: int = 100) -> Dict[str, Any]:
    # TODO: Implement real DhanHQ API call
    return {"ok": True, "symbol": symbol, "timeframe": timeframe, "data": []}

def get_annexure() -> Dict[str, Any]:
    # TODO: Implement real DhanHQ API call
    return {"ok": True, "annexure": []}
