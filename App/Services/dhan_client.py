# App/Services/dhan_client.py
from __future__ import annotations

import csv
import gzip
import io
import json
import os
import time
from typing import Dict, List, Optional, Tuple

import requests

# --------- Config ---------
DHAN_CSV_COMPACT = os.getenv(
    "DHAN_CSV_COMPACT",
    "https://images.dhan.co/api-data/api-scrip-master.csv",
)
DHAN_CSV_DETAILED = os.getenv(
    "DHAN_CSV_DETAILED",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv",
)

# Optional fallback (segmentwise, used rarely)
DHAN_SEGMENT_API_BASE = os.getenv("DHAN_SEGMENT_API_BASE", "https://api.dhan.co/v2/instrument")

CACHE_DIR = os.getenv("CACHE_DIR", "data")
CACHE_FILE = os.path.join(CACHE_DIR, "instruments.json.gz")
CACHE_TTL_SECONDS = int(os.getenv("INSTRUMENTS_TTL_SECONDS", "0"))  # 0 = never auto-expire

# In-process cache
_cache: Dict[str, any] = {"rows": [], "meta": {}}


# --------- Helpers ---------
def _ensure_cache_dir() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)


def _save_cache(rows: List[Dict], meta: Dict) -> None:
    _ensure_cache_dir()
    payload = {"rows": rows, "meta": meta}
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(json.dumps(payload).encode("utf-8"))
    with open(CACHE_FILE, "wb") as f:
        f.write(buf.getvalue())


def _load_cache_from_disk() -> Tuple[List[Dict], Dict]:
    if not os.path.exists(CACHE_FILE):
        return [], {}
    with gzip.open(CACHE_FILE, "rb") as f:
        payload = json.loads(f.read().decode("utf-8"))
    return payload.get("rows", []), payload.get("meta", {})


def _now_ts() -> int:
    return int(time.time())


def _normalize_row(row: Dict[str, str]) -> Dict:
    """
    Normalize both Compact & Detailed CSV columns into a common minimal schema.
    We keep the original columns as well (under 'raw') so nothing is lost.
    """
    # Detailed keys (preferred)
    exch = row.get("EXCH_ID") or row.get("SEM_EXM_EXCH_ID")
    seg = row.get("SEGMENT") or row.get("SEM_SEGMENT")
    instr = row.get("INSTRUMENT") or row.get("SEM_INSTRUMENT_NAME")
    trading_sym = row.get("SEM_TRADING_SYMBOL") or row.get("TRADING_SYMBOL") or row.get("SYMBOL_NAME") or row.get("SM_SYMBOL_NAME")
    display = row.get("DISPLAY_NAME") or row.get("SEM_CUSTOM_SYMBOL") or row.get("SYMBOL_NAME") or trading_sym
    series = row.get("SERIES") or row.get("SEM_SERIES")
    lot = row.get("LOT_SIZE") or row.get("SEM_LOT_UNITS")
    expiry = row.get("SM_EXPIRY_DATE") or row.get("SEM_EXPIRY_DATE")
    strike = row.get("STRIKE_PRICE") or row.get("SEM_STRIKE_PRICE")
    opt_type = row.get("OPTION_TYPE") or row.get("SEM_OPTION_TYPE")
    sec_id = row.get("UNDERLYING_SECURITY_ID") or row.get("SECURITY_ID") or row.get("UNDERLYING SECURITY ID") or row.get("SECURITYID")

    base = {
        "exchange": exch,
        "segment": seg,
        "instrument": instr,
        "trading_symbol": trading_sym,
        "display_name": display,
        "series": series,
        "lot_size": _maybe_int(lot),
        "expiry": expiry,
        "strike_price": _maybe_float(strike),
        "option_type": opt_type,
        "security_id": sec_id,
    }
    base["raw"] = row
    return base


def _maybe_int(v: Optional[str]) -> Optional[int]:
    try:
        return int(float(v)) if v not in (None, "", "NA") else None
    except Exception:
        return None


def _maybe_float(v: Optional[str]) -> Optional[float]:
    try:
        return float(v) if v not in (None, "", "NA") else None
    except Exception:
        return None


def _download_csv(url: str, timeout: int = 60) -> List[Dict]:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    text = r.text
    # CSV may have \r\n — csv.DictReader handles it.
    reader = csv.DictReader(io.StringIO(text))
    rows = [_normalize_row(row) for row in reader]
    return rows


