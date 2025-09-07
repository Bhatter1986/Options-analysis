# App/Services/dhan_client.py
from __future__ import annotations
import os, time, csv, io
from typing import Dict, List, Optional, Tuple
import requests

# ---- ENV (Dhan-hosted CSV)
CSV_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-script-master-detailed.csv"
)
TTL_SEC = int(os.getenv("INSTRUMENTS_TTL_SEC", "86400"))  # default 1 day

# ---- Simple in-memory cache
_cache: Dict[str, object] = {
    "rows": None,          # type: Optional[List[Dict[str, str]]]
    "fetched_at": 0.0,     # type: float (epoch)
}

# ---- Helpers to normalize column names coming from Dhan CSV
def _get(row: Dict[str, str], *keys: str) -> Optional[str]:
    for k in keys:
        if k in row and row[k] not in ("", None):
            return row[k]
    return None

def _seg(row: Dict[str, str]) -> str:
    # Try common variants
    return (_get(row, "exchange_segment", "exchangeSegment", "segment") or "").strip()

def _symbol(row: Dict[str, str]) -> str:
    return (_get(row, "symbol", "Symbol", "tradingsymbol", "tradingSymbol", "trading_symbol") or "").strip()

def _name(row: Dict[str, str]) -> str:
    return (_get(row, "name", "Name", "description", "Description") or "").strip()

def _security_id(row: Dict[str, str]) -> str:
    return (_get(row, "security_id", "securityId", "SecurityId", "securityID", "securityid") or "").strip()

# ---- Core CSV loader (Dhan only)
def _load_csv(force: bool = False) -> List[Dict[str, str]]:
    now = time.time()
    if (not force) and _cache["rows"] and (now - float(_cache["fetched_at"])) < TTL_SEC:
        return _cache["rows"]  # type: ignore

    resp = requests.get(CSV_URL, timeout=60)
    resp.raise_for_status()
    content = resp.content.decode("utf-8", errors="replace")

    buf = io.StringIO(content)
    reader = csv.DictReader(buf)
    rows = []
    for row in reader:
        # keep original row + normalized keys for easy filter/search
        row = dict(row or {})
        row["_norm"] = {
            "exchange_segment": _seg(row),
            "symbol": _symbol(row),
            "name": _name(row),
            "security_id": _security_id(row),
        }
        rows.append(row)

    _cache["rows"] = rows
    _cache["fetched_at"] = now
    return rows

# ---- Public API used by Routers (DON'T CHANGE NAMES)
def get_instruments_csv(segment: Optional[str] = None) -> Tuple[List[Dict[str, str]], Dict[str, object]]:
    """
    Return full CSV (optionally filtered by exchange segment).
    """
    rows = _load_csv()
    if segment:
        seg = segment.strip().upper()
        rows = [r for r in rows if (r.get("_norm", {}).get("exchange_segment", "").upper() == seg)]
    meta = {
        "source": "dhan_csv",
        "url": CSV_URL,
        "ttl_sec": TTL_SEC,
        "count": len(rows),
    }
    return rows, meta

def get_instruments_by_segment(segment: str) -> Tuple[List[Dict[str, str]], Dict[str, object]]:
    """
    Backward-compatible wrapper (some modules import this).
    """
    return get_instruments_csv(segment)

def search_instruments(keyword: str, segment: Optional[str] = None, limit: int = 50) -> Tuple[List[Dict[str, str]], Dict[str, object]]:
    """
    Simple case-insensitive contains search on symbol/name within optional segment.
    """
    kw = (keyword or "").strip().lower()
    if not kw:
        return [], {"source": "dhan_csv", "url": CSV_URL, "ttl_sec": TTL_SEC, "count": 0, "query": keyword}

    rows = _load_csv()
    if segment:
        seg = segment.strip().upper()
        rows = [r for r in rows if (r.get("_norm", {}).get("exchange_segment", "").upper() == seg)]

    out: List[Dict[str, str]] = []
    for r in rows:
        sym = r.get("_norm", {}).get("symbol", "").lower()
        nm  = r.get("_norm", {}).get("name", "").lower()
        if kw in sym or kw in nm:
            out.append(r)
            if len(out) >= limit:
                break

    meta = {
        "source": "dhan_csv",
        "url": CSV_URL,
        "ttl_sec": TTL_SEC,
        "count": len(out),
        "query": keyword,
        "segment": segment,
    }
    return out, meta
