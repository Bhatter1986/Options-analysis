from fastapi import APIRouter, Query
from App.Services import dhan_client

router = APIRouter(prefix="/instruments", tags=["Instruments"])


# ===== 1. Instrument CSV (Compact/Detailed) =====
@router.get("/csv")
def instruments_csv(detailed: bool = True):
    """
    Get Dhan Instruments CSV (Compact or Detailed).
    """
    url = dhan_client.get_instruments_csv(detailed=detailed)
    return {"csv_url": url}


# ===== 2. Instrument List (by Exchange Segment) =====
@router.get("/segment/{exchange_segment}")
def instruments_by_segment(exchange_segment: str):
    """
    Get instruments for a specific exchange segment.
    Example: NSE_EQ, NSE_FNO, BSE_EQ
    """
    data = dhan_client.get_instruments_by_segment(exchange_segment)
    return {"exchange_segment": exchange_segment, "data": data}
