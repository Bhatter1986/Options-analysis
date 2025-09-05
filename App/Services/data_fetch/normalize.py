cat > App/Services/data_fetch/normalize.py <<'PY'
from .schema import Quote, OI, Greeks, Volume, Sentiment, MarketSnapshot

def to_snapshot(raw: dict) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=raw["symbol"],
        quote=Quote(**raw["quote"]),
        oi=OI(**raw["oi"]),
        greeks=Greeks(**raw["greeks"]),
        volume=Volume(**raw["volume"]),
        sentiment=Sentiment(**raw["sentiment"]),
    )
PY
