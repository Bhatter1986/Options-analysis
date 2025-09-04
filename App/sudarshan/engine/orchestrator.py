import asyncio
from typing import Any, Dict, Tuple

from ..blades.price import analyze_price
from ..blades.oi import analyze_oi
from ..blades.greeks import analyze_greeks
from ..blades.volume import analyze_volume
from ..blades.sentiment import analyze_sentiment
from .fusion import fuse
from ..config import DEFAULT_WEIGHTS, DEFAULT_MIN_CONFIRMS

async def analyze_market(context: Dict[str, Any]) -> Dict[str, Any]:
    context = context or {}
    inputs  = context.get("inputs", {}) or {}
    weights = context.get("weights") or DEFAULT_WEIGHTS
    min_confirms = int(context.get("min_confirms") or DEFAULT_MIN_CONFIRMS)

    price, oi, greeks, volume, sentiment = await asyncio.gather(
        analyze_price(inputs.get("price")),
        analyze_oi(inputs.get("oi")),
        analyze_greeks(inputs.get("greeks")),
        analyze_volume(inputs.get("volume")),
        analyze_sentiment(inputs.get("sentiment")),
    )

    per_blade = {
        "price": price["signal"],
        "oi": oi["signal"],
        "greeks": greeks["signal"],
        "volume": volume["signal"],
        "sentiment": sentiment["signal"],
    }

    agg, confirms, verdict = fuse(per_blade, weights, min_confirms)
    return {
        "ok": True,
        "version": "0.1.0",
        "signals": per_blade,
        "score": agg,
        "confirms": confirms,
        "verdict": verdict,
        "detail": {
            "price": price, "oi": oi, "greeks": greeks, "volume": volume, "sentiment": sentiment
        }
    }
