# App/Services/data_fetch/normalize.py
from __future__ import annotations
from typing import Dict

def to_sudarshan_inputs(raw: Dict) -> Dict:
    """Map raw snapshot fields to Sudarshan blade-inputs."""
    return {
        "price":   {"trend": raw.get("price", {}).get("trend", "neutral")},
        "oi":      {"signal": raw.get("oi", {}).get("signal", "neutral")},
        "greeks":  {"delta_bias": raw.get("greeks", {}).get("delta_bias", "flat")},
        "volume":  {
            "volume_spike": bool(raw.get("volume", {}).get("volume_spike", False)),
            "confirmation": bool(raw.get("volume", {}).get("confirmation", False)),
        },
        "sentiment": {"sentiment": raw.get("sentiment", {}).get("sentiment", "neutral")},
    }
