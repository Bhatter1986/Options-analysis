cat > App/Services/data_fetch/sources.py <<'PY'
import time
from typing import Dict, Any

# TODO: In future, replace these stubs with real calls:
# - from App.Services.dhan_client import get_quote, get_option_oi, ...
# - from App.Services.feed_client import get_greeks, get_volume, ...
# Right now we return dummy-but-realistic values so the pipeline runs.

def fetch_price(symbol: str) -> Dict[str, Any]:
    return {"symbol": symbol, "price": 25000.0, "ts": int(time.time() * 1000)}

def fetch_oi(symbol: str) -> Dict[str, Any]:
    return {"symbol": symbol, "oi": 125000, "ts": int(time.time() * 1000)}

def fetch_greeks(symbol: str) -> Dict[str, Any]:
    return {"symbol": symbol, "delta": 0.35, "ts": int(time.time() * 1000)}

def fetch_volume(symbol: str) -> Dict[str, Any]:
    # spike/confirm placeholders; later compute via rolling history
    return {"symbol": symbol, "volume": 3200, "spike": True, "confirm": True, "ts": int(time.time() * 1000)}

def fetch_sentiment(symbol: str) -> Dict[str, Any]:
    # later: news/FII-DII/netflow → score → bullish/bearish/neutral
    return {"symbol": symbol, "sentiment": "neutral", "score": 0.0, "ts": int(time.time() * 1000)}
PY
