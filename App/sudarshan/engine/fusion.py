# App/sudarshan/engine/fusion.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def _signal_to_num(sig: Optional[str]) -> int:
    """
    Map blade 'signal' to numeric score:
      bullish -> +1
      bearish -> -1
      neutral/unknown/None -> 0
    """
    if not sig:
        return 0
    s = str(sig).strip().lower()
    if s in ("bull", "bullish", "up", "long"):
        return 1
    if s in ("bear", "bearish", "down", "short"):
        return -1
    return 0


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def fuse(
    blades: Dict[str, Dict[str, Any]],
    *,
    weights: Optional[Dict[str, float]] = None,
    min_confirmations: int = 3,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Combine blade outputs into a single verdict.

    Parameters
    ----------
    blades : dict
        Per-blade outputs (price/oi/greeks/volume/sentiment). Each blade ideally returns:
          { "ok": bool, "signal": "bullish|bearish|neutral", "detail": {...} }
    weights : dict | None
        Per-blade weights. Missing blades default to 1.0.
    min_confirmations : int
        Minimum agreeing non-neutral blades required to issue a trade call.

    Returns
    -------
    (scores, verdict)
      scores  : detailed per-blade + aggregate math
      verdict : { "score": float [-1..+1], "confirms": int, "verdict": "buy|sell|pass" }
    """
    weights = (weights or {}).copy()

    # 1) Collect blades present and assign raw weights
    blade_names = list(blades.keys())
    raw_items = []
    for name in blade_names:
        out = blades.get(name) or {}
        sig = out.get("signal")
        num = _signal_to_num(sig)
        w = _safe_float(weights.get(name, 1.0), 1.0)
        raw_items.append(
            {
                "name": name,
                "signal": sig if sig is not None else "neutral",
                "score": num,          # -1, 0, +1
                "weight": w,           # raw (unnormalized)
            }
        )

    # Edge: no blades
    if not raw_items:
        scores = {
            "per_blade": [],
            "sum_weights": 0.0,
            "sum_norm_weights": 0.0,
            "weighted_sum": 0.0,
            "agg": 0.0,
        }
        verdict = {"score": 0.0, "confirms": 0, "verdict": "pass"}
        return scores, verdict

    # 2) Normalize weights to sum=1 (only positive weights considered)
    sum_w = sum(max(0.0, it["weight"]) for it in raw_items)
    if sum_w <= 0.0:
        # If user passed all zeros/negatives, fall back to equal weights = 1
        for it in raw_items:
            it["weight"] = 1.0
        sum_w = float(len(raw_items))

    for it in raw_items:
        it["norm_weight"] = max(0.0, it["weight"]) / sum_w

    # 3) Aggregate (normalized weighted sum in [-1..+1])
    weighted_sum = sum(it["score"] * it["norm_weight"] for it in raw_items)
    agg = max(-1.0, min(1.0, weighted_sum))

    # 4) Confirmations logic:
    #    Count blades that agree with the final direction (ignore neutral),
    #    then require at least min_confirmations.
    direction = 1 if agg > 0 else (-1 if agg < 0 else 0)
    confirms = 0
    if direction != 0:
        confirms = sum(1 for it in raw_items if it["score"] == direction)

    # 5) Verdict thresholds
    #    Small dead-zone to avoid noise; tweak if needed.
    THRESH = 0.20
    if direction > 0 and agg >= THRESH and confirms >= int(min_confirmations):
        final = "buy"
    elif direction < 0 and agg <= -THRESH and confirms >= int(min_confirmations):
        final = "sell"
    else:
        final = "pass"

    # 6) Build detailed scores payload
    scores = {
        "per_blade": [
            {
                "name": it["name"],
                "signal": it["signal"],
                "score": it["score"],                  # -1/0/+1
                "weight": it["weight"],               # raw weight
                "norm_weight": it["norm_weight"],     # normalized [0..1]
                "weighted_contrib": it["score"] * it["norm_weight"],
            }
            for it in raw_items
        ],
        "sum_weights": sum_w,
        "sum_norm_weights": sum(it["norm_weight"] for it in raw_items),  # should be 1.0
        "weighted_sum": weighted_sum,
        "agg": agg,
        "direction": "bullish" if direction > 0 else ("bearish" if direction < 0 else "neutral"),
        "threshold": THRESH,
        "min_confirmations": int(min_confirmations),
    }

    verdict = {
        "score": agg,
        "confirms": int(confirms),
        "verdict": final,
    }

    return scores, verdict
