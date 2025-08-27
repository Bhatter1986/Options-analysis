import os, csv, time
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
import requests
from App.common import logger

router = APIRouter(prefix="/instruments", tags=["instruments"])

INSTRUMENTS_URL       = os.getenv("INSTRUMENTS_URL", "https://images.dhan.co/api-data/api-script-master-detailed.csv")
INSTRUMENTS_CACHE     = Path("/tmp/instruments.csv")
INSTRUMENTS_TTL_SEC   = int(os.getenv("INSTRUMENTS_TTL_SEC", "86400"))
LOCAL_FALLBACK_PATH   = Path("data/instruments.csv")  # optional local

def _download_to_cache() -> Path:
    logger.info(f"Downloading instruments: {INSTRUMENTS_URL}")
    r = requests.get(INSTRUMENTS_URL, timeout=30)
    r.raise_for_status()
    INSTRUMENTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    INSTRUMENTS_CACHE.write_bytes(r.content)
    logger.info(f"Saved instruments to {INSTRUMENTS_CACHE} ({len(r.content)} bytes)")
    return INSTRUMENTS_CACHE

def _ensure_csv_path(force: bool = False) -> Path:
    # prefer /tmp cache (fresh), else local fallback, else download
    if force and INSTRUMENTS_CACHE.exists():
        try: INSTRUMENTS_CACHE.unlink()
        except Exception: pass
    if INSTRUMENTS_CACHE.exists():
        age = time.time() - INSTRUMENTS_CACHE.stat().st_mtime
        if age < INSTRUMENTS_TTL_SEC:
            return INSTRUMENTS_CACHE
    if LOCAL_FALLBACK_PATH.exists():
        # copy once into cache to keep a single path source
        try:
            data = LOCAL_FALLBACK_PATH.read_bytes()
            INSTRUMENTS_CACHE.write_bytes(data)
            logger.info(f"Copied local data/instruments.csv → {INSTRUMENTS_CACHE}")
            return INSTRUMENTS_CACHE
        except Exception as e:
            logger.warning(f"Local fallback copy failed: {e}")
    return _download_to_cache()

def _iter_rows(limit: Optional[int] = None,
               q: str = "",
               filter_fn = None) -> List[Dict[str, Any]]:
    path = _ensure_csv_path()
    out: List[Dict[str, Any]] = []
    qq = (q or "").strip().lower()

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if filter_fn and not filter_fn(row):
                continue
            if qq:
                hay = " ".join([
                    str(row.get("symbol_name","")), str(row.get("trading_symbol","")),
                    str(row.get("underlying_symbol","")), str(row.get("name","")),
                    str(row.get("security_id",""))
                ]).lower()
                if qq not in hay:
                    continue
            out.append(row)
            if limit and len(out) >= limit:
                break
    return out

@router.get("/_debug")
def dbg():
    path = None
    exists = INSTRUMENTS_CACHE.exists()
    size = INSTRUMENTS_CACHE.stat().st_size if exists else 0
    rows = 0
    if exists:
        try:
            with INSTRUMENTS_CACHE.open("r", encoding="utf-8") as f:
                rows = sum(1 for _ in f) - 1  # header
        except Exception:
            rows = -1
    return {
        "cache_path": str(INSTRUMENTS_CACHE),
        "exists": exists,
        "size_bytes": size,
        "rows_estimate": rows,
        "ttl_sec": INSTRUMENTS_TTL_SEC,
        "source_url": INSTRUMENTS_URL
    }

@router.post("/_refresh")
def refresh():
    _ensure_csv_path(force=True)
    return {"status": "ok"}

@router.get("")
def list_sample(limit: int = Query(50, ge=1, le=500)):
    rows = _iter_rows(limit=limit)
    return {"count": len(rows), "data": rows}

@router.get("/indices")
def list_indices(q: str = Query("", description="filter text"),
                 limit: int = Query(200, ge=1, le=2000)):
    def is_index(row):
        it = str(row.get("instrument_type","")).upper()
        seg = str(row.get("segment","") or row.get("exchange_segment","")).upper()
        return it in ("INDEX","I") or seg == "I"
    rows = _iter_rows(limit=limit, q=q, filter_fn=is_index)
    # compact fields first
    slim = []
    for r in rows:
        slim.append({
            "security_id": r.get("security_id"),
            "symbol_name": r.get("symbol_name") or r.get("symbol"),
            "underlying_symbol": r.get("underlying_symbol") or r.get("symbol"),
            "segment": r.get("segment") or r.get("exchange_segment"),
            "instrument_type": r.get("instrument_type")
        })
    return {"count": len(slim), "data": slim}

@router.get("/search")
def search(q: str = Query(..., min_length=1),
           limit: int = Query(100, ge=1, le=1000)):
    rows = _iter_rows(limit=limit, q=q)
    return {"count": len(rows), "data": rows}

@router.get("/by-id")
def by_id(security_id: str = Query(...)):
    path = _ensure_csv_path()
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("security_id")) == str(security_id):
                return {"data": row}
    raise HTTPException(status_code=404, detail="Security ID not found")
