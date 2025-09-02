async def analyze_greeks(data: dict | None = None):
    """
    Input shape (example): {"delta_bias": "long"|"short"|"neutral"}
    """
    data = data or {}
    bias = (data.get("delta_bias") or "neutral").lower()
    if bias not in ("long", "short", "neutral"):
        bias = "neutral"
    return {"delta_bias": bias}
