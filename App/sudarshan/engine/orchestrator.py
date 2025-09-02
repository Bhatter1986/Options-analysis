# App/sudarshan/engine/orchestrator.py
import asyncio
from typing import Any, Dict, Optional, Tuple, List
from ..blades import (
    analyze_price,
    analyze_oi,
    analyze_greeks,
    analyze_volume,
    analyze_sentiment,
)
from .fusion import fuse

async def analyze_market(context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    context:
    {
      "weights": {"price":1, "oi":1, "greeks":0.8, "volume":0.7, "sentiment":0.5},
      "min_confirms": 3,
      "inputs": {
         "price": {"trend":"bullish"},
         "oi": {"signal":"long_buildup"},
         "greeks": {"delta_bias":"long"},
         "volume": {"volume_spike": true, "confirmation": true},
         "sentiment": {"sentiment":"neutral"}
      }
    }
    """
    context = context or {}
    inputs = (context or {}).get("inputs", {}) or {}

    # Build coroutine list with safety check (so future non-async bugs surface early)
    task_specs: List[Tuple[str, Any, Any]] = [
        ("price", analyze_price, inputs.get("price")),
        ("oi", analyze_oi, inputs.get("oi")),
        ("greeks", analyze_greeks, inputs.get("greeks")),
        ("volume", analyze_volume, inputs.get("volume")),
        ("sentiment", analyze_sentiment, inputs.get("sentiment")),
    ]

    coros = []
    for name, fn, arg in task_specs:
        coro = fn(arg)
        if not asyncio.iscoroutine(coro):
            # Give a very clear error if any blade is not async
            raise TypeError(
                f"Blade '{name}' is not async (got {type(coro).__name__}) "
                f"at {fn.__code__.co_filename}:{fn.__code__.co_firstlineno}"
            )
        coros.append(coro)

    results = await asyncio.gather(*coros)

    blade_outputs = {
        "price": results[0],
        "oi": results[1],
        "greeks": results[2],
        "volume": results[3],
        "sentiment": results[4],
    }

    scores, verdict = fuse(
        blade_outputs,
        weights=context.get("weights"),
        min_confirmations=int(context.get("min_confirms") or context.get("min_confirmations") or 3),
    )

    return {"blades": blade_outputs, "scores": scores, "verdict": verdict}
