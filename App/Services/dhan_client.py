<<<<<<< HEAD
# App/Services/dhan_client.py
from __future__ import annotations
=======
python - <<'PY'
from App.Services.dhan_client import get_instruments_csv, list_segments
rows = get_instruments_csv()
print("Fetched rows:", len(rows))
print("Segments:", list_segments()[:10])
if rows:
    print("Sample:", {k: rows[0][k] for k in list(rows[0])[:6]})
PYfrom __future__ import annotations
>>>>>>> 55f49b0 (feat: add Dhan instruments client with cache/search)

import os
import time
import csv
import io
from typing import Dict, List, Tuple, Iterable, Optional

import requests

# -------- Config (overridable via Render env or .env) -------------------------
INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-script-master-detailed.csv",
)
INSTRUMENTS_TTL_SEC = int(os.getenv("INSTRUMENTS_TTL_SEC", "86400"))  # 24h cache

# In-memory cache: key -> (timestamp, data)
_CACHE: Dict[str, Tuple[float, List[Dict[str, str]]]] = {}


# -------- Core fetch + cache --------------------------------------------------
def _download_instruments_csv() -> List[Dict[str, str]]:
    """
    Downloads Dhan instruments CSV and returns list of dict rows.
    Raises requests.HTTPError on non-200.
    """
    r = requests.get(INSTRUMENTS_URL, timeout=30)
    r.raise_for_status()
    # Parse CSV
    text = r.text
    rows = list(csv.DictReader(io.StringIO(text)))
    return rows


def get_instruments_csv(force: bool = False) -> List[Dict[str, str]]:
    """
    Public API used by routers. Returns cached instruments unless TTL expired,
    or force=True is passed.
    """
    now = time.time()
    if not force and "data" in _CACHE:
        ts, data = _CACHE["data"]
        if now - ts < INSTRUMENTS_TTL_SEC:
            return data

    data = _download_instruments_csv()
    _CACHE["data"] = (now, data)
    return data


# -------- Convenience helpers (safe to use from routers) ----------------------
def filter_by_segment(rows: Iterable[Dict[str, str]], exchange_segment: Optional[str]) -> List[Dict[str, str]]:
    """
    Filter instruments by exchange segment (e.g., 'IDX_I', 'NSE_EQ', 'NSE_FNO', etc.)
    If exchange_segment is None or empty, returns all.
    """
    if not exchange_segment:
        return list(rows)
    seg = exchange_segment.strip().upper()
    return [r for r in rows if str(r.get("EXCHANGE_SEGMENT", "")).upper() == seg]


def search_instruments(
    query: str,
    exchange_segment: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, str]]:
    """
    Case-insensitive substring match across common columns.
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    rows = get_instruments_csv()
    if exchange_segment:
        rows = filter_by_segment(rows, exchange_segment)

    cols_to_check = [
        "SYMBOL",
        "TRADING_SYMBOL",
        "SECURITY_ID",
        "EXCHANGE_SEGMENT",
        "ISIN",
        "INSTRUMENT",
        "SERIES",
        "DESCRIPTION",
    ]

    out: List[Dict[str, str]] = []
    for r in rows:
        for col in cols_to_check:
            val = str(r.get(col, "")).lower()
            if q in val:
                out.append(r)
                break
        if len(out) >= limit:
            break
    return out


def list_segments() -> List[str]:
    """
    Returns distinct EXCHANGE_SEGMENT values from the instruments list.
    """
    rows = get_instruments_csv()
    segs = sorted({str(r.get("EXCHANGE_SEGMENT", "")).upper() for r in rows if r.get("EXCHANGE_SEGMENT")})
    return segs


def list_indices() -> List[Dict[str, str]]:
    """
    Tries to return rows that look like indices (heuristic).
    You can tweak this based on your CSV columns.
    """
    rows = get_instruments_csv()
    out: List[Dict[str, str]] = []
    for r in rows:
        # Heuristic examples (adjust based on your CSV):
        # Many CSVs have INSTRUMENT == 'INDEX' or SYMBOL like 'NIFTY', 'BANKNIFTY'
        instrument = str(r.get("INSTRUMENT", "")).upper()
        symbol = str(r.get("SYMBOL", "")).upper()
        if "INDEX" in instrument or symbol in {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX"}:
            out.append(r)
    return out


def force_refresh() -> int:
    """
    Clears cache and triggers refetch on next get_instruments_csv() call.
    Returns 1 if cache was cleared, else 0.
    """
    if "data" in _CACHE:
        del _CACHE["data"]
        return 1
    return 0
