import os
import requests
from typing import Optional

# ===== Config =====
BASE_URL = "https://api.dhan.co/v2"
COMPACT_CSV = "https://images.dhan.co/api-data/api-scrip-master.csv"
DETAILED_CSV = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

# ===== Auth Header =====
def _headers():
    token = os.getenv("DHAN_ACCESS_TOKEN")
    if not token:
        raise ValueError("DHAN_ACCESS_TOKEN not set in environment variables.")
    return {"access-token": token}


# ===== Instrument List (CSV) =====
def get_instruments_csv(detailed: bool = True) -> str:
    """
    Returns instrument CSV URL from Dhan (Compact or Detailed).
    """
    return DETAILED_CSV if detailed else COMPACT_CSV


# ===== Instrument List (by Exchange Segment) =====
def get_instruments_by_segment(exchange_segment: str):
    """
    Fetch detailed instrument list for one exchange segment.
    Example exchange_segment: NSE_EQ, NSE_FNO, BSE_EQ
    """
    url = f"{BASE_URL}/instrument/{exchange_segment}"
    resp = requests.get(url, headers=_headers())
    resp.raise_for_status()
    return resp.json()


# ===== Option Chain =====
def get_option_chain(symbol: str, expiry: Optional[str] = None):
    """
    Fetch option chain for a given symbol.
    Example: symbol="NIFTY", expiry="2025-09-11"
    """
    url = f"{BASE_URL}/option-chain/{symbol}"
    if expiry:
        url += f"?expiry={expiry}"
    resp = requests.get(url, headers=_headers())
    resp.raise_for_status()
    return resp.json()


# ===== Expiry List =====
def get_expiry_list(symbol: str):
    """
    Return available expiry dates for a given symbol.
    Derived from option chain response.
    """
    data = get_option_chain(symbol)
    expiries = {item["expiryDate"] for item in data.get("optionContracts", [])}
    return sorted(expiries)
