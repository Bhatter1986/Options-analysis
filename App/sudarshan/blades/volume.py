from typing import Any, Dict

async def analyze_volume(data: Dict[str, Any] | None) -> Dict[str, Any]:
    data = data or {}
    spike = bool(data.get("volume_spike", False))
    confirm = bool(data.get("confirmation", False))
    if spike and confirm:
        sig = "bullish"
    elif spike and not confirm:
        sig = "neutral"
    else:
        sig = "neutral"
    return {"ok": True, "signal": sig, "detail": {"spike": spike, "confirm": confirm}}
