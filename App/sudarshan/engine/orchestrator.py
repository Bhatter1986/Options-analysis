# App/sudarshan/engine/orchestrator.py
import asyncio
from typing import Any, Dict
from ..blades import analyze_price, analyze_oi, analyze_greeks, analyze_volume, analyze_sentiment
from .fusion import fuse

async def analyze_market(context: Dict[str, Any]) -> Dict[str, Any]:
    context = context or {}
    inputs = context.get("inputs", {}) or {}

    tasks = [
        analyze_price(inputs.get("price")),
        analyze_oi(inputs.get("oi")),
        analyze_greeks(inputs.get("greeks")),
        analyze_volume(inputs.get("volume")),
        analyze_sentiment(inputs.get("sentiment")),
    ]
    price, oi, greeks, volume, sentiment = await asyncio.gather(*tasks)

    blade_outputs = {
        "price": price, "oi": oi, "greeks": greeks, "volume": volume, "sentiment": sentiment
    }

    scores, verdict = fuse(
        blade_outputs,
        weights=context.get("weights"),
        min_confirmations=int(context.get("min_confirms") or 3),
    )
    return {"blades": blade_outputs, "scores": scores, "verdict": verdict}
