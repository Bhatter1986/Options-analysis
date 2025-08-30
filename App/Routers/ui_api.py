# App/Routers/ui_api.py
from __future__ import annotations

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query
import httpx
import os

router = APIRouter(prefix="/ui/api", tags=["ui-api"])

# internal base to call our own service routes
INTERNAL_BASE = os.getenv("INTERNAL_BASE_URL", "http://127.0.0.1:8000")

async def _get_json(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{INTERNAL_BASE}{path}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

@router.get("/expiry-dates")
async def ui_expiry_dates(
    under_security_id: int = Query(..., description="e.g. 25=BANKNIFTY, 2=NIFTY"),
    under_exchange_segment: str = Query("IDX_I"),
) -> List[str]:
    """
    Thin wrapper over /optionchain/expirylist that returns just a list[str] of dates.
    """
    data = await _get_json(
        "/optionchain/expirylist",
        {
            "under_security_id": under_security_id,
            "under_exchange_segment": under_exchange_segment,
        },
    )
    # expected shape: {"data": ["YYYY-MM-DD", ...], "status":"success"}
    return data.get("data", [])

@router.get("/option-chain")
async def ui_option_chain(
    expiry: str = Query(..., description="YYYY-MM-DD"),
    under_security_id: int = Query(..., description="e.g. 25=BANKNIFTY, 2=NIFTY"),
    under_exchange_segment: str = Query("IDX_I"),
) -> Dict[str, Any]:
    """
    Wrapper over /optionchain that transforms 'oc' dict to a friendly list for the dashboard table.
    """
    raw = await _get_json(
        "/optionchain",
        {
            "under_security_id": under_security_id,
            "under_exchange_segment": under_exchange_segment,
            "expiry": expiry,
        },
    )
    # raw expected:
    # {"data": {"last_price": float, "oc": { "25500.000000": {"ce": {...}, "pe": {...}}, ... }}, "status":"success"}

    out: Dict[str, Any] = {"last_price": None, "rows": []}
    d = raw.get("data", {})
    out["last_price"] = d.get("last_price")

    oc: Dict[str, Any] = d.get("oc", {}) or {}
    # Transform to list sorted by strike
    def _as_float(x: Optional[str | float]) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    for strike_str, legs in oc.items():
        strike = _as_float(strike_str)
        ce = legs.get("ce", {}) or {}
        pe = legs.get("pe", {}) or {}

        row = {
            "strike": strike,
            "call": {
                "price": ce.get("last_price", 0) or 0,
                "oi": ce.get("oi", 0) or 0,
                "changeOi": (ce.get("oi", 0) or 0) - (ce.get("previous_oi", 0) or 0),
                "iv": ce.get("implied_volatility", 0),
            },
            "put": {
                "price": pe.get("last_price", 0) or 0,
                "oi": pe.get("oi", 0) or 0,
                "changeOi": (pe.get("oi", 0) or 0) - (pe.get("previous_oi", 0) or 0),
                "iv": pe.get("implied_volatility", 0),
            },
        }
        out["rows"].append(row)

    # sort by strike
    out["rows"].sort(key=lambda r: r["strike"])
    return out
