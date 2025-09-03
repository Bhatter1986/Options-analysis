# App/sudarshan/engine/orchestrator.py
import asyncio
from typing import Any, Dict
from ..blades import (
    analyze_price, analyze_oi, analyze_greeks, analyze_volume, analyze_sentiment
)
from .fusion import fuse

async def analyze_market(context: Dict[str, Any]) -> Dict[str, Any]:
    ctx = context or {}
    inputs = ctx.get("inputs", {}) or {}

    results = await asyncio.gather(
        analyze_price(inputs.get("price")),
        analyze_oi(inputs.get("oi")),
        analyze_greeks(inputs.get("greeks")),
        analyze_volume(inputs.get("volume")),
        analyze_sentiment(inputs.get("sentiment")),
    )

    blades = {
        "price": results[0],
        "oi": results[1],
        "greeks": results[2],
        "volume": results[3],
        "sentiment": results[4],
    }

    scores, verdict = fuse(
        blades,
        weights=ctx.get("weights"),
        min_confirmations=int(ctx.get("min_confirms") or 3),
    )
    return {"blades": blades, "scores": scores, "verdict": verdict}
