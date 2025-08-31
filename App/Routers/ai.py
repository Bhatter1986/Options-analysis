# App/Routers/ai.py
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from App.Services.dhan_client import get_option_chain_raw
from App.Services.ai_vishnu import analyze

router = APIRouter(prefix="/ai", tags=["AI / Vishnu"])

@router.get("/analyze")
def ai_analyze(
    under_security_id: int,
    under_exchange_segment: str,
    expiry: str,
    strikes_window: int = Query(15, ge=1, le=50),
    step: Optional[int] = Query(None, ge=1),
    show_all: bool = False,
):
    """
    Combine Dhan option chain + Vishnu rules → AI advice
    """
    raw = get_option_chain_raw(under_security_id, under_exchange_segment, expiry)
    if not raw or "oc" not in raw:
        raise HTTPException(502, "Empty chain from Dhan")

    spot = float(raw.get("last_price", 0) or 0)
    oc = raw["oc"]

    # Convert raw oc → list of rows (same shape your /optionchain returns)
    def _row(strike: float):
        s = f"{strike:.6f}"
        node = oc.get(s, {}) or {}
        ce = node.get("ce", {}) or {}
        pe = node.get("pe", {}) or {}
        return {
            "strike": strike,
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

    strikes = sorted(float(k) for k in oc.keys())
    chain_all = [_row(s) for s in strikes]

    # Windowing like /optionchain (ATM ± N * step)
    if show_all or not spot or not strikes:
        chain_window = chain_all
    else:
        # infer step if missing
        step_val = step or (100 if (max(strikes) - min(strikes)) > 2000 else 50)
        atm = min(strikes, key=lambda s: abs(s - spot))
        lo = atm - strikes_window * step_val
        hi = atm + strikes_window * step_val
        chain_window = [r for r in chain_all if lo <= r["strike"] <= hi]

    payload = {
        "spot": spot,
        "chain": chain_window,
        "meta": {"count_full": len(chain_all)},
    }

    result = analyze(payload, step_hint=step)
    return {
        "status": "success",
        "instrument": under_security_id,
        "segment": under_exchange_segment,
        "expiry": expiry,
        "ai": result,
    }
