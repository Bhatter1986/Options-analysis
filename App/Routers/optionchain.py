from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from App.Services.dhan_client import get_expiry_list, get_option_chain_raw

router = APIRouter(prefix="/optionchain", tags=["Option Chain"])

@router.get("/expirylist")
def expiry_list(under_security_id: int, under_exchange_segment: str):
    expiries = get_expiry_list(under_security_id, under_exchange_segment)
    return {"status": "success", "data": expiries}

@router.get("")
def option_chain(
    under_security_id: int,
    under_exchange_segment: str,
    expiry: str,
    show_all: Optional[bool] = False,
    strikes_window: int = Query(15, ge=1, le=50), # ATM ± N strikes; default 15
    step: int = Query(100, ge=1)                  # strike step (BankNifty=100, Nifty=50)
):
    """
    Return option chain:
    - Default: ATM ± `strikes_window` strikes
    - `show_all=true` -> full chain
    - Also returns summary: PCR, Max Pain, Total OI, Spot
    """
    raw = get_option_chain_raw(under_security_id, under_exchange_segment, expiry)
    if not raw or "oc" not in raw:
        raise HTTPException(502, "Empty chain returned from Dhan")

    spot: float = float(raw.get("last_price", 0) or 0)
    oc: Dict[str, Any] = raw["oc"]

    # Parse to list
    def _to_row(strike_str: str) -> Dict[str, Any]:
        row = oc.get(strike_str, {})
        ce = row.get("ce", {}) or {}
        pe = row.get("pe", {}) or {}
        return {
            "strike": float(strike_str),
            "call": {
                "oi": int(ce.get("oi", 0) or 0),
                "chgOi": int(ce.get("oi", 0) or 0) - int(ce.get("previous_oi", 0) or 0),
                "iv": float(ce.get("implied_volatility", 0) or 0),
                "price": float(ce.get("last_price", 0) or 0),
            },
            "put": {
                "oi": int(pe.get("oi", 0) or 0),
                "chgOi": int(pe.get("oi", 0) or 0) - int(pe.get("previous_oi", 0) or 0),
                "iv": float(pe.get("implied_volatility", 0) or 0),
                "price": float(pe.get("last_price", 0) or 0),
            },
        }

    strikes_sorted: List[float] = sorted(float(k) for k in oc.keys())
    chain_all: List[Dict[str, Any]] = [_to_row(f"{s:.6f}") for s in strikes_sorted]

    # Summary on FULL chain
    total_call_oi = sum(x["call"]["oi"] for x in chain_all)
    total_put_oi  = sum(x["put"]["oi"]  for x in chain_all)
    pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else 0.0

    # Max Pain (simplified: min |call_oi - put_oi|)
    if chain_all:
        max_pain_strike = min(chain_all, key=lambda r: abs(r["call"]["oi"] - r["put"]["oi"]))["strike"]
    else:
        max_pain_strike = 0.0

    # Filtered window (ATM ± N strikes)
    if show_all or not spot or not strikes_sorted:
        chain_window = chain_all
    else:
        # Pick closest strike to spot
        atm = min(strikes_sorted, key=lambda s: abs(s - spot))
        lo = atm - strikes_window * step
        hi = atm + strikes_window * step
        chain_window = [r for r in chain_all if lo <= r["strike"] <= hi]

    return {
        "status": "success",
        "instrument": under_security_id,
        "segment": under_exchange_segment,
        "expiry": expiry,
        "spot": spot,
        "summary": {
            "pcr": pcr,
            "max_pain": max_pain_strike,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
        },
        "chain": chain_window,
        "meta": {
            "count_window": len(chain_window),
            "count_full": len(chain_all),
            "window": f"ATM ± {strikes_window} (step={step})",
            "show_all": bool(show_all),
        }
    }
