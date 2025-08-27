from fastapi import APIRouter, Query
from typing import Dict, Any
from datetime import datetime
import random
from App.common import dhan_get, logger

router = APIRouter(prefix="/marketfeed", tags=["marketfeed"])

def _mock_ltp() -> float:
    return round(1600 + random.random()*80, 2)

@router.get("/ltp")
def ltp(exchange_segment: str = Query(...), security_id: int = Query(...)):
    try:
        j = dhan_get("/market-quote/ltp", {"exchange_segment": exchange_segment, "security_id": security_id})
        ltp_val = None
        if isinstance(j, dict):
            ltp_val = j.get("ltp") or j.get("LTP") or j.get("last_price")
        if ltp_val is None: ltp_val = _mock_ltp()
        return {"data": {"data": {f"{exchange_segment}_EQ": [{"ltp": float(ltp_val)}]}}}
    except Exception as e:
        logger.warning(f"ltp mock due to: {e}")
        return {"data": {"data": {f"{exchange_segment}_EQ": [{"ltp": _mock_ltp()}]}}}

@router.get("/quote")
def quote(exchange_segment: str = Query(...), security_id: int = Query(...)):
    try:
        j = dhan_get("/market-quote", {"exchange_segment": exchange_segment, "security_id": security_id})
        return {"data": {
            "last_price": j.get("last_price") or j.get("ltp"),
            "best_bid": j.get("best_bid") or j.get("bid"),
            "best_ask": j.get("best_ask") or j.get("ask"),
            "volume":   j.get("volume") or j.get("total_traded_volume"),
        }}
    except Exception as e:
        logger.warning(f"quote mock due to: {e}")
        lp = _mock_ltp()
        return {"data": {"last_price": lp, "best_bid": lp-0.5, "best_ask": lp+0.5, "volume": 123456}}

@router.get("/depth")
def depth(exchange_segment: str = Query(...), security_id: int = Query(...), levels: int = Query(5, ge=1, le=10)):
    try:
        j = dhan_get("/market-depth", {"exchange_segment": exchange_segment, "security_id": security_id, "levels": levels})
        return {"data": j}
    except Exception as e:
        logger.warning(f"depth mock due to: {e}")
        lp = _mock_ltp()
        book = {
            "bids": [{"price": round(lp - i*0.5,2), "qty": 1000 + i*200} for i in range(1, levels+1)],
            "asks": [{"price": round(lp + i*0.5,2), "qty": 1000 + i*200} for i in range(1, levels+1)],
            "last": lp
        }
        return {"data": book}

@router.get("/livefeed")
def livefeed(exchange_segment: str = Query(...), security_ids: str = Query(...)):
    ids = [s.strip() for s in security_ids.split(",") if s.strip()]
    try:
        j = dhan_get("/market-livefeed", {"exchange_segment": exchange_segment, "security_ids": ",".join(ids)})
        return {"data": j}
    except Exception as e:
        logger.warning(f"livefeed mock due to: {e}")
        return {"data": {sid: {"ltp": _mock_ltp(), "ts": datetime.now().isoformat()} for sid in ids}}
