# App/sudarshan/blades/sentiment.py
async def analyze_sentiment(data: dict | None = None):
    data = data or {}
    senti = str(data.get("sentiment", "neutral")).lower()
    score_map = {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0}
    return {"sentiment": senti, "score": score_map.get(senti, 0.0)}
