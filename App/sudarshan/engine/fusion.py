from __future__ import annotations
from typing import Dict, Tuple

Signal = str  # "bullish" | "bearish" | "neutral"

def _score_of(signal: Signal) -> float:
    if signal == "bullish": return +1.0
    if signal == "bearish": return -1.0
    return 0.0  # neutral

def normalize_weights(w: Dict[str, float] | None, defaults: Dict[str, float]) -> Dict[str, float]:
    """Merge user weights with defaults & normalize to sum=1 (if any positive)."""
    merged = {**defaults, **(w or {})}
    total = sum(x for x in merged.values() if x > 0)
    if total <= 0:
        return {k: 0.0 for k in merged}
    return {k: v / total if v > 0 else 0.0 for k, v in merged.items()}

def fuse(
    per_blade: Dict[str, Dict],
    weights: Dict[str, float],
    min_confirms: int,
) -> Tuple[float, int, str]:
    """
    per_blade: {blade: {"signal": "bullish|bearish|neutral", ...}}
    weights: normalized weights for each blade
    returns: (agg_score, confirms, verdict)
    """
    agg = 0.0
    confirms = 0
    for blade, res in per_blade.items():
        sig: Signal = str(res.get("signal", "neutral")).lower()
        s = _score_of(sig)
        w = float(weights.get(blade, 0.0))
        agg += w * s
        if sig in ("bullish", "bearish"):
            confirms += 1

    verdict = "neutral"
    if confirms >= max(1, int(min_confirms)):
        if agg > 0.05:
            verdict = "bullish"
        elif agg < -0.05:
            verdict = "bearish"
        else:
            verdict = "neutral"
    return agg, confirms, verdict
