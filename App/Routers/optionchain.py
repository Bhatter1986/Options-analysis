from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, List
from datetime import datetime, timedelta
import os, logging, requests, random

router = APIRouter(prefix="", tags=["optionchain"])
log = logging.getLogger("optionchain")

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

def _mock_expiries() -> List[str]:
    base = datetime.now().date()
    return [(base + timedelta(days=7*i)).strftime("%Y-%m-%d") for i in range(1,5)]

def _mock_chain() -> Dict[str, Any]:
    strikes = [24800, 24900, 25000, 25100, 25200]
    data = {}
    for sp in strikes:
        data[str(sp)] = {
            "CE": {"oi": random.randint(8000,22000),"previous_oi": random.randint(7000,21000),
                   "volume": random.randint(1500,7000),"implied_volatility": round(15+random.random()*6,2),
                   "last_price": round(90+random.random()*60,2),"change": round(-3+random.random()*6,2)},
            "PE": {"oi": random.randint(8000,22000),"previous_oi": random.randint(7000,21000),
                   "volume": random.randint(1500,7000),"implied_volatility": round(15+random.random()*6,2),
                   "last_price": round(90+random.random()*60,2),"change": round(-3+random.random()*6,2)}
        }
    return data

@router.get("/optionchain/expirylist")
def expirylist(under_security_id: int = Query(...), under_exchange_segment: str = Query(...)):
    if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
        try:
            url = f"{DHAN_API_BASE}/option-chain/expiry-list"
            j = _safe_json(requests.get(url, headers=_headers(), params={
                "under_security_id": under_security_id,
                "under_exchange_segment": under_exchange_segment
            }, timeout=10))
            return {"data": {"data": j}}
        except Exception as e:
            log.warning(f"expirylist fallback to mock: {e}")
    return {"data": {"data": _mock_expiries()}}

def _optionchain_common(under_security_id: int, under_exchange_segment: str, expiry: str):
    if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
        try:
            url = f"{DHAN_API_BASE}/option-chain"
            j = _safe_json(requests.post(url, headers=_headers(), json={
                "under_security_id": under_security_id,
                "under_exchange_segment": under_exchange_segment,
                "expiry": expiry
            }, timeout=15))
            return {"data": {"data": j}}
        except Exception as e:
            log.warning(f"optionchain fallback to mock: {e}")
    return {"data": {"data": _mock_chain()}}

@router.get("/optionchain")
def optionchain_get(under_security_id: int = Query(...), under_exchange_segment: str = Query(...), expiry: str = Query(...)):
    return _optionchain_common(under_security_id, under_exchange_segment, expiry)

@router.post("/optionchain")
def optionchain_post(payload: Dict[str, Any] = Body(...)):
    return _optionchain_common(int(payload.get("under_security_id")), str(payload.get("under_exchange_segment")), str(payload.get("expiry")))
