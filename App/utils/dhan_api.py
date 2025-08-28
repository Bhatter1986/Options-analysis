# App/utils/dhan_api.py
from __future__ import annotations
import os, time, requests
from fastapi import HTTPException

# LIVE / SANDBOX mode choose
APP_MODE = os.getenv("APP_MODE", "SANDBOX").upper()

if APP_MODE == "LIVE":
    DHAN_CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID")
    DHAN_TOKEN = os.getenv("DHAN_LIVE_TOKEN")
    BASE_URL = "https://api.dhan.co"
else:
    DHAN_CLIENT_ID = os.getenv("DHAN_SAND_CLIENT_ID")
    DHAN_TOKEN = os.getenv("DHAN_SAND_TOKEN")
    BASE_URL = "https://api-sandbox.dhan.co"

HEADERS = {
    "accept": "application/json",
    "client-id": DHAN_CLIENT_ID or "",
    "access-token": DHAN_TOKEN or "",
}

def _get(path: str, params: dict | None = None):
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dhan API error: {str(e)}")

# ---- Specific APIs ----
def fetch_instruments():
    return _get("/instruments")

def fetch_expirylist(under_security_id: int, under_exchange_segment: str):
    return _get("/optionchain/expirylist", {
        "under_security_id": under_security_id,
        "under_exchange_segment": under_exchange_segment
    })

def fetch_optionchain(under_security_id: int, under_exchange_segment: str, expiry: str):
    return _get("/optionchain", {
        "under_security_id": under_security_id,
        "under_exchange_segment": under_exchange_segment,
        "expiry": expiry
    })
