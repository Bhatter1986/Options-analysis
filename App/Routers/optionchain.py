from fastapi import APIRouter, Query, Body
from typing import Any, Dict
from datetime import datetime, timedelta
import random
from App.common import dhan_get, dhan_post, logger

router = APIRouter(prefix="/optionchain", tags=["optionchain"])

def _mock_expiries():
    base = datetime.now().date()
    return [(base + timedelta(days=7*i)).strftime("%Y-%m-%d") for i in range(1,5)]

def _mock_chain():
    strikes = [24800, 24900, 25000, 25100, 25200]
    data = {}
    for sp in strikes:
        data[str(sp)] = {
            "CE": {
                "oi": random.randint(8000,22000),
                "previous_oi": random.randint(7000,21000),
                "volume": random.randint(1500,7000),
                "implied_volatility": round(15+random.random()*6,2),
                "last_price": round(90+random.random()*60,2),
                "change": round(-3+random.random()*6,2),
            },
            "PE": {
                "oi": random.randint(8000,22000),
                "previous_oi": random.randint(7000,21000),
                "volume": random.randint(1500,7000),
                "implied_volatility": round(15+random.random()*6,2),
                "last_price": round(90+random.random()*60,2),
                "change": round(-3+random.random()*6,2),
            }
        }
    return data

@router.get("/expirylist")
def expirylist(under_security_id: int = Query(...), under_exchange_segment: str = Query(...)):
    try:
        j = dhan_get("/option-chain/expiry-list", {
            "under_security_id": under_security_id,
            "under_exchange_segment": under_exchange_segment
        })
        return {"data": {"data": j}}
    except Exception as e:
        logger.warning(f"expirylist mock due to: {e}")
        return {"data": {"data": _mock_expiries()}}

def _chain_common(under_security_id: int, under_exchange_segment: str, expiry: str):
    try:
        j = dhan_post("/option-chain", {
            "under_security_id": under_security_id,
            "under_exchange_segment": under_exchange_segment,
            "expiry": expiry
        })
        return {"data": {"data": j}}
    except Exception as e:
        logger.warning(f"optionchain mock due to: {e}")
        return {"data": {"data": _mock_chain()}}

@router.post("")
def optionchain_post(payload: Dict[str, Any] = Body(...)):
    return _chain_common(int(payload.get("under_security_id")), str(payload.get("under_exchange_segment")), str(payload.get("expiry")))

@router.get("")
def optionchain_get(under_security_id: int = Query(...), under_exchange_segment: str = Query(...), expiry: str = Query(...)):
    return _chain_common(under_security_id, under_exchange_segment, expiry)
