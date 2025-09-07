# App/Services/dhan_client.py
import csv, io, time, threading
from typing import List, Dict, Optional
import requests

# ---- Dhan sources (ONLY Dhan)
DETAILED_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
COMPACT_URL  = "https://images.dhan.co/api-data/api-scrip-master.csv"

# ---- In-memory cache
_cache_lock = threading.Lock()
_cache_rows: List[Dict] = []
_cache_meta = {"source": "detailed", "fetched_at": 0, "rows": 0, "ttl_sec": 6*60*60}

def _download_csv(url: str) -> List[Dict]:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    content = r.content.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))
    rows = [ {k.strip(): (v.strip() if isinstance(v, str) else v) for k,v in row.items()} for row in reader ]
    return rows

def _ensure_cache(force: bool = False, source: str = "detailed") -> None:
    global _cache_rows, _cache_meta
    now = time.time()
    with _cache_lock:
        need = force or (now - _cache_meta["fetched_at"] > _cache_meta["ttl_sec"]) or not _cache_rows
        if not need:
            return
        url = DETAILED_URL if source == "detailed" else COMPACT_URL
        rows = _download_csv(url)
        _cache_rows = rows
        _cache_meta = {"source": source, "fetched_at": now, "rows": len(rows), "ttl_sec": _cache_meta["ttl_sec"]}

# ---- Public helpers (these names are what routers import)
def get_instruments_csv(source: str = "detailed") -> List[Dict]:
    _ensure_cache(force=False, source=source)
    return _cache_rows

def refresh_instruments(source: str = "detailed") -> Dict:
    _ensure_cache(force=True, source=source)
    return _cache_meta

def get_cache_meta() -> Dict:
    return _cache_meta

def get_instruments(limit: Optional[int] = None) -> List[Dict]:
    rows = get_instruments_csv()
    return rows[:limit] if limit else rows

def get_instruments_by_segment(exch: Optional[str] = None, segment: Optional[str] = None, limit: int = 5000) -> List[Dict]:
    """
    exch: NSE/BSE/MCX ; segment: E (Equity) / D (Derivatives) / C (Currency) / M (Commodity)
    Uses DETAILED CSV columns: EXCH_ID, SEGMENT, SEM_TRADING_SYMBOL, etc.
    """
    rows = get_instruments_csv()
    out = []
    ex = (exch or "").upper()
    sg = (segment or "").upper()
    for r in rows:
        if ex and r.get("EXCH_ID","").upper() != ex:
            continue
        if sg and r.get("SEGMENT","").upper() != sg:
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out

def search_instruments(q: str, limit: int = 100) -> List[Dict]:
    q = (q or "").strip().upper()
    if not q:
        return []
    rows = get_instruments_csv()
    out = []
    for r in rows:
        hay = " ".join([
            r.get("SEM_TRADING_SYMBOL",""),
            r.get("SYMBOL_NAME",""),
            r.get("DISPLAY_NAME",""),
            r.get("UNDERLYING_SYMBOL",""),
        ]).upper()
        if q in hay:
            out.append(r)
            if len(out) >= limit:
                break
    return out

def get_by_trading_symbol(symbol: str) -> Optional[Dict]:
    sy = (symbol or "").upper()
    for r in get_instruments_csv():
        if r.get("SEM_TRADING_SYMBOL","").upper() == sy:
            return r
    return None

def get_by_security_id(sec_id: str) -> Optional[Dict]:
    sid = (sec_id or "").upper()
    # Detailed CSV column name:
    key = "UNDERLYING_SECURITY_ID" if "UNDERLYING_SECURITY_ID" in (get_instruments_csv()[0] if get_instruments_csv() else {}) else "SECURITY_ID"
    for r in get_instruments_csv():
        if (r.get(key,"") or "").upper() == sid:
            return r
    return None
