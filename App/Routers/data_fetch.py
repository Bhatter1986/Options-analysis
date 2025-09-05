# 1) Make sure the package init file exists (empty file is OK)
mkdir -p App/Routers
[ -f App/Routers/__init__.py ] || touch App/Routers/__init__.py

# 2) Ensure data_fetch router file exists at the RIGHT path (case-sensitive)
#    (Skip this if it already exists. Otherwise create/paste your code.)
[ -f App/Routers/data_fetch.py ] || printf '%s\n' \
'from fastapi import APIRouter, Query
router = APIRouter(prefix="/data", tags=["data"])
@router.get("/snapshot")
def snapshot(symbol: str = Query(..., description="e.g. NIFTY, BANKNIFTY")):
    return {
        "symbol": symbol,
        "sudarshan_inputs": {
            "price": {"trend": "bullish"},
            "oi": {"signal": "bullish"},
            "greeks": {"delta_bias": "long"},
            "volume": {"volume_spike": True, "confirmation": True},
            "sentiment": {"sentiment": "neutral"},
        },
    }' > App/Routers/data_fetch.py

# 3) Verify both files are in place
ls -l App/Routers/__init__.py App/Routers/data_fetch.py
