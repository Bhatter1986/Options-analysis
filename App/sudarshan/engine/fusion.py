cat > App/sudarshan/engine/fusion.py <<'PY'
from __future__ import annotations
from typing import Dict, Any

DEFAULT_WEIGHTS: Dict[str, float] = {
    "price": 1.0,
    "oi": 1.0,
    "greeks": 0.8,
    "volume": 0.7,
    "sentiment": 0.5,
}
DEFAULT_MIN_CONFIRMS = 3

def _score_bool(ok: bool) -> float:
    return 1.0 if ok else 0.0

async def fuse(
    inputs: Dict[str, Any],
    weights: Dict[str, float] | None = None,
    min_confirms: int | None = None,
) -> Dict[str, Any]:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    minc = int(min_confirms or DEFAULT_MIN_CONFIRMS)

    detail: Dict[str, bool] = {}

    price_ok = (inputs.get("price") or {}).get("trend") == "bullish"
    detail["price"] = bool(price_ok)

    oi_ok = (inputs.get("oi") or {}).get("signal") == "long_buildup"
    detail["oi"] = bool(oi_ok)

    greeks_ok = (inputs.get("greeks") or {}).get("delta_bias") == "long"
    detail["greeks"] = bool(greeks_ok)

    vol = inputs.get("volume") or {}
    volume_ok = bool(vol.get("volume_spike")) and bool(vol.get("confirmation", True))
    detail["volume"] = bool(volume_ok)

    sentiment_ok = (inputs.get("sentiment") or {}).get("sentiment", "neutral") == "bullish"
    detail["sentiment"] = bool(sentiment_ok)

    confirms = sum(1 for v in detail.values() if v)
    confirmation = confirms >= minc

    score = (
        w["price"] * _score_bool(price_ok)
        + w["oi"] * _score_bool(oi_ok)
        + w["greeks"] * _score_bool(greeks_ok)
        + w["volume"] * _score_bool(volume_ok)
        + w["sentiment"] * _score_bool(sentiment_ok)
    ) / (sum(w.values()) or 1.0)

    return {
        "confirmation": confirmation,
        "confirms": int(confirms),
        "min_confirms": minc,
        "score": round(score, 3),
        "detail": detail,
    }
PY
