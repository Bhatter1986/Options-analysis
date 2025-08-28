# App/utils/dhan_api.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException

# -----------------------------------------------------------------------------
# Env & constants

APP_MODE = os.getenv("APP_MODE", "SANDBOX").upper()

# Sandbox creds
DHAN_SAND_CLIENT_ID = os.getenv("DHAN_SAND_CLIENT_ID", "")
DHAN_SAND_TOKEN     = os.getenv("DHAN_SAND_TOKEN", "")
DHAN_SANDBOX_URL    = os.getenv("DHAN_SANDBOX_URL", "https://api.dhan.co/v2")

# Live creds
DHAN_LIVE_CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID", "")
DHAN_LIVE_TOKEN     = os.getenv("DHAN_LIVE_TOKEN", "")
DHAN_LIVE_URL       = os.getenv("DHAN_LIVE_URL", "https://api.dhan.co/v2")

# Dhan OptionChain rate limit: 1 req / 3 sec
DEFAULT_SLEEP_SEC = 3.0


# -----------------------------------------------------------------------------
# Helpers

def _pick_creds() -> Tuple[str, str, str]:
    """
    Return (base_url, client_id, token) by APP_MODE.
    """
    if APP_MODE == "LIVE":
        return (DHAN_LIVE_URL, DHAN_LIVE_CLIENT_ID, DHAN_LIVE_TOKEN)
    return (DHAN_SANDBOX_URL, DHAN_SAND_CLIENT_ID, DHAN_SAND_TOKEN)


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


def _join_url(base_url: str, endpoint: str) -> str:
    """
    Join base + endpoint safely. If base doesn't end with /v2 and endpoint
    also doesn't start with /v2, add /v2 in the middle.

    Works for:
      base=https://api.dhan.co      endpoint=/optionchain/expirylist -> .../v2/optionchain/expirylist
      base=https://api.dhan.co/v2   endpoint=/optionchain/expirylist -> .../v2/optionchain/expirylist
      base=https://api.dhan.co/v2   endpoint=/v2/optionchain         -> .../v2/optionchain
    """
    b = (base_url or "").rstrip("/")
    e = "/" + (endpoint or "").lstrip("/")

    if not b.endswith("/v2") and not e.startswith("/v2/"):
        b += "/v2"
    return b + e


def call_dhan_api(
    method: str,
    endpoint: str,
    *,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Low-level caller for Dhan v2 endpoints.

    method: "GET" | "POST"
    endpoint: "/optionchain/expirylist" or "/optionchain" (without /v2)
    """
    base_url, client_id, token = _pick_creds()

    if not client_id or not token:
        raise HTTPException(
            status_code=500,
            detail="Dhan credentials missing. Set DHAN_* env vars.",
        )

    url = _join_url(base_url, endpoint)

    try:
        with httpx.Client(timeout=timeout) as client:
            if method.upper() == "POST":
                resp = client.post(url, headers=_headers(client_id, token), json=json_body or {})
            else:
                resp = client.get(url, headers=_headers(client_id, token), params=json_body or {})

        # HTTP error?
        if resp.status_code >= 400:
            # Surface Dhan's body for easier debugging
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        data = resp.json()
        return data if isinstance(data, dict) else {"data": data}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Dhan API call failed: {e}")


# -----------------------------------------------------------------------------
# High-level wrappers

def fetch_expirylist(under_security_id: int, under_exchange_segment: str) -> List[str]:
    """
    POST /optionchain/expirylist
    Body:
      { "UnderlyingScrip": <int>, "UnderlyingSeg": "<enum>" }
    Returns: list of YYYY-MM-DD strings.
    """
    body = {
        "UnderlyingScrip": int(under_security_id),
        "UnderlyingSeg":   str(under_exchange_segment),
    }

    data = call_dhan_api("POST", "/optionchain/expirylist", json_body=body)

    if "data" not in data or not isinstance(data["data"], list):
        raise HTTPException(status_code=502, detail=f"Unexpected expirylist response: {data}")

    # rate limit
    dhan_sleep()
    return data["data"]


def fetch_optionchain(
    under_security_id: int,
    under_exchange_segment: str,
    expiry_date: str,
) -> Dict[str, Any]:
    """
    POST /optionchain
    Body:
      {
        "UnderlyingScrip": <int>,
        "UnderlyingSeg":   "<enum>",
        "ExpiryDate":      "YYYY-MM-DD"
      }
    """
    body = {
        "UnderlyingScrip": int(under_security_id),
        "UnderlyingSeg":   str(under_exchange_segment),
        "ExpiryDate":      str(expiry_date),
    }

    data = call_dhan_api("POST", "/optionchain", json_body=body)

    if "data" not in data:
        raise HTTPException(status_code=502, detail=f"Unexpected optionchain response: {data}")

    # rate limit
    dhan_sleep()
    return data["data"]
