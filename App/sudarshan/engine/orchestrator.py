from __future__ import annotations
import asyncio
from typing import Any, Dict

from ..blades.price import analyze_price
from ..blades.oi import analyze_oi
from ..blades.greeks import analyze_greeks
from ..blades.volume import analyze_volume
from ..blades.sentiment import analyze_sentiment

from .fusion import fuse, normalize_weights
from ..config import DEFAULT_WEIGHTS, DEFAULT_MIN_CONFIRMS

VERSION = "0.1.0"

async def analyze_market(context: Dict[str, Any]) -> Dict[str, Any]:
    context     = context or {}
    inputs      = context.get("inputs", {}) or {}
    min_confirm = int(context.get("min_confirms") or DEFAULT_MIN_CONFIRMS)
    weights     = normalize_weights(context.get("weights"), DEFAULT_WEIGHTS)

    price, oi, greeks, volume, sentiment = await asyncio.gather(
        analyze_price(inputs.get("price")),
        analyze_oi(inputs.get("oi")),
        analyze_greeks(inputs.get("greeks")),
        analyze_volume(inputs.get("volume")),
        analyze_sentiment(inputs.get("sentiment")),
    )

    per_blade = {
        "price": price,
        "oi": oi,
        "greeks": greeks,
        "volume": volume,
        "sentiment": sentiment,
    }

    fusion = fuse(per_blade, weights, min_confirm)

    return {
        "version": VERSION,
        "weights": weights,
        "min_confirms": min_confirm,
        "per_blade": per_blade,
        "fusion": fusion,
    }
