# App/sudarshan/blades/sentiment.py
async def analyze_sentiment(data: dict | None = None):
    d = data or {}
    s = str(d.get("sentiment", "neutral")).lower()
    score = {"bullish": 0.7, "bearish": -0.7, "neutral": 0.0}.get(s, 0.0)
    return {"sentiment": s, "score": score}
