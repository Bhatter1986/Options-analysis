from typing import Any, Dict

async def analyze_oi(data: Dict[str, Any] | None) -> Dict[str, Any]:
    data = data or {}
    sig = str(data.get("signal", "neutral")).lower()
    if sig not in ("bullish", "bearish", "neutral"):
        sig = "neutral"
    return {"ok": True, "signal": sig, "detail": data}
