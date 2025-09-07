# App/Services/dhan_client.py
"""
Dhan instruments client — ONLY Dhan official CSV sources.

Sources (v2 docs):
- Compact CSV : https://images.dhan.co/api-data/api-scrip-master.csv
- Detailed CSV: https://images.dhan.co/api-data/api-scrip-master-detailed.csv

We fetch the Detailed CSV by default (richer columns), then filter / search in-memory.
"""

from __future__ import annotations
import csv
import io
import time
import typing as t
import requests

# ---- Dhan CSV URLs
COMPACT_CSV_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
DETAILED_CSV_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

# ---- Simple in-memory cache
_CACHE: dict[str, tuple[float, list[dict]]] = {}
_DEFAULT_TTL = 60 * 30  # 30 minutes


def _http_get(url: str, timeout: int = 30) -> str:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    # CSV is text
    return r.text


def _load_csv(text: str) -> list[dict]:
    # autodetect header with csv DictReader
    buff = io.StringIO(text)
    reader = csv.DictReader(buff)
    rows = [dict({k: (v or "").strip() for k, v in row.items()}) for row in reader]
    return rows


def _get_cached(key: str, ttl: int) -> list[dict] | None:
    now = time.time()
    item = _CACHE.get(key)
    if not item:
        return None
    ts, data = item
    if now - ts > ttl:
        return None
    return data


def _set_cache(key: str, data: list[dict]) -> None:
    _CACHE[key] = (time.time(), data)


# ---------- Public API ----------

def get_instruments_csv(detailed: bool = True, ttl: int = _DEFAULT_TTL) -> list[dict]:
    """
    Fetch the Dhan instruments CSV (detailed by default) and return as list of dicts.
    Cached for `ttl` seconds to avoid repeated downloads.
    """
    url = DETAILED_CSV_URL if detailed else COMPACT_CSV_URL
    key = f"csv::{ 'detailed' if detailed else 'compact' }"
    cached = _get_cached(key, ttl)
    if cached is not None:
        return cached

    text = _http_get(url)
    rows = _load_csv(text)
    _set_cache(key, rows)
    return rows


def _norm(s: str) -> str:
    return (s or "").strip().upper()


def _match_segment(row: dict, segment: str) -> bool:
    """
    Try to match exchange/segment from Dhan CSV row.
    CSV columns (detailed) include at least:
      EXCH_ID (NSE/BSE/MCX), SEGMENT (E/D/C/M), SEM_EXM_EXCH_ID, SEM_SEGMENT, etc.
    We accept common tokens like: NSE, BSE, MCX, NSEFO, NSE-FNO, NSE-D, etc.
    """
    seg = _norm(segment)

    exch = _norm(row.get("EXCH_ID") or row.get("SEM_EXM_EXCH_ID") or "")
    seg_code = _norm(row.get("SEGMENT") or row.get("SEM_SEGMENT") or "")

    # Basic exchange-only filter: NSE / BSE / MCX
    if seg in {"NSE", "BSE", "MCX"}:
        return exch == seg

    # Combined styles: NSEFO / NSE-FNO / NSE-D / NSE_E / BSE-E, etc.
    if seg.startswith("NSE") or seg.startswith("BSE") or seg.startswith("MCX"):
        want_exch = seg.split("-")[0].split("_")[0].split("F")[0]  # crude but robust
        if exch != _norm(want_exch):
            return False
        # Derive segment letter if provided (E/D/C/M)
        # heuristics: look for E or D/C/M in token
        if "FO" in seg or "-FNO" in seg or seg.endswith("D"):
            # F&O == Derivatives -> 'D'
            return seg_code == "D"
        if seg.endswith("E"):
            return seg_code == "E"
        if seg.endswith("C"):
            return seg_code == "C"
        if seg.endswith("M"):
            return seg_code == "M"
        # if not specified further, just exchange match is fine
        return True

    # If nothing matched, fall back to exchange match
    return exch == seg


def get_instruments_by_segment(segment: str, detailed: bool = True, ttl: int = _DEFAULT_TTL) -> list[dict]:
    """
    Compatibility helper required by routers.
    Returns rows filtered by the provided `segment`.
    Examples: "NSE", "BSE", "MCX", "NSEFO", "NSE-D", "BSE-E"
    """
    rows = get_instruments_csv(detailed=detailed, ttl=ttl)
    if not segment:
        return rows
    segment = _norm(segment)
    return [r for r in rows if _match_segment(r, segment)]


# Backwards-compatible alias some modules might import:
# (Your router import was failing due to this missing symbol)
get_instruments = get_instruments_csv  # alias to maintain older imports


def search_instruments(
    query: str,
    segment: str | None = None,
    detailed: bool = True,
    limit: int = 50,
    ttl: int = _DEFAULT_TTL,
) -> list[dict]:
    """
    Case-insensitive substring search over common symbol/name fields.
    Optionally restrict to a segment (e.g. 'NSE', 'NSEFO', 'BSE-E', etc.)
    """
    q = _norm(query)
    rows = get_instruments_by_segment(segment, detailed=detailed, ttl=ttl) if segment else get_instruments_csv(detailed=detailed, ttl=ttl)

    fields = [
        "SYMBOL_NAME", "SM_SYMBOL_NAME",
        "SEM_TRADING_SYMBOL", "DISPLAY_NAME", "SEM_CUSTOM_SYMBOL",
        "UNDERLYING_SYMBOL", "UNDERLYING_SECURITY_ID"
    ]

    out: list[dict] = []
    for r in rows:
        for f in fields:
            v = _norm(r.get(f, ""))
            if q in v:
                out.append(r)
                break
        if len(out) >= limit:
            break
    return out
