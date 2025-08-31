from __future__ import annotations

import csv
import os
import time
from pathlib import Path
from typing import List, Dict
import requests

# ENV
MASTER_URL = os.getenv("DHAN_INSTRUMENTS_CSV_URL", "").strip()
CACHE_PATH = Path(os.getenv("DHAN_INSTRUMENTS_CACHE", "data/dhan_master_cache.csv"))

# How long to re-use cache (seconds). 10 mins is plenty.
CACHE_TTL = int(os.getenv("DHAN_INSTRUMENTS_CACHE_TTL", "600"))


def _ensure_cached() -> Path:
    """
    Download CSV to CACHE_PATH if cache is missing or stale.
    """
    if not MASTER_URL:
        raise RuntimeError("DHAN_INSTRUMENTS_CSV_URL not set")

    # Use cache if fresh
    if CACHE_PATH.exists():
        age = time.time() - CACHE_PATH.stat().st_mtime
        if age < CACHE_TTL and CACHE_PATH.stat().st_size > 0:
            return CACHE_PATH

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(MASTER_URL, timeout=60)
    resp.raise_for_status()
    CACHE_PATH.write_bytes(resp.content)
    return CACHE_PATH


def _step_for_segment(seg: str) -> int:
    """
    Reasonable default tick step by segment.
    """
    seg = (seg or "").upper().strip()
    if seg in ("IDX_I", "NSE_I", "IDX_FO"):
        return 50
    if seg in ("BANKNIFTY", "FINNIFTY"):  # safeguard if names leak in segment
        return 100
    return 10  # equities default


def _compact_row(row: Dict[str, str]) -> Dict[str, str | int]:
    """
    Convert Dhan master CSV row → minimal fields our UI needs.
    Dhan master columns (superset) me 'security_id', 'name', 'exchange_segment' present hote hain.
    """
    # Try common headers with fallbacks
    sid = row.get("security_id") or row.get("securityId") or row.get("id") or ""
    name = row.get("name") or row.get("tradingsymbol") or row.get("symbol") or ""
    seg  = row.get("exchange_segment") or row.get("segment") or ""

    sid = str(sid).strip()
    name = str(name).strip()
    seg  = str(seg).strip().upper()

    if not sid or not name or not seg:
        # skip incomplete lines
        return {}

    # numeric id
    try:
        _id = int(sid)
    except Exception:
        return {}

    return {
        "id": _id,
        "name": name,
        "segment": seg,
        "step": _step_for_segment(seg),
    }


def load_dhan_master() -> List[Dict[str, str | int]]:
    """
    Return compact list for all supported rows.
    """
    path = _ensure_cached()
    out: List[Dict[str, str | int]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item = _compact_row(row)
            if item:
                out.append(item)
    # Deduplicate by id (keep first)
    seen = set()
    uniq: List[Dict[str, str | int]] = []
    for x in out:
        if x["id"] in seen:
            continue
        seen.add(x["id"])
        uniq.append(x)
    return uniq


def search_dhan_master(q: str) -> List[Dict[str, str | int]]:
    ql = (q or "").lower().strip()
    if not ql:
        return []
    data = load_dhan_master()
    return [x for x in data if ql in x["name"].lower()]
