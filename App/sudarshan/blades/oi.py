# App/sudarshan/blades/oi.py
async def analyze_oi(data: dict | None = None):
    data = data or {}
    signal = str(data.get("signal", "neutral")).lower()
    score_map = {
        "long_buildup": 1.0, "short_covering": 0.5,
        "short_buildup": -1.0, "long_unwinding": -0.5,
        "neutral": 0.0
    }
    return {"signal": signal, "score": score_map.get(signal, 0.0)}
