from __future__ import annotations
from typing import Dict, Any, Optional

# Map signals to numeric scores
_SCORE = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}

def normalize_weights(override: Optional[Dict[str, float]], defaults: Dict[str, float]) -> Dict[str, float]:
    w = dict(defaults)
    if override:
        for k, v in override.items():
            if k in w and isinstance(v, (int, float)) and v >= 0:
                w[k] = float(v)

    total = sum(w.values()) or 1.0
    return {k: (v / total) for k, v in w.items()}

def _signal_score(sig: str) -> float:
    return _SCORE.get(str(sig).lower(), 0.0)

def fuse(per_blade: Dict[str, Dict[str, Any]],
         weights: Dict[str, float],
         min_confirms: int = 3) -> Dict[str, Any]:
    # Weighted aggregate
    agg = 0.0
    for name, w in weights.items():
        sig = (per_blade.get(name, {}).get("signal") or "neutral")
        agg += _signal_score(sig) * w

    # Small deadband so tiny noise != verdict
    threshold = 0.15
    if   agg >  threshold: verdict = "bullish"
    elif agg < -threshold: verdict = "bearish"
    else:                  verdict = "neutral"

    confirms = sum(
        1 for r in per_blade.values()
        if r.get("signal") == verdict and verdict != "neutral"
    )

    return {"score": round(agg, 3), "verdict": verdict, "confirms": confirms, "min_needed": min_confirms}
