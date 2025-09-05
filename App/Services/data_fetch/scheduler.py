cat > App/Services/data_fetch/scheduler.py <<'PY'
from . import sources
from .schema import MarketSnapshot
from .normalize import to_snapshot

def fetch_snapshot(symbol: str) -> MarketSnapshot:
    raw = {
        "symbol": symbol,
        "quote":   sources.fetch_price(symbol),
        "oi":      sources.fetch_oi(symbol),
        "greeks":  sources.fetch_greeks(symbol),
        "volume":  sources.fetch_volume(symbol),
        "sentiment": sources.fetch_sentiment(symbol),
    }
    return to_snapshot(raw)
PY
