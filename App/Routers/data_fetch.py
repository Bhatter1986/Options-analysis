from fastapi import APIRouter, Query

router = APIRouter(prefix="/data", tags=["data"])

@router.get("/snapshot")
def snapshot(symbol: str = Query(..., description="e.g. NIFTY")):
    return {
        "symbol": symbol,
        "sudarshan_inputs": {
            "price":     {"trend": "bullish"},
            "oi":        {"signal": "bullish"},
            "greeks":    {"delta_bias": "long"},
            "volume":    {"volume_spike": True, "confirmation": True},
            "sentiment": {"sentiment": "neutral"},
        },
    }
