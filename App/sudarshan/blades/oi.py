# App/sudarshan/blades/oi.py
async def analyze_oi(data: dict | None = None):
    d = data or {}
    sig = str(d.get("signal", "neutral")).lower()
    mapping = {
        "long_buildup": 1.0,
        "short_covering": 0.7,
        "short_buildup": -1.0,
        "long_unwinding": -0.7,
        "neutral": 0.0,
    }
    return {"signal": sig, "score": mapping.get(sig, 0.0)}
