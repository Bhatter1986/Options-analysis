from typing import Any, Dict

async def analyze_volume(data: Dict[str, Any] | None) -> Dict[str, Any]:
    data = data or {}
    spike = bool(data.get("volume_spike"))
    confirm = bool(data.get("confirmation"))
    sig = "bullish" if spike and confirm else "neutral"
    return {"ok": True, "signal": sig, "detail": {"spike": spike, "confirm": confirm}}
