from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Tuple
import httpx
from fastapi import HTTPException

APP_MODE = os.getenv("APP_MODE", "SANDBOX").upper()

# env vars (Render → Dashboard → Environment)
DHAN_CLIENT_ID     = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN  = os.getenv("DHAN_ACCESS_TOKEN", "")
DHAN_BASE_URL      = os.getenv("DHAN_BASE_URL", "https://api.dhan.co")

DEFAULT_SLEEP_SEC = float(os.getenv("DHAN_SLEEP_SEC", "0.8"))

def _headers() -> Dict[str, str]:
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        raise HTTPException(500, "Missing DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN")
    return {
        "Content-Type": "application/json",
        "client-id": DHAN_CLIENT_ID,
        "access-token": DHAN_ACCESS_TOKEN,
    }

def _post(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{DHAN_BASE_URL.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=_headers(), json=body)
        if resp.status_code >= 400:
            # Pass-through Dhan error for easier debugging
            raise HTTPException(resp.status_code, resp.text)
        return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Dhan API call failed: {e}")
    finally:
        time.sleep(DEFAULT_SLEEP_SEC)

# ---- Public helpers ----

def get_expiry_list(under_security_id: int, under_exchange_segment: str) -> List[str]:
    body = {"UnderlyingScrip": int(under_security_id), "UnderlyingSeg": under_exchange_segment}
    data = _post("/v2/optionchain/expirylist", body)
    return data.get("data", []) or []

def get_option_chain_raw(under_security_id: int, under_exchange_segment: str, expiry: str) -> Dict[str, Any]:
    body = {
        "UnderlyingScrip": int(under_security_id),
        "UnderlyingSeg": under_exchange_segment,
        "ExpiryDate": expiry,
    }
    data = _post("/v2/optionchain", body)
    # Dhan wraps as {"data": {...}, "status": "success"}
    return data.get("data", {}) or {}
