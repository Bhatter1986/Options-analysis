from typing import Any, Dict

async def analyze_sentiment(data: Dict[str, Any] | None) -> Dict[str, Any]:
    data = data or {}
    s = (data.get("sentiment") or "neutral").lower()
    if s not in {"bullish","bearish","neutral"}:
        s = "neutral"
    return {"ok": True, "signal": s, "detail": {"sentiment": s}}
