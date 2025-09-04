from typing import Any, Dict

def _norm(v: str | None) -> str:
    v = (v or "").lower()
    return {"up":"bullish","bull":"bullish","bullish":"bullish",
            "down":"bearish","bear":"bearish","bearish":"bearish"}.get(v, "neutral")

async def analyze_price(data: Dict[str, Any] | None) -> Dict[str, Any]:
    data = data or {}
    sig = _norm(data.get("trend"))
    return {"ok": True, "signal": sig, "detail": {"trend": data.get("trend", "neutral")}}
