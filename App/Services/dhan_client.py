from __future__ import annotations

import os
import httpx
from typing import Any, Dict

# ---- Base URL ----
DHAN_BASE = "https://api.dhan.co/v2"

# ---- Env vars ----
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
DHAN_CLIENT_ID    = os.getenv("DHAN_CLIENT_ID", "")

def _headers() -> dict:
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

# ------------------ Option Chain APIs ------------------

async def get_expiry_list(under_security_id: int, under_exchange_segment: str):
    """
    Calls Dhan v2 POST /optionchain/expirylist
    Body keys MUST be: UnderlyingScrip, UnderlyingSeg
    """
    url = f"{DHAN_BASE}/optionchain/expirylist"
    payload = {
        "UnderlyingScrip": under_security_id,
        "UnderlyingSeg": under_exchange_segment,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=_headers(), json=payload)
        r.raise_for_status()
        data = r.json()
        return data.get("data", [])

async def get_option_chain_raw(under_security_id: int, under_exchange_segment: str, expiry: str):
    """
    Calls Dhan v2 POST /optionchain
    Body keys MUST be: UnderlyingScrip, UnderlyingSeg, Expiry
    """
    url = f"{DHAN_BASE}/optionchain"
    payload = {
        "UnderlyingScrip": under_security_id,
        "UnderlyingSeg": under_exchange_segment,
        "Expiry": expiry,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()

# ------------------ Market Quote APIs ------------------

async def get_ltp(req_body: Dict[str, Any]):
    """
    Calls Dhan v2 POST /marketfeed/ltp
    req_body example: {"NSE_FNO":[49081], "NSE_EQ":[11536]}
    """
    url = f"{DHAN_BASE}/marketfeed/ltp"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, headers=_headers(), json=req_body)
        r.raise_for_status()
        return r.json()

async def get_ohlc(req_body: Dict[str, Any]):
    """
    Calls Dhan v2 POST /marketfeed/ohlc
    req_body example: {"NSE_FNO":[49081]}
    """
    url = f"{DHAN_BASE}/marketfeed/ohlc"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, headers=_headers(), json=req_body)
        r.raise_for_status()
        return r.json()

async def get_quote(req_body: Dict[str, Any]):
    """
    Calls Dhan v2 POST /marketfeed/quote
    req_body example: {"NSE_FNO":[49081]}
    """
    url = f"{DHAN_BASE}/marketfeed/quote"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=_headers(), json=req_body)
        r.raise_for_status()
        return r.json()

# ------------------ Historical Data APIs ------------------

async def get_historical_daily(payload: dict):
    """
    Calls Dhan v2 POST /charts/historical
    Body keys: securityId, exchangeSegment, instrument, expiryCode, oi, fromDate, toDate
    """
    url = f"{DHAN_BASE}/charts/historical"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()

async def get_historical_intraday(payload: dict):
    """
    Calls Dhan v2 POST /charts/intraday
    Body keys: securityId, exchangeSegment, instrument, interval, oi, fromDate, toDate
    """
    url = f"{DHAN_BASE}/charts/intraday"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()
