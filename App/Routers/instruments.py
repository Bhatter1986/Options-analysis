# App/Routers/instruments.py
import os
import requests
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/instruments", tags=["instruments"])

# ---------------------------
# DEMO Data (static fallback)
# ---------------------------
DEMO_INDICES = [
    {"name": "NIFTY 50", "symbol": "NIFTY", "security_id": 999901},
    {"name": "BANKNIFTY", "symbol": "BANKNIFTY", "security_id": 999903},
    {"name": "FINNIFTY", "symbol": "FINNIFTY", "security_id": 999907},
    {"name": "MIDCPNIFTY", "symbol": "MIDCPNIFTY", "security_id": 999910},
    {"name": "SENSEX", "symbol": "SENSEX", "security_id": 999920},
]

# ---------------------------
# Utils
# ---------------------------
def is_live_mode() -> bool:
    return os.getenv("MODE", "DEMO").upper() == "LIVE"

def get_dhan_headers():
    return {
        "accept": "application/json",
        "access-token": os.getenv("DHAN_ACCESS_TOKEN", ""),
    }

# ---------------------------
# Routes
# ---------------------------

@router.get("/search")
def search_instruments(
    q: str = Query(..., description="Search symbol or name"),
    exchange_segment: str = Query("IDX_I", description="Exchange segment"),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Search instruments by symbol/name.
    """
    if not is_live_mode():
        # DEMO → simple filter
        data = [x for x in DEMO_INDICES if q.lower() in x["name"].lower()]
        return {"mode": "DEMO", "count": len(data), "data": data[:limit]}

    # LIVE → Dhan API
    url = f"{os.getenv('DHAN_BASE_URL')}/instruments"
    params = {"q": q, "exchange_segment": exchange_segment, "limit": limit}
    resp = requests.get(url, headers=get_dhan_headers(), params=params, timeout=10)
    return resp.json()


@router.get("/indices")
def list_indices(
    q: Optional[str] = Query(None, description="Filter by name"),
    limit: int = Query(50, ge=1, le=500)
):
    """
    List all major indices.
    """
    data = DEMO_INDICES

    if is_live_mode():
        # TODO: Integrate with real Dhan indices API if available
        # Right now fallback to DEMO list (since DhanHQ v2 has flat CSV for instruments)
        pass

    # filter
    if q:
        qlow = q.lower()
        data = [x for x in data if qlow in x["name"].lower()]

    return {"mode": "LIVE" if is_live_mode() else "DEMO", "count": len(data), "data": data[:limit]}


@router.get("/by-id")
def get_instrument_by_id(
    security_id: int = Query(..., description="Security ID from instruments CSV")
):
    """
    Get single instrument details by security_id.
    """
    if not is_live_mode():
        for x in DEMO_INDICES:
            if x["security_id"] == security_id:
                return {"mode": "DEMO", "data": x}
        return {"mode": "DEMO", "error": "Instrument not found"}

    # LIVE → would normally query full CSV or Dhan API
    url = f"{os.getenv('INSTRUMENTS_URL')}"
    return {"mode": "LIVE", "source": url, "security_id": security_id}
