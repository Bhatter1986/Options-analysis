# App/Services/ai_vishnu.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple

Number = float | int

def _round_to_step(x: Number, step: int) -> float:
    if step <= 0:
        step = 50
    return round(float(x) / step) * step

def _infer_step(strikes: List[float]) -> int:
    if len(strikes) < 2:
        return 50
    diffs = sorted(set(round(abs(b - a)) for a, b in zip(strikes, strikes[1:])))
    # common Indian steps
    for s in (50, 100, 10, 5):
        if s in diffs:
            return s
    return diffs[0] if diffs and diffs[0] > 0 else 50

def _calc_pcr_total(chain_all: List[Dict[str, Any]]) -> float:
    call_oi = sum(r["call"]["oi"] for r in chain_all)
    put_oi  = sum(r["put"]["oi"]  for r in chain_all)
    return round((put_oi / call_oi), 2) if call_oi else 0.0

def _max_pain(chain_all: List[Dict[str, Any]]) -> float:
    if not chain_all:
        return 0.0
    row = min(chain_all, key=lambda r: abs(r["call"]["oi"] - r["put"]["oi"]))
    return float(row["strike"])

def _atm_bucket(chain_all: List[Dict[str, Any]], spot: float, step: int, width_steps: int = 2
               ) -> Tuple[List[Dict[str, Any]], float]:
    if not chain_all:
        return [], 0.0
    strikes = [r["strike"] for r in chain_all]
    step = step or _infer_step(strikes)
    atm = _round_to_step(spot, step)
    lo = atm - width_steps * step
    hi = atm + width_steps * step
    bucket = [r for r in chain_all if lo <= r["strike"] <= hi]
    return bucket, atm

