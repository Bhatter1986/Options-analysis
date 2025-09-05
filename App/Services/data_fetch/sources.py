# App/Services/data_fetch/sources.py
from __future__ import annotations
from typing import Dict

def get_live_snapshot(symbol: str) -> Dict:
    """
    TODO: Replace with real Dhan/NSE calls.
    Abhi ke liye lightweight placeholder so that the pipeline works.
    """
    s = symbol.upper()
    # Just a tiny variation to prove it's "live"
    bullish = s.startswith("BANK")

    return {
        "symbol": s,
        "price": {"trend": "bullish" if bullish else "bullish"},
        "oi": {"signal": "bullish"},
        "greeks": {"delta_bias": "long"},
        "volume": {"volume_spike": True, "confirmation": True},
        "sentiment": {"sentiment": "neutral"},
    }
