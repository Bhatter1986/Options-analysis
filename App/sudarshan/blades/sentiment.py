# App/sudarshan/blades/sentiment.py
from typing import Dict, Any, Optional

async def analyze_sentiment(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Sentiment blade:
      Inputs (all optional):
        - fii_net: float         # FII net buy/sell (cr)
        - dii_net: float         # DII net buy/sell (cr)
        - global_bias: str       # 'risk_on' | 'risk_off' | 'neutral'
        - news_score: float      # -1..+1 (aggregated)
    Returns:
      - sentiment: 'bullish' | 'bearish' | 'neutral'
      - score: 0..1
      - notes: str
    """
    d = data or {}

    score = 0.5
    notes = []

    try:
        fii = float(d.get("fii_net", 0.0))
        dii = float(d.get("dii_net", 0.0))
    except Exception:
        fii = 0.0
        dii = 0.0

    if fii - dii > 200:           # crude heuristic
        score += 0.15; notes.append("fii>dii")
    elif dii - fii > 200:
        score -= 0.15; notes.append("dii>fii")

    gb = str(d.get("global_bias", "neutral")).lower()
    if gb == "risk_on":
        score += 0.1;  notes.append("risk_on")
    elif gb == "risk_off":
        score -= 0.1;  notes.append("risk_off")

    try:
        ns = float(d.get("news_score", 0.0))
        score += max(-0.15, min(0.15, ns * 0.15))
        if ns != 0:
            notes.append(f"news={ns:+.2f}")
    except Exception:
        pass

    score = max(0.0, min(1.0, score))
    if score >= 0.6:
        senti = "bullish"
    elif score <= 0.4:
        senti = "bearish"
    else:
        senti = "neutral"

    return {"sentiment": senti, "score": float(f"{score:.3f}"), "notes": ", ".join(notes)}
