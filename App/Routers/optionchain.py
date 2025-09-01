from __future__ import annotations
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from App.Services.dhan_client import get_expiry_list, get_option_chain_raw

import math
from datetime import datetime

router = APIRouter(prefix="/optionchain", tags=["Option Chain"])

# --- Math helpers ---
def _d1(S, K, T, r, sigma):
    return (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))

def _d2(d1, sigma, T):
    return d1 - sigma * math.sqrt(T)

def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def _norm_pdf(x):
    return (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x * x)

def safe_round(val: float, ndigits: int) -> float:
    try:
        if val is None or math.isnan(val) or math.isinf(val):
            return 0.0
        return round(val, ndigits)
    except Exception:
        return 0.0

# --- Black–Scholes Greeks ---
def compute_greeks(S: float, K: float, T: float, r: float, sigma: float, opt_type: str) -> Dict[str, float]:
    """Return dict with delta,gamma,theta,vega for call/put using Black–Scholes."""
    if sigma <= 0 or T <= 0 or S <= 0 or K <= 0:
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0}

    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(d1, sigma, T)
    pdf, cdf_d1, cdf_d2 = _norm_pdf(d1), _norm_cdf(d1), _norm_cdf(d2)

    if opt_type == "call":
        delta = cdf_d1
        theta = -(S * pdf * sigma / (2 * math.sqrt(T))) - r * K * math.exp(-r * T) * cdf_d2
    else:  # put
        delta = cdf_d1 - 1
        theta = -(S * pdf * sigma / (2 * math.sqrt(T))) + r * K * math.exp(-r * T) * (1 - cdf_d2)

    gamma = pdf / (S * sigma * math.sqrt(T))
    vega = S * pdf * math.sqrt(T)

    # Normalize units
    theta = theta / 365.0      # per day
    vega = vega / 100.0        # per 1% change in IV

    return {
        "delta": safe_round(delta, 4),
        "gamma": safe_round(gamma, 6),
        "theta": safe_round(theta, 4),
        "vega": safe_round(vega, 4),
    }

# ---------------------------

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
    step: int = Query(100, ge=1),
):
    # --- Validate expiry ---
    valid = await get_expiry_list(under_security_id, under_exchange_segment)
    if not valid:
        raise HTTPException(502, "No expiries returned from Dhan")
    if expiry not in valid:
        raise HTTPException(400, f"Invalid expiry: {expiry}. Use one of: {', '.join(valid[:6])}…")

    # --- Fetch chain ---
    raw = await get_option_chain_raw(under_security_id, under_exchange_segment, expiry)
    if not raw or "data" not in raw or "oc" not in raw["data"]:
        raise HTTPException(502, "Empty chain returned from Dhan")

    spot = float(raw["data"].get("last_price") or 0.0)
    oc: Dict[str, Any] = raw["data"]["oc"]

    # --- Time-to-expiry in years ---
    try:
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d")
        except ValueError:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
        days = max((exp_date - datetime.utcnow()).days, 0) + 1
        T = days / 365.0
    except Exception:
        T = 0.05  # fallback ~18 days

    r = 0.06  # risk free rate ~6%

    # --- Format row ---
    def _to_row(strike_str: str) -> Dict[str, Any]:
        row = oc.get(strike_str, {}) or {}
        ce = row.get("ce", {}) or {}
        pe = row.get("pe", {}) or {}

        K = float(strike_str)
        sigma_c = float(ce.get("implied_volatility") or 0.0) / 100.0
        sigma_p = float(pe.get("implied_volatility") or 0.0) / 100.0

        greeks_call = compute_greeks(spot, K, T, r, sigma_c, "call") if sigma_c > 0 else {}
        greeks_put  = compute_greeks(spot, K, T, r, sigma_p, "put")  if sigma_p > 0 else {}

        call_oi = max(0, int(ce.get("oi", 0) or 0))
        put_oi  = max(0, int(pe.get("oi", 0) or 0))

        return {
            "strike": K,
            "call": {
                "oi": call_oi,
                "chgOi": call_oi - int(ce.get("previous_oi", 0) or 0),
                "iv": float(ce.get("implied_volatility") or 0.0),
                "price": float(ce.get("last_price") or 0.0),
                **greeks_call,
            },
            "put": {
                "oi": put_oi,
                "chgOi": put_oi - int(pe.get("previous_oi", 0) or 0),
                "iv": float(pe.get("implied_volatility") or 0.0),
                "price": float(pe.get("last_price") or 0.0),
                **greeks_put,
            },
        }

    # --- Build chain ---
    strikes_sorted: List[float] = sorted(float(k) for k in oc.keys())
    chain_all: List[Dict[str, Any]] = [_to_row(f"{s:.6f}") for s in strikes_sorted]

    total_call_oi = sum(x["call"]["oi"] for x in chain_all)
    total_put_oi  = sum(x["put"]["oi"] for x in chain_all)
    pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else 0.0
    max_pain_strike = min(chain_all, key=lambda r: abs(r["call"]["oi"] - r["put"]["oi"]))["strike"] if chain_all else 0.0

    # --- Window selection ---
    if show_all or not spot or not strikes_sorted:
        chain_window = chain_all
    else:
        step_used = step or (50 if len(strikes_sorted) > 1 and (strikes_sorted[1] - strikes_sorted[0] <= 50) else 100)
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
            "window": f"ATM ± {strikes_window} (step={step})",
            "show_all": bool(show_all),
        },
    }
