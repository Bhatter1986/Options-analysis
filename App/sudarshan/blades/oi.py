from typing import Any, Dict

async def analyze_oi(data: Dict[str, Any] | None) -> Dict[str, Any]:
    data = data or {}
    raw = (data.get("signal") or "").lower()
    sig = raw if raw in {"bullish","bearish","neutral"} else "neutral"
    return {"ok": True, "signal": sig, "detail": data}
