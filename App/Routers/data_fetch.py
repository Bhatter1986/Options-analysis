# App/Routers/data_fetch.py
from __future__ import annotations

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/data", tags=["data"])

VERSION = "0.1.0"


@router.get("/health")
def health() -> Dict[str, Any]:
    """
    Lightweight health for this router.
    """
    return {"ok": True, "name": "data_fetch", "version": VERSION}


def _build_stub_inputs(symbol: str) -> Dict[str, Any]:
    """
    Temporary stub to generate Sudarshan-ready inputs.

    Replace this with real fetchers:
      - Price trend from candles
      - OI signal from OI changes
      - Greeks delta-bias from option greeks
      - Volume spike/confirmation from volumes
      - Sentiment from your news/FII-DII pipeline
    """
    # NOTE: Keep keys + shapes exactly as Sudarshan expects.
    return {
        "symbol": symbol,
        "sudarshan_inputs": {
            "price": {"trend": "bullish"},              # or "bearish" / "neutral"
            "oi": {"signal": "bullish"},                # or "bearish" / "neutral"
            "greeks": {"delta_bias": "long"},           # or "short" / "neutral"
            "volume": {"volume_spike": True, "confirmation": True},
            "sentiment": {"sentiment": "neutral"},      # "bullish" / "bearish" / "neutral"
        },
    }


@router.get("/snapshot")
def snapshot(
    symbol: str = Query(..., description="Instrument code, e.g. NIFTY / BANKNIFTY / RELIANCE"),
) -> Dict[str, Any]:
    """
    Return a *normalized* data snapshot that is directly consumable by Sudarshan.

    Response shape:
    {
      "symbol": "...",
      "sudarshan_inputs": {
        "price":     {"trend": "..."},
        "oi":        {"signal": "..."},
        "greeks":    {"delta_bias": "..."},
        "volume":    {"volume_spike": bool, "confirmation": bool},
        "sentiment": {"sentiment": "..."}
      }
    }
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    # TODO: Wire real sources here
    # price = fetch_price_trend(symbol)
    # oi = compute_oi_signal(symbol)
    # greeks = derive_delta_bias(symbol)
    # volume = detect_volume_spike(symbol)
    # sentiment = read_sentiment(symbol)
    # return {"symbol": symbol, "sudarshan_inputs": {...}}

    return _build_stub_inputs(symbol)