def analyze(raw: Dict[str, Any], step_hint: int | None = None) -> Dict[str, Any]:
    """
    Phase-1 rules engine:
    - Features: PCR, MaxPain, ATM OI build-up, IV skew
    - Decision: Bias (Bullish/Bearish/Neutral), simple strike suggestion
    """
    data = raw or {}
    spot = float(data.get("spot") or data.get("last_price") or 0.0)
    chain: List[Dict[str, Any]] = data.get("chain") or []

    # If chain passed in is windowed, try to also accept full chain meta
    full_count = data.get("meta", {}).get("count_full", len(chain))

    # Step
    strikes = [r["strike"] for r in chain]
    step = step_hint or _infer_step(strikes)

    # Features
    pcr = _calc_pcr_total(chain)
    max_pain = _max_pain(chain)
    atm_bucket, atm_strike = _atm_bucket(chain, spot, step, width_steps=2)

    # ATM change OI (build-up)
    call_chg_atm = sum(r["call"].get("chgOi", 0) for r in atm_bucket)
    put_chg_atm  = sum(r["put"].get("chgOi", 0) for r in atm_bucket)

    # IV skew near ATM (avg)
    def _avg(xs: List[float]) -> float:
        return round(sum(xs)/len(xs), 2) if xs else 0.0
    ce_iv_avg = _avg([float(r["call"].get("iv", 0) or 0) for r in atm_bucket])
    pe_iv_avg = _avg([float(r["put"].get("iv", 0) or 0) for r in atm_bucket])
    iv_skew = round(pe_iv_avg - ce_iv_avg, 2)  # +ve => puts costlier (downside fear)

    # Simple rules for bias
    bias = "Neutral"
    reasons: List[str] = []

    # Rule 1: PCR
    if pcr >= 1.2:
        bias = "Bullish"
        reasons.append(f"High PCR {pcr} (put OI > call OI)")
    elif pcr <= 0.8 and pcr > 0:
        bias = "Bearish"
        reasons.append(f"Low PCR {pcr} (call OI > put OI)")
    else:
        reasons.append(f"Neutral PCR {pcr}")

    # Rule 2: ATM change OI
    if put_chg_atm > call_chg_atm * 1.3:
        # strong put writing near ATM
        if bias == "Bearish":
            reasons.append("BUT strong PUT build-up near ATM → offsets bearishness")
            bias = "Neutral"
        else:
            reasons.append("Strong PUT build-up near ATM → bullish support")
            bias = "Bullish"
    elif call_chg_atm > put_chg_atm * 1.3:
        if bias == "Bullish":
            reasons.append("BUT strong CALL build-up near ATM → caps upside")
            bias = "Neutral"
        else:
            reasons.append("Strong CALL build-up near ATM → bearish pressure")
            bias = "Bearish"
    else:
        reasons.append("Balanced ATM build-up")

    # Rule 3: Spot vs MaxPain distance
    dist = abs(spot - max_pain)
    if dist < 0.75 * step:
        reasons.append("Spot ~ MaxPain → mean-revert/sideways probability high")
        if bias != "Neutral":
            bias = "Neutral"

    # Rule 4: IV skew
    if iv_skew >= 1.0:
        reasons.append(f"PE IV > CE IV by {iv_skew} → downside protection demand")
    elif iv_skew <= -1.0:
        reasons.append(f"CE IV > PE IV by {abs(iv_skew)} → upside chase / calls pricey")

    # Confidence (simple heuristic 0–100)
    conf = 60
    conf += int(min(20, (abs(1 - pcr) * 20)))  # dev from 1
    conf += 10 if "Strong" in " ".join(reasons) else 0
    conf -= 10 if "BUT" in " ".join(reasons) else 0
    if bias == "Neutral":
        conf = max(40, conf - 20)
    conf = max(10, min(conf, 95))

    # Suggest strikes
    # pick the row equal to atm_strike from chain if present
    def _find_row(strike: float) -> Dict[str, Any] | None:
        for r in chain:
            if abs(r["strike"] - strike) < 0.1:
                return r
        return None

    suggestions: List[Dict[str, Any]] = []
    if bias == "Bullish":
        buy_strike = atm_strike  # CE
        row = _find_row(buy_strike) or {}
        ltp = float(row.get("call", {}).get("price", 0) or 0.0)
        sl = round(ltp * 0.7, 2) if ltp else 0.0     # 30% SL
        tgt = round(ltp * 1.6, 2) if ltp else 0.0   # 60% target
        suggestions.append({
            "type": "CE",
            "side": "BUY",
            "strike": buy_strike,
            "entry_price": ltp,
            "stop_loss": sl,
            "target": tgt,
        })
    elif bias == "Bearish":
        buy_strike = atm_strike  # PE
        row = _find_row(buy_strike) or {}
        ltp = float(row.get("put", {}).get("price", 0) or 0.0)
        sl = round(ltp * 0.7, 2) if ltp else 0.0
        tgt = round(ltp * 1.6, 2) if ltp else 0.0
        suggestions.append({
            "type": "PE",
            "side": "BUY",
            "strike": buy_strike,
            "entry_price": ltp,
            "stop_loss": sl,
            "target": tgt,
        })
    else:
        # Neutral → credit spreads idea (placeholder)
        suggestions.append({
            "type": "SPREAD",
            "side": "SELL",
            "strike": atm_strike,
            "note": "Neutral bias → consider short strangle/iron fly with risk control",
        })

    features = {
        "spot": round(spot, 2),
        "step": step,
        "atm_strike": atm_strike,
        "pcr": pcr,
        "max_pain": max_pain,
        "atm_call_chg_oi": int(call_chg_atm),
        "atm_put_chg_oi": int(put_chg_atm),
        "ce_iv_avg": ce_iv_avg,
        "pe_iv_avg": pe_iv_avg,
        "iv_skew": iv_skew,
        "universe_count": full_count,
    }

    return {
        "ok": True,
        "bias": bias,
        "confidence": conf,
        "features": features,
        "reasons": reasons,
        "suggestions": suggestions,
    }
