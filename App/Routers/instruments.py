import os
import csv
import io
import logging
from typing import List, Optional

import requests
from fastapi import APIRouter, Query

logger = logging.getLogger("instruments")
router = APIRouter(prefix="/instruments", tags=["Instruments"])

# ------------------------------------------------------------
# CSV Source (env override → local fallback)
# ------------------------------------------------------------
CSV_URL = os.getenv("INSTRUMENTS_URL")

if not CSV_URL or CSV_URL.strip() == "":
    CSV_URL = "data/instruments.csv"   # default local file

# Cache in memory
_cache: List[dict] = []


# ------------------------------------------------------------
# Load CSV (from URL or local file)
# ------------------------------------------------------------
def _load_csv_rows() -> List[dict]:
    rows: List[dict] = []
    try:
        if CSV_URL.startswith("http://") or CSV_URL.startswith("https://"):
            r = requests.get(CSV_URL, timeout=30)
            r.raise_for_status()
            text = r.text
            reader = csv.DictReader(io.StringIO(text))
            rows = [row for row in reader]
        else:
            with open(CSV_URL, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = [row for row in reader]
    except Exception as e:
        logger.exception("Failed loading instruments from %s", CSV_URL)
    return rows


def _ensure_cache():
    global _cache
    if not _cache:
        _cache = _load_csv_rows()


# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------

# 1) All indices
@router.get("/indices")
def list_indices(q: Optional[str] = None, limit: int = 50):
    _ensure_cache()
    results = []
    for row in _cache:
        # indices usually have instrument_type = INDEX or FUTIDX/OPTIDX
        inst_type = (row.get("instrument_type") or "").upper()
        if "INDEX" in inst_type:
            if q and q.lower() not in (row.get("trading_symbol") or "").lower():
                continue
            results.append(row)
        if len(results) >= limit:
            break
    return {"count": len(results), "data": results}


# 2) Generic search
@router.get("/search")
def search_instruments(
    q: str,
    exchange_segment: Optional[str] = None,
    limit: int = 50
):
    _ensure_cache()
    results = []
    for row in _cache:
        if q.lower() not in (row.get("trading_symbol") or "").lower():
            continue
        if exchange_segment and exchange_segment.upper() != (row.get("segment") or "").upper():
            continue
        results.append(row)
        if len(results) >= limit:
            break
    return {"count": len(results), "data": results}


# 3) By ID
@router.get("/by-id")
def get_by_id(security_id: str):
    _ensure_cache()
    for row in _cache:
        if row.get("security_id") == str(security_id):
            return {"data": row}
    return {"detail": "Not Found"}


# 4) Cache refresh
@router.post("/_refresh")
def refresh_cache():
    global _cache
    _cache = _load_csv_rows()
    return {"status": "refreshed", "count": len(_cache)}
