from typing import Dict, Tuple

def fuse(per_blade: Dict[str, str], weights: Dict[str, float], min_confirms: int) -> Tuple[float, int, str]:
    score = 0.0
    confirms_bull = 0
    confirms_bear = 0

    for k, sig in per_blade.items():
        w = float(weights.get(k, 1.0))
        if sig == "bullish":
            score += w
            confirms_bull += 1
        elif sig == "bearish":
            score -= w
            confirms_bear += 1

    confirms = max(confirms_bull, confirms_bear)
    if confirms >= min_confirms:
        verdict = "bullish" if score > 0 else ("bearish" if score < 0 else "neutral")
    else:
        verdict = "neutral"
    return score, confirms, verdict
