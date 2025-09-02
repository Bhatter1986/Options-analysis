from typing import Dict, Any

def analyze_price(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Very basic price blade:
    expects {"trend": "bullish"|"bearish"|"neutral"}; returns a score.
    """
    trend = str(data.get("trend", "neutral")).lower()
    score_map = {"bullish": 0.7, "bearish": 0.7, "neutral": 0.5}
    score = score_map.get(trend, 0.5)
    return {"trend": trend, "score": score}
