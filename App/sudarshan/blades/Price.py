# App/sudarshan/blades/price.py
async def analyze_price(data: dict | None = None):
    d = data or {}
    trend = str(d.get("trend", "neutral")).lower()
    score = {"bullish": 1.0, "bearish": -1.0}.get(trend, 0.0)
    return {"trend": trend, "score": score}
