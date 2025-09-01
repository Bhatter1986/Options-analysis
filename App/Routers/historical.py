# App/Routers/historical.py
from typing import Any, Dict, List
from fastapi import APIRouter, Body, HTTPException

router = APIRouter(prefix="/historical", tags=["Historical"])

# --- If you already have this helper, keep using yours.
# from ._helpers import historical_to

# --- Minimal fallback if `historical_to` doesn't exist in your codebase ---
# Comment this out if you already have a shared proxy helper.
# from apps.services import dhan_client
# async def historical_to(path: str, body: Dict[str, Any]):
#     """
#     Very small proxy shim for Dhan Historical endpoints.
#     path examples: "/historical/daily", "/historical/intraday"
#     """
#     if path == "/historical/daily":
#         return await dhan_client.get_historical_daily(body)
#     elif path == "/historical/intraday":
#         return await dhan_client.get_historical_intraday(body)
#     else:
#         raise ValueError(f"Unsupported historical path: {path}")

def _normalize_daily_arrays_to_candles(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Dhan 'historical daily' returns per-field arrays:
    {
      "open":[], "high":[], "low":[], "close":[], "volume":[], "timestamp":[]
    }
    Convert to: [{"t": ts, "o": o, "h": h, "l": l, "c": c, "v": v}, ...]
    """
    opens   = resp.get("open", []) or []
    highs   = resp.get("high", []) or []
    lows    = resp.get("low", []) or []
    closes  = resp.get("close", []) or []
    volumes = resp.get("volume", []) or []
    times   = resp.get("timestamp", []) or []

    n = min(len(opens), len(highs), len(lows), len(closes), len(volumes), len(times))
    out: List[Dict[str, Any]] = []
    for i in range(n):
        out.append({
            "t": times[i],
            "o": opens[i],
            "h": highs[i],
            "l": lows[i],
            "c": closes[i],
            "v": volumes[i],
        })
    return out

@router.post("/daily")
async def daily(body: Dict[str, Any] = Body(...)):
    """
    Forwards to Dhan /historical/daily endpoint.

    Example body:
      {
        "securityId": "1333",
        "exchangeSegment": "NSE_EQ",
        "instrument": "EQUITY",
        "expiryCode": 0,
        "oi": false,
        "fromDate": "2024-01-01",
        "toDate": "2024-02-01"
      }
    """
    try:
        return await historical_to("/historical/daily", body)
    except Exception as e:
        raise HTTPException(502, f"Dhan historical daily failed: {e}")

@router.post("/daily/candles")
async def daily_candles(body: Dict[str, Any] = Body(...)):
    """
    Same as /historical/daily but returns normalized candle objects:
      [{t, o, h, l, c, v}, ...]
    """
    try:
        raw = await historical_to("/historical/daily", body)
        if not isinstance(raw, dict):
            raise ValueError("Unexpected Dhan daily response shape (expected dict with arrays).")
        return _normalize_daily_arrays_to_candles(raw)
    except Exception as e:
        raise HTTPException(502, f"Dhan historical daily (normalized) failed: {e}")
