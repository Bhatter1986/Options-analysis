# App/sudarshan/blades/price.py
async def analyze_price(data: dict | None = None):
    data = data or {}
    trend = str(data.get("trend", "neutral")).lower()
    score_map = {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0}
    return {"trend": trend, "score": score_map.get(trend, 0.0)}