# --------- Public: cache lifecycle ---------
def refresh_instruments(kind: str = "detailed") -> Dict:
    """
    Download Dhan CSV (detailed/compact), normalize, cache to disk + memory.
    Returns meta summary.
    """
    url = DHAN_CSV_DETAILED if kind.lower() == "detailed" else DHAN_CSV_COMPACT
    rows = _download_csv(url)
    meta = {
        "kind": kind.lower(),
        "source_url": url,
        "rows": len(rows),
        "refreshed_at": _now_ts(),
        "cache_file": CACHE_FILE,
    }
    _cache["rows"] = rows
    _cache["meta"] = meta
    _save_cache(rows, meta)
    return meta


def ensure_cache(use_disk: bool = True) -> None:
    """
    Load cache from disk if memory is empty or TTL expired.
    If no disk cache, trigger a fresh detailed download.
    """
    # if memory cache looks good and not expired, keep it
    if _cache.get("rows"):
        if CACHE_TTL_SECONDS > 0:
            ts = _cache.get("meta", {}).get("refreshed_at") or 0
            if _now_ts() - ts <= CACHE_TTL_SECONDS:
                return
        else:
            return

    if use_disk and os.path.exists(CACHE_FILE):
        rows, meta = _load_cache_from_disk()
        if rows:
            _cache["rows"] = rows
            _cache["meta"] = meta
            return

    # last resort: pull fresh detailed
    refresh_instruments(kind="detailed")


# --------- Public: queries ---------
def get_cache_meta() -> Dict:
    ensure_cache()
    return _cache.get("meta", {})


def get_instruments() -> List[Dict]:
    """
    Return all normalized instruments (from memory cache).
    """
    ensure_cache()
    return _cache["rows"]


def search_instruments(
    q: Optional[str] = None,
    exchange: Optional[str] = None,
    segment: Optional[str] = None,
    instrument_type: Optional[str] = None,
    limit: int = 100,
) -> List[Dict]:
    """
    Simple substring search on trading_symbol/display_name/symbol_name;
    with optional filters.
    """
    ensure_cache()
    rows = _cache["rows"]

    def ok(row: Dict) -> bool:
        if exchange and (row.get("exchange") or "").upper() != exchange.upper():
            return False
        if segment and (row.get("segment") or "").upper() != segment.upper():
            return False
        if instrument_type:
            instr = (row.get("instrument") or "").upper()
            if instrument_type.upper() not in instr:
                return False
        if q:
            ql = q.lower()
            ts = (row.get("trading_symbol") or "").lower()
            dn = (row.get("display_name") or "").lower()
            sym = (row.get("raw", {}).get("SYMBOL_NAME") or "").lower()
            if (ql not in ts) and (ql not in dn) and (ql not in sym):
                return False
        return True

    out = []
    for r in rows:
        if ok(r):
            out.append(r)
            if len(out) >= limit:
                break
    return out


def get_by_trading_symbol(symbol: str) -> Optional[Dict]:
    ensure_cache()
    s = symbol.lower()
    for r in _cache["rows"]:
        ts = (r.get("trading_symbol") or "").lower()
        if ts == s:
            return r
    return None


def get_by_security_id(security_id: str) -> Optional[Dict]:
    ensure_cache()
    s = security_id.strip()
    for r in _cache["rows"]:
        if (r.get("security_id") or "").strip() == s:
            return r
    return None


# --------- Optional fallback: segment API ---------
def fetch_segment(exchange_segment: str, timeout: int = 60) -> Dict:
    """
    Only for fallback / debug. Hits Dhan segmentwise endpoint.
    Returns {'ok': bool, 'count': int, 'rows': [...], 'url': ...}
    """
    url = f"{DHAN_SEGMENT_API_BASE}/{exchange_segment}"
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        # Some environments return CSV, some JSON; try both
        content_type = r.headers.get("content-type", "")
        if "json" in content_type:
            data = r.json()
            # try to normalize if it's a list of dicts
            rows = [_normalize_row(x) if isinstance(x, dict) else x for x in data] if isinstance(data, list) else []
        else:
            # assume CSV
            rows = [_normalize_row(x) for x in csv.DictReader(io.StringIO(r.text))]
        return {"ok": True, "count": len(rows), "rows": rows, "url": url}
    except Exception as e:
        return {"ok": False, "count": 0, "rows": [], "url": url, "error": str(e)}
