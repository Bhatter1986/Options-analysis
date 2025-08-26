from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any
import os, logging, requests, random
from datetime import datetime

router = APIRouter(prefix="/marketfeed", tags=["marketfeed"])
log = logging.getLogger("marketfeed")

MODE = os.getenv("MODE","SANDBOX").upper()
DHAN_BASE_URL = "https://api.dhan.co" if MODE == "LIVE" else "https://api-sandbox.dhan.co"
DHAN_API_BASE = f"{DHAN_BASE_URL}/api/v2"
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID","")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN","")

def _headers():
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail="Dhan credentials not configured")
    return {"access-token": DHAN_ACCESS_TOKEN, "client-id": DHAN_CLIENT_ID, "Accept":"application/json","Content-Type":"application/json"}

def _safe_json(r: requests.Response) -> Any:
    try:
        r.raise_for_status()
        return r.json()
    except Exception:
        try: detail = r.json()
        except Exception: detail = r.text
        raise HTTPException(status_code=r.status_code if hasattr(r,'status_code') else 500, detail=detail)

def _mock_ltp() -> float:
    return round(1600 + random.random()*80, 2)

@router.get("/ltp")
def ltp(exchange_segment: str = Query(...), security_id: int = Query(...)):
    if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
        try:
            url = f"{DHAN_API_BASE}/market-quote/ltp"
            j = _safe_json(requests.get(url, headers=_headers(), params={
                "exchange_segment": exchange_segment, "security_id": security_id
            }, timeout=10))
            ltp_val = j.get("ltp") or j.get("LTP") or j.get("last_price") if isinstance(j, dict) else None
            if ltp_val is None: ltp_val = _mock_ltp()
            return {"data": {"data": {f"{exchange_segment}_EQ": [{"ltp": float(ltp_val)}]}}}
        except Exception as e:
            log.warning(f"ltp fallback→mock: {e}")
    return {"data": {"data": {f"{exchange_segment}_EQ": [{"ltp": _mock_ltp()}]}}}

@router.get("/quote")
def quote(exchange_segment: str = Query(...), security_id: int = Query(...)):
    if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
        try:
            url = f"{DHAN_API_BASE}/market-quote"
            j = _safe_json(requests.get(url, headers=_headers(), params={
                "exchange_segment": exchange_segment, "security_id": security_id
            }, timeout=10))
            data = {
                "last_price": j.get("last_price") or j.get("ltp"),
                "best_bid": j.get("best_bid") or j.get("bid"),
                "best_ask": j.get("best_ask") or j.get("ask"),
                "volume": j.get("volume") or j.get("total_traded_volume"),
            }
            return {"data": data}
        except Exception as e:
            log.warning(f"quote fallback→mock: {e}")
    return {"data": {"last_price": _mock_ltp(), "best_bid": _mock_ltp()-0.5, "best_ask": _mock_ltp()+0.5, "volume": 123456}}

@router.get("/depth")
def depth(exchange_segment: str = Query(...), security_id: int = Query(...), levels: int = Query(5, ge=1, le=10)):
    if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
        try:
            url = f"{DHAN_API_BASE}/market-depth"
            j = _safe_json(requests.get(url, headers=_headers(), params={
                "exchange_segment": exchange_segment, "security_id": security_id, "levels": levels
            }, timeout=10))
            return {"data": j}
        except Exception as e:
            log.warning(f"depth fallback→mock: {e}")
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
    if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
        try:
            url = f"{DHAN_API_BASE}/market-livefeed"
            j = _safe_json(requests.get(url, headers=_headers(), params={
                "exchange_segment": exchange_segment, "security_ids": ",".join(ids)
            }, timeout=12))
            return {"data": j}
        except Exception as e:
            log.warning(f"livefeed fallback→mock: {e}")
    return {"data": {sid: {"ltp": _mock_ltp(), "ts": datetime.now().isoformat()} for sid in ids}}
