# App/utils/dhan_api.py
from __future__ import annotations

import os
import time
import requests
from fastapi import HTTPException

# Pick LIVE vs SANDBOX from APP_MODE (default SANDBOX)
APP_MODE = os.getenv("APP_MODE", "SANDBOX").upper()

if APP_MODE == "LIVE":
    DHAN_CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")
    DHAN_TOKEN     = os.getenv("DHAN_LIVE_TOKEN") or os.getenv("DHAN_TOKEN")
else:
    DHAN_CLIENT_ID = os.getenv("DHAN_SAND_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")
    DHAN_TOKEN     = os.getenv("DHAN_SAND_TOKEN") or os.getenv("DHAN_TOKEN")

BASE_URL = "https://api.dhan.co/v2"
RATE_SEC = 3  # Dhan OC: 1 req / 3 sec

def _headers() -> dict:
    if not DHAN_CLIENT_ID or not DHAN_TOKEN:
        raise HTTPException(500, "Dhan env missing (client/token)")
    return {
        "client-id": DHAN_CLIENT_ID,
        "access-token": DHAN_TOKEN,
        "Content-Type": "application/json",
    }

def _post(endpoint: str, payload: dict) -> dict:
    url = f"{BASE_URL}{endpoint}"
    try:
        r = requests.post(url, headers=_headers(), json=payload, timeout=30)
    except requests.RequestException as e:
        raise HTTPException(502, f"Network error calling {endpoint}: {e}")
    if r.status_code != 200:
        raise HTTPException(r.status_code, f"{endpoint} failed: {r.text}")
    return r.json()

def fetch_expirylist(under_scrip: int, under_seg: str) -> dict:
    """
    Calls /optionchain/expirylist
    payload: {"UnderlyingScrip": <int>, "UnderlyingSeg": "<code>"}
    """
    res = _post("/optionchain/expirylist", {
        "UnderlyingScrip": int(under_scrip),
        "UnderlyingSeg": under_seg,
    })
    time.sleep(RATE_SEC)
    return res

def fetch_optionchain(under_scrip: int, under_seg: str, expiry: str) -> dict:
    """
    Calls /optionchain
    payload: {"UnderlyingScrip": <int>, "UnderlyingSeg": "<code>", "Expiry": "YYYY-MM-DD"}
    """
    res = _post("/optionchain", {
        "UnderlyingScrip": int(under_scrip),
        "UnderlyingSeg": under_seg,
        "Expiry": expiry,
    })
    time.sleep(RATE_SEC)
    return res
