# App/Services/dhan_client.py
from __future__ import annotations
import os, io, csv, time, requests
from typing import List, Dict, Optional

# ---- Dhan CSV URLs (Dhan docs)
DHAN_COMPACT_URL  = os.getenv(
    "DHAN_INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-scrip-master.csv"
)
DHAN_DETAILED_URL = os.getenv(
    "DHAN_INSTRUMENTS_DETAILED_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
)

# Cache (memory)
_CACHE: Dict[str, object] = {"rows": None, "ts": 0.0, "url": DHAN_COMPACT_URL}
_CACHE_TTL = int(os.getenv("INSTRUMENTS_CACHE_TTL", "3600"))  # 1 hour

# Which url to use: "compact" (default) or "detailed"
_MODE = os.getenv("INSTRUMENTS_MODE", "compact").strip().lower()


def _active_url() -> str:
    return DHAN_DETAILED_URL if _MODE == "detailed" else DHAN_COMPACT_URL


def _load_csv(url: str) -> List[Dict[str, str]]:
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    # CSV may contain unicode — decode and parse
    buf = io.StringIO(r.content.decode("utf-8"))
    reader = csv.DictReader(buf)
    return list(reader)


def get_instruments_csv(segment: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Returns the entire Dhan instruments CSV (from Compact or Detailed file),
    with simple in-memory caching. If `segment` is provided, rows are filtered
    by exchange/segment column (works for both Compact/Detailed header variants).
    """
    now = time.time()
    url = _active_url()

    needs_refresh = (
        not _CACHE["rows"]
        or (now - float(_CACHE["ts"])) > _CACHE_TTL
        or _CACHE.get("url") != url
    )
    if needs_refresh:
        rows = _load_csv(url)
        _CACHE["rows"] = rows
        _CACHE["ts"] = now
        _CACHE["url"] = url

    rows: List[Dict[str, str]] = _CACHE["rows"]  # type: ignore

    if not segment:
        return rows

    seg = segment.strip().upper()
    # Column names differ between compact vs detailed CSV.
    # Try common possibilities:
    candidates = (
        "EXCHANGE",              # sometimes present
        "EXCH_ID",               # detailed
        "SEM_EXM_EXCH_ID",       # compact tag in docs
        "EXCHANGESEGMENT",       # some older dumps
        "ExchangeSegment",       # mixed-case
        "SEGMENT", "SEM_SEGMENT" # back-up filters if needed
    )

    # If the CSV has explicit SEGMENT/SEM_SEGMENT as single-letter codes (E/D/C/M),
    # user may pass NSE/BSE/MCX too. Prefer exact exchange code first, else fall back.
    def row_matches(r: Dict[str, str]) -> bool:
        for c in candidates:
            if c in r and r[c]:
                if r[c].strip().upper() == seg:
                    return True
        return False

    filtered = [r for r in rows if row_matches(r)]
    return filtered


def search_instruments(q: str, segment: Optional[str] = None, limit: int = 50) -> List[Dict[str, str]]:
    """
    Case-insensitive substring search over a few useful columns:
      - SYMBOL_NAME / SM_SYMBOL_NAME / SEM_TRADING_SYMBOL / DISPLAY_NAME / SEM_CUSTOM_SYMBOL
    """
    rows = get_instruments_csv(segment=segment)
    if not q:
        return rows[:limit]

    ql = q.strip().upper()
    cols = (
        "SYMBOL_NAME", "SM_SYMBOL_NAME",
        "SEM_TRADING_SYMBOL",
        "DISPLAY_NAME", "SEM_CUSTOM_SYMBOL",
        "UNDERLYING_SYMBOL",  # helpful for derivatives
    )

    out: List[Dict[str, str]] = []
    for r in rows:
        for c in cols:
            if c in r and r[c] and ql in r[c].upper():
                out.append(r)
                break
        if len(out) >= limit:
            break
    return out


# --------- Backward-compat alias (ROUTER EXPECTS THIS NAME) ----------
def get_instruments_by_segment(segment: str) -> List[Dict[str, str]]:
    """
    Old router import uses this name. Keep as thin alias so routers don't break.
    """
    return get_instruments_csv(segment)
