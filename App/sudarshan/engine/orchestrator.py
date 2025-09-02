# App/sudarshan/engine/orchestrator.py
import asyncio
from typing import Any, Dict
from ..blades import analyze_price, analyze_oi, analyze_greeks, analyze_volume, analyze_sentiment
from .fusion import fuse

async def analyze_market(context: Dict[str, Any]) -> Dict[str, Any]:
    inputs = (context or {}).get("inputs", {})

    results = await asyncio.gather(
        analyze_price(inputs.get("price")),
        analyze_oi(inputs.get("oi")),
        analyze_greeks(inputs.get("greeks")),
        analyze_volume(inputs.get("volume")),
        analyze_sentiment(inputs.get("sentiment")),
    )

    blade_outputs = {
        "price":    results[0],
        "oi":       results[1],
        "greeks":   results[2],
        "volume":   results[3],
        "sentiment":results[4],
    }

    scores, verdict = fuse(
        blade_outputs,
        weights=context.get("weights"),
        min_confirmations=int(context.get("min_confirms") or 3),
    )

    return {"blades": blade_outputs, "scores": scores, "verdict": verdict}
