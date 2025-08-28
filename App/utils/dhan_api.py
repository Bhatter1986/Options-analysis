from __future__ import annotations
import os, time
from typing import Any, Dict, List
import httpx
from fastapi import HTTPException

APP_MODE = os.getenv("APP_MODE", "SANDBOX").upper()

# Env creds
DHAN_SAND_CLIENT_ID = os.getenv("DHAN_SAND_CLIENT_ID", "")
DHAN_SAND_TOKEN     = os.getenv("DHAN_SAND_TOKEN", "")
DHAN_LIVE_CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID", "")
DHAN_LIVE_TOKEN     = os.getenv("DHAN_LIVE_TOKEN", "")

# Base URLs
DHAN_BASE_URL_SANDBOX = os.getenv("DHAN_BASE_URL_SANDBOX", "https://api.dhan.co")
DHAN_BASE_URL_LIVE    = os.getenv("DHAN_BASE_URL_LIVE", "https://api.dhan.co")

DEFAULT_SLEEP_SEC = 3.0

def _pick_creds():
    if APP_MODE == "LIVE":
        return (DHAN_BASE_URL_LIVE, DHAN_LIVE_CLIENT_ID, DHAN_LIVE_TOKEN)
    return (DHAN_BASE_URL_SANDBOX, DHAN_SAND_CLIENT_ID, DHAN_SAND_TOKEN)

def dhan_sleep(sec: float = DEFAULT_SLEEP_SEC):
    time.sleep(sec)

def _headers(client_id: str, token: str) -> Dict[str,str]:
    return {
        "Content-Type": "application/json",
        "client-id": client_id,
        "access-token": token,
    }

def call_dhan_api(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    base_url, client_id, token = _pick_creds()
    if not client_id or not token:
        raise HTTPException(500, "Missing Dhan credentials")

    url = f"{base_url.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=_headers(client_id, token), json=body)
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, resp.text)
        return resp.json()
    except Exception as e:
        raise HTTPException(502, f"Dhan API call failed: {e}")

# -------- High Level -------- #

def fetch_expirylist(security_id: int, seg: str) -> List[str]:
    body = {"UnderlyingScrip": int(security_id), "UnderlyingSeg": seg}
    data = call_dhan_api("/v2/optionchain/expirylist", body)
    dhan_sleep()
    return data.get("data", [])

def fetch_optionchain(security_id: int, seg: str, expiry: str) -> Dict[str, Any]:
    body = {
        "UnderlyingScrip": int(security_id),
        "UnderlyingSeg": seg,
        "ExpiryDate": expiry,
    }
    data = call_dhan_api("/v2/optionchain", body)
    dhan_sleep()
    return data.get("data", {})
