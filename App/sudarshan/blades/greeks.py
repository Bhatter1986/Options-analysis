from typing import Any, Dict

async def analyze_greeks(data: Dict[str, Any] | None) -> Dict[str, Any]:
    data = data or {}
    bias = str(data.get("delta_bias", "flat")).lower()
    if bias in ("long", "call", "positive"):
        sig = "bullish"
    elif bias in ("short", "put", "negative"):
        sig = "bearish"
    else:
        sig = "neutral"
    return {"ok": True, "signal": sig, "detail": {"delta_bias": bias}}
