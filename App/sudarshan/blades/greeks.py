<<<<<<< HEAD
async def analyze_greeks(data: dict | None = None):
    """
    Input shape (example): {"delta_bias": "long"|"short"|"neutral"}
    """
    data = data or {}
    bias = (data.get("delta_bias") or "neutral").lower()
    if bias not in ("long", "short", "neutral"):
        bias = "neutral"
    return {"delta_bias": bias}
=======
async def analyze_greeks(data):
    """
    Greeks Analysis:
    - Input: option chain with greeks
    - Output: dict with delta/theta/vega trends
    """
    return {"delta_bias": "flat", "iv_percentile": None}
>>>>>>> d0cdbbc (Add Sudarshan blade modules (price/oi/greeks/volume/sentiment))
