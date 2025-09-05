cat > App/Services/data_fetch/schema.py <<'PY'
from typing import Optional, Dict
from pydantic import BaseModel, Field

class Quote(BaseModel):
    symbol: str
    price: float
    ts: Optional[int] = None  # epoch ms

class OI(BaseModel):
    symbol: str
    oi: int
    ts: Optional[int] = None

class Greeks(BaseModel):
    symbol: str
    delta: float
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta: Optional[float] = None
    ts: Optional[int] = None

class Volume(BaseModel):
    symbol: str
    volume: int
    ts: Optional[int] = None
    spike: Optional[bool] = None
    confirm: Optional[bool] = None

class Sentiment(BaseModel):
    symbol: str
    sentiment: str = Field(pattern="^(bullish|bearish|neutral)$")
    score: Optional[float] = None
    ts: Optional[int] = None

class MarketSnapshot(BaseModel):
    symbol: str
    quote: Quote
    oi: OI
    greeks: Greeks
    volume: Volume
    sentiment: Sentiment

    def sudarshan_inputs(self) -> Dict:
        """Convert snapshot -> Sudarshan /analyze inputs format."""
        return {
            "price":   {"trend": "bullish" if self.quote.price >= 0 else "bearish"},
            "oi":      {"signal": "bullish" if self.oi.oi >= 0 else "bearish"},
            "greeks":  {"delta_bias": "long" if (self.greeks.delta or 0) >= 0 else "short"},
            "volume":  {"volume_spike": bool(self.volume.spike), "confirmation": bool(self.volume.confirm)},
            "sentiment": {"sentiment": self.sentiment.sentiment},
        }
PY
