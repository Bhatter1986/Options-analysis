cat > App/Services/data_fetch/sentiment.py <<'PY'
from typing import Literal

def compute_overall_sentiment(news_score: float = 0, fii_dii_flow: float = 0) -> Literal["bullish","bearish","neutral"]:
    score = news_score + fii_dii_flow
    if score > 0.1: return "bullish"
    if score < -0.1: return "bearish"
    return "neutral"
PY
