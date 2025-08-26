from fastapi import APIRouter, Query
from typing import Optional, Dict, Any, List
from pathlib import Path
import csv, time, requests, os, logging

router = APIRouter(prefix="", tags=["instruments"])
log = logging.getLogger("instruments")

INSTRUMENTS_URL      = os.getenv("INSTRUMENTS_URL", "https://images.dhan.co/api-data/api-script-master-detailed.csv")
INSTRUMENTS_CACHE    = Path("/tmp/instruments.csv")
INSTRUMENTS_CACHE_TT = int(os.getenv("INSTRUMENTS_TTL_SEC", "86400"))

def _download_if_stale() -> Path:
    if INSTRUMENTS_CACHE.exists():
        age = time.time() - INSTRUMENTS_CACHE.stat().st_mtime
        if age < INSTRUMENTS_CACHE_TT:
            return INSTRUMENTS_CACHE
    log.info(f"Downloading instruments: {INSTRUMENTS_URL}")
    r = requests.get(INSTRUMENTS_URL, timeout=30)
    r.raise_for_status()
    INSTRUMENTS_CACHE.write_bytes(r.content)
    return INSTRUMENTS_CACHE

@router.get("/instruments")
def instruments(q: str = Query("", description="search symbol/name"),
                exchange_segment: Optional[str] = Query(None),
                security_id: Optional[str] = Query(None),
                limit: int = Query(50, ge=1, le=500)):
    path = _download_if_stale()
    out: List[Dict[str, Any]] = []
    qq = q.strip().lower()
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if exchange_segment and str(row.get("exchange_segment","")).upper() != exchange_segment.upper():
                continue
            if security_id and str(row.get("security_id","")) != str(security_id):
                continue
            if qq:
                hay = " ".join([str(row.get("symbol","")), str(row.get("trading_symbol","")), str(row.get("name",""))]).lower()
                if qq not in hay:
                    continue
            out.append({
                "security_id": row.get("security_id"),
                "symbol": row.get("symbol"),
                "trading_symbol": row.get("trading_symbol"),
                "exchange_segment": row.get("exchange_segment"),
                "instrument_type": row.get("instrument_type"),
                "lot_size": row.get("lot_size"),
                "tick_size": row.get("tick_size"),
            })
            if len(out) >= limit: break
    return {"data": out, "count": len(out)}
