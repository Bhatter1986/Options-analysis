# App/sudarshan/blades/greeks.py
async def analyze_greeks(data: dict | None = None):
    d = data or {}
    bias = str(d.get("delta_bias", "neutral")).lower()
    score = {"long": 0.8, "short": -0.8}.get(bias, 0.0)
    return {"delta_bias": bias, "score": score}
