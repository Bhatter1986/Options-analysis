# App/sudarshan/blades/greeks.py
async def analyze_greeks(data: dict | None = None):
    data = data or {}
    delta_bias = str(data.get("delta_bias", "neutral")).lower()
    score_map = {"long": 1.0, "short": -1.0, "neutral": 0.0}
    return {"delta_bias": delta_bias, "score": score_map.get(delta_bias, 0.0)}
