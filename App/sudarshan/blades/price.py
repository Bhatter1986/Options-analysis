from typing import Any, Dict

async def analyze_price(data: Dict[str, Any] | None) -> Dict[str, Any]:
    data = data or {}
    trend = str(data.get("trend", "neutral")).lower()
    if trend in ("up", "bull", "bullish"):
        sig = "bullish"
    elif trend in ("down", "bear", "bearish"):
        sig = "bearish"
    else:
        sig = "neutral"
    return {"ok": True, "signal": sig, "detail": {"trend": trend}}
