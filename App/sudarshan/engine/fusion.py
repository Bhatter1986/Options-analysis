mkdir -p App/sudarshan/blades && cat > App/sudarshan/blades/__init__.py <<'PY'
from .price import analyze_price
from .oi import analyze_oi
from .greeks import analyze_greeks
from .volume import analyze_volume
from .sentiment import analyze_sentiment
PY

cat > App/sudarshan/blades/price.py <<'PY'
async def analyze_price(data):
    """
    Price Action Analysis:
    - Input: candle data, EMA, VWAP, S/R
    - Output: dict with trend & support/resistance
    """
    return {"trend": "neutral", "support": None, "resistance": None}
PY

cat > App/sudarshan/blades/oi.py <<'PY'
async def analyze_oi(data):
    """
    Open Interest Analysis:
    - Input: option chain OI data
    - Output: dict with PCR, max pain, buildup signals
    """
    return {"pcr": None, "max_pain": None, "signal": "neutral"}
PY

cat > App/sudarshan/blades/greeks.py <<'PY'
async def analyze_greeks(data):
    """
    Greeks Analysis:
    - Input: option chain with greeks
    - Output: dict with delta/theta/vega trends
    """
    return {"delta_bias": "flat", "iv_percentile": None}
PY

cat > App/sudarshan/blades/volume.py <<'PY'
async def analyze_volume(data):
    """
    Volume Analysis:
    - Input: market volume & depth
    - Output: dict with volume spike, confirmation
    """
    return {"volume_spike": False, "confirmation": False}
PY

cat > App/sudarshan/blades/sentiment.py <<'PY'
async def analyze_sentiment(data):
    """
    Sentiment Analysis:
    - Input: FII/DII, global indices, news sentiment
    - Output: dict with bullish/bearish/neutral
    """
    return {"sentiment": "neutral"}
PY
