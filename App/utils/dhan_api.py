# App/utils/dhan_api.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException

# ---- Env & constants ---------------------------------------------------------

APP_MODE = os.getenv("APP_MODE", "SANDBOX").upper()

# Required creds (provide via Render/ENV or .env)
DHAN_SAND_CLIENT_ID = os.getenv("DHAN_SAND_CLIENT_ID", "")
DHAN_SAND_TOKEN = os.getenv("DHAN_SAND_TOKEN", "")

DHAN_LIVE_CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID", "")
DHAN_LIVE_TOKEN = os.getenv("DHAN_LIVE_TOKEN", "")

# Optional custom base URLs (defaults to Dhan v2)
DHAN_BASE_URL_SANDBOX = os.getenv("DHAN_BASE_URL_SANDBOX", "https://api.dhan.co")
DHAN_BASE_URL_LIVE = os.getenv("DHAN_BASE_URL_LIVE", "https://api.dhan.co")

# Dhan OptionChain rate limit: 1 req / 3 sec
DEFAULT_SLEEP_SEC = 3.0


# ---- Helpers ----------------------------------------------------------------

def _pick_creds() -> Tuple[str, str, str]:
    """Return (base_url, client_id, token) based on APP_MODE."""
    if APP_MODE == "LIVE":
        return (DHAN_BASE_URL_LIVE, DHAN_LIVE_CLIENT_ID, DHAN_LIVE_TOKEN)
    return (DHAN_BASE_URL_SANDBOX, DHAN_SAND_CLIENT_ID, DHAN_SAND_TOKEN)


def dhan_sleep(sec: float = DEFAULT_SLEEP_SEC) -> None:
    """Respect documented rate limits."""
    try:
        time.sleep(max(0.0, float(sec)))
    except Exception:
        time.sleep(DEFAULT_SLEEP_SEC)


def _headers(client_id: str, token: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "client-id": client_id,
        "access-token": token,
    }


def call_dhan_api(
    method: str,
    path: str,
    *,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Low-level caller for Dhan v2 endpoints.

    method: "GET" | "POST"
    path:   "/v2/optionchain/expirylist" or "/v2/optionchain"
    """
    base_url, client_id, token = _pick_creds()

    if not client_id or not token:
        raise HTTPException(
            status_code=500,
            detail="Dhan credentials missing. Set DHAN_* env vars.",
        )

    url = f"{base_url.rstrip('/')}{path}"

    try:
        with httpx.Client(timeout=timeout) as client:
            if method.upper() == "POST":
                resp = client.post(url, headers=_headers(client_id, token), json=json_body or {})
            else:
                resp = client.get(url, headers=_headers(client_id, token), params=json_body or {})

        # Raise for HTTP errors; Dhan returns JSON body with error sometimes
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        data = resp.json()
        return data if isinstance(data, dict) else {"data": data}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Dhan API call failed: {e}")


# ---- High level wrappers -----------------------------------------------------

def fetch_expirylist(under_security_id: int, under_exchange_segment: str) -> List[str]:
    """
    Hit Dhan /v2/optionchain/expirylist and return list of YYYY-MM-DD strings.

    Docs require:
      POST JSON: {"UnderlyingScrip": <int>, "UnderlyingSeg": "<enum>"}
      Headers: client-id, access-token
    """
    body = {
        "UnderlyingScrip": int(under_security_id),
        "UnderlyingSeg": str(under_exchange_segment),
    }

    data = call_dhan_api("POST", "/v2/optionchain/expirylist", json_body=body)

    if "data" not in data or not isinstance(data["data"], list):
        raise HTTPException(status_code=502, detail=f"Unexpected expirylist response: {data}")

    # Respect rate limit (1 req / 3 sec)
    dhan_sleep()

    return data["data"]


def fetch_optionchain(
    under_security_id: int,
    under_exchange_segment: str,
    expiry_date: str,
) -> Dict[str, Any]:
    """
    Hit Dhan /v2/optionchain for a given underlying + expiry.

    POST JSON expected by Dhan (mirroring their docs):
      {
        "UnderlyingScrip": <int>,
        "UnderlyingSeg":   "<enum>",
        "ExpiryDate":      "YYYY-MM-DD"
      }
    """
    body = {
        "UnderlyingScrip": int(under_security_id),
        "UnderlyingSeg": str(under_exchange_segment),
        "ExpiryDate": str(expiry_date),
    }

    data = call_dhan_api("POST", "/v2/optionchain", json_body=body)

    # Option chain payload varies; we just validate the top-level structure.
    if "data" not in data:
        raise HTTPException(status_code=502, detail=f"Unexpected optionchain response: {data}")

    # Respect rate limit
    dhan_sleep()

    return data["data"]
