# App/Services/dhan_client.py
from __future__ import annotations
import os, time, io, csv, threading
from typing import List, Dict, Optional
import requests

# ---- Dhan instrument sources (official)
DHAN_CSV_COMPACT = "https://images.dhan.co/api-data/api-scrip-master.csv"
DHAN_CSV_DETAILED = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

# Cache settings
_TTL_SECONDS = int(os.getenv("INSTRUMENTS_TTL_SECONDS", str(6 * 60 * 60)))  # 6 hours
_lock = threading.Lock()
_cache: Dict[str, object] = {"rows": None, "fetched_at": 0.0, "source": DHAN_CSV_DETAILED}

def _fetch_detailed_csv() -> List[Dict[str, str]]:
    """Fetch detailed instruments CSV from Dhan and return list[dict]."""
    resp = requests.get(DHAN_CSV_DETAILED, timeout=60)
    resp.raise_for_status()
    data = resp.content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(data))
    rows = [dict(r) for r in reader]
    return rows

def get_instruments_csv(force: bool = False) -> List[Dict[str, str]]:
    """Cached getter for detailed CSV."""
    now = time.time()
    with _lock:
        if (not force) and _cache.get("rows") and (now - float(_cache["fetched_at"])) < _TTL_SECONDS:
            return _cache["rows"]  # type: ignore[return-value]
        rows = _fetch_detailed_csv()
        _cache["rows"] = rows
        _cache["fetched_at"] = now
        _cache["source"] = DHAN_CSV_DETAILED
        return rows

# Backward friendly name
def get_instruments(force: bool = False) -> List[Dict[str, str]]:
    return get_instruments_csv(force=force)

def refresh_instruments() -> Dict[str, object]:
    rows = get_instruments_csv(force=True)
    return {"ok": True, "count": len(rows), "refreshed_at": _cache["fetched_at"]}

def get_cache_meta() -> Dict[str, object]:
    return {
        "ok": True,
        "count": len(_cache["rows"] or []),
        "fetched_at": _cache["fetched_at"],
        "ttl_seconds": _TTL_SECONDS,
        "source": _cache["source"],
        "hint": "Data comes directly from Dhan CSV (detailed).",
    }

# ---- Helpers / Lookups ----
def _norm(s: Optional[str]) -> str:
    return (s or "").strip()

def search_instruments(q: str, limit: int = 100) -> List[Dict[str, str]]:
    ql = q.lower().strip()
    out: List[Dict[str, str]] = []
    for r in get_instruments_csv():
        if len(out) >= limit:
            break
        # Try multiple relevant columns from Dhan detailed CSV
        hay = " ".join([
            _norm(r.get("SEM_TRADING_SYMBOL")),
            _norm(r.get("DISPLAY_NAME")),
            _norm(r.get("SM_SYMBOL_NAME")),
            _norm(r.get("UNDERLYING_SYMBOL")),
            _norm(r.get("SEM_CUSTOM_SYMBOL")),
        ]).lower()
        if ql in hay:
            out.append(r)
    return out

def get_by_trading_symbol(trading_symbol: str) -> Optional[Dict[str, str]]:
    ts = trading_symbol.strip().upper()
    for r in get_instruments_csv():
        if _norm(r.get("SEM_TRADING_SYMBOL")).upper() == ts:
            return r
    return None

def get_by_security_id(security_id: str) -> Optional[Dict[str, str]]:
    si = security_id.strip().upper()
    for r in get_instruments_csv():
        if _norm(r.get("UNDERLYING_SECURITY_ID")).upper() == si or _norm(r.get("SM_SECURITY_ID", "")).upper() == si:
            return r
    return None

# ---- NEW: Segment-wise (filtering CSV; Dhan source hi hai)
# exch: NSE/BSE/MCX ; segment: E (Equity), D (Derivatives), C (Currency), M (Commodity)
def get_instruments_by_segment(exch: Optional[str] = None, segment: Optional[str] = None, limit: int = 5000) -> List[Dict[str, str]]:
    ex = (exch or "").strip().upper()
    sg = (segment or "").strip().upper()
    out: List[Dict[str, str]] = []
    for r in get_instruments_csv():
        if len(out) >= limit:
            break
        ok = True
        if ex:
            ok = ok and _norm(r.get("EXCH_ID")).upper() == ex
        if sg:
            ok = ok and _norm(r.get("SEGMENT")).upper() == sg
        if ok:
            out.append(r)
    return out
