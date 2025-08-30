# App/Services/dhan_client.py
from __future__ import annotations

import os
import httpx

DHAN_BASE = "https://api.dhan.co/v2"
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
DHAN_CLIENT_ID    = os.getenv("DHAN_CLIENT_ID", "")

def _headers() -> dict:
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json",
    }

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
        # return only the array of valid dates in YYYY-MM-DD
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
