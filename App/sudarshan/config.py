from typing import Dict

DEFAULT_WEIGHTS: Dict[str, float] = {
    "price": 1.0, "oi": 1.0, "greeks": 0.8, "volume": 0.7, "sentiment": 0.5
}
DEFAULT_MIN_CONFIRMS = 3
