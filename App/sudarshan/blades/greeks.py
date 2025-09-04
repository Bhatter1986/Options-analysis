from typing import Any, Dict

async def analyze_greeks(data: Dict[str, Any] | None) -> Dict[str, Any]:
    """Example rule: delta_bias 'long' => bullish, 'short' => bearish"""
    data = data or {}
    bias = (data.get("delta_bias") or "").lower()
    sig = "bullish" if bias in {"long","pos","positive"} else "bearish" if bias in {"short","neg","negative"} else "neutral"
    return {"ok": True, "signal": sig, "detail": {"delta_bias": bias or "neutral"}}
