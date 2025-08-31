# App/Routers/optionchain.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone
import os

from App.Services.dhan_client import get_expiry_list, get_option_chain_raw
from App.Services.greeks import bs_greeks  # <-- new

router = APIRouter(prefix="/optionchain", tags=["Option Chain"])


def _pf(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def _pi(x) -> int:
    try:
        return int(float(x))
    except Exception:
        return 0


def _years_to_expiry(expiry_str: str) -> float:
    """
    Convert 'YYYY-MM-DD' (Dhan format) to time to expiry in years.
    We assume end-of-day UTC for simplicity.
    """
    try:
        exp = datetime.fromisoformat(expiry_str).replace(tzinfo=timezone.utc, hour=23, minute=59, second=59)
    except Exception:
        # fall back: now + small epsilon to avoid 0
        return 1e-6
    now = datetime.now(timezone.utc)
    days = max((exp - now).total_seconds() / 86400.0, 1e-6)
    return days / 365.0


@router.get("/expirylist")
async def expiry_list(under_security_id: int, under_exchange_segment: str):
    expiries = await get_expiry_list(under_security_id, under_exchange_segment)
    return {"status": "success", "data": expiries}


@router.get("")
async def option_chain(
    under_security_id: int,
    under_exchange_segment: str,
    expiry: str,
    show_all: Optional[bool] = False,
    strikes_window: int = Query(15, ge=1, le=50),
    step: int = Query(0, ge=0),  # 0 => auto-detect
):
    # 1) validate expiry with Dhan
    valid = await get_expiry_list(under_security_id, under_exchange_segment)
    if not valid:
        raise HTTPException(502, "No expiries returned from Dhan")
    if expiry not in valid:
        raise HTTPException(400, f"Invalid expiry: {expiry}. Use one of: {', '.join(valid[:6])}…")

    # 2) fetch chain
    raw = await get_option_chain_raw(under_security_id, under_exchange_segment, expiry)
    if not raw or "data" not in raw or "oc" not in raw["data"]:
        raise HTTPException(502, "Empty chain returned from Dhan")

    spot = _pf(raw["data"].get("last_price", 0))
    oc: Dict[str, Any] = raw["data"]["oc"] or {}

    # 3) convert map -> sorted list of strikes
    strikes_sorted: List[float] = sorted(_pf(k) for k in oc.keys() if k is not None)

    # auto-detect step if not provided
    step_used = step
    if step_used <= 0 and len(strikes_sorted) >= 2:
        diffs = sorted(abs(strikes_sorted[i + 1] - strikes_sorted[i]) for i in range(len(strikes_sorted) - 1))
        step_used = int(diffs[0]) if diffs else 100
        if step_used == 0:
            step_used = 100

    # 4) time to expiry & params for greeks
    t_years = _years_to_expiry(expiry)
    R = float(os.getenv("RISK_FREE_RATE", "0.065"))   # 6.5% default
    Q = float(os.getenv("DIVIDEND_YIELD", "0.0"))

    def _to_row(strike_float: float) -> Dict[str, Any]:
        # Dhan keys are strings with 6 decimals; normalize
        key = f"{strike_float:.6f}"
        row = oc.get(key, {}) or {}
        ce = row.get("ce", {}) or {}
        pe = row.get("pe", {}) or {}

        # IVs may arrive as %; keep in same units in payload (%, 2dp),
        # but convert to decimal for greeks.
        ce_iv_pct = _pf(ce.get("implied_volatility", 0))
        pe_iv_pct = _pf(pe.get("implied_volatility", 0))
        iv_for_greeks = 0.0
        if ce_iv_pct and pe_iv_pct:
            iv_for_greeks = 0.5 * (ce_iv_pct + pe_iv_pct) / 100.0
        else:
            iv_for_greeks = (ce_iv_pct or pe_iv_pct) / 100.0

        g = bs_greeks(
            spot=spot,
            strike=strike_float,
            iv=iv_for_greeks,
            t_years=t_years,
            r=R,
            q=Q,
        )

        return {
            "strike": strike_float,
            "call": {
                "oi": _pi(ce.get("oi", 0)),
                "chgOi": _pi(ce.get("oi", 0)) - _pi(ce.get("previous_oi", 0)),
                "iv": round(ce_iv_pct, 2),
                "price": _pf(ce.get("last_price", 0)),
                # greeks
                "delta": round(g["call"]["delta"], 4),
                "gamma": round(g["call"]["gamma"], 6),
                "theta": round(g["call"]["theta"], 2),  # per day
                "vega":  round(g["call"]["vega"], 2),   # per 1 vol pt
            },
            "put": {
                "oi": _pi(pe.get("oi", 0)),
                "chgOi": _pi(pe.get("oi", 0)) - _pi(pe.get("previous_oi", 0)),
                "iv": round(pe_iv_pct, 2),
                "price": _pf(pe.get("last_price", 0)),
                "delta": round(g["put"]["delta"], 4),
                "gamma": round(g["put"]["gamma"], 6),
                "theta": round(g["put"]["theta"], 2),
                "vega":  round(g["put"]["vega"], 2),
            },
        }

    chain_all: List[Dict[str, Any]] = [_to_row(s) for s in strikes_sorted]

    # 5) summary stats
    total_call_oi = sum(x["call"]["oi"] for x in chain_all)
    total_put_oi = sum(x["put"]["oi"] for x in chain_all)
    pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else 0.0
    max_pain_strike = (
        min(chain_all, key=lambda r: abs(r["call"]["oi"] - r["put"]["oi"]))["strike"]
        if chain_all else 0.0
    )

    # 6) windowing
    if show_all or not spot or not strikes_sorted:
        chain_window = chain_all
    else:
        # find ATM and take ±N steps
        atm = min(strikes_sorted, key=lambda s: abs(s - spot))
        lo = atm - strikes_window * step_used
        hi = atm + strikes_window * step_used
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
            "window": f"ATM ± {strikes_window} (step={step_used})",
            "show_all": bool(show_all),
            "greeks": {"theta_unit": "per day", "vega_unit": "per 1 vol pt"},
            "r": R,
            "q": Q,
            "t_years": round(t_years, 6),
        },
    }
