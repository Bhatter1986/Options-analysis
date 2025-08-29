# App/utils/dhan_api.py
from __future__ import annotations
import os
import time
from typing import Any, Dict, List, Tuple

import httpx
from fastapi import HTTPException

# --------------------------------------------------------------------
# Mode & ENV
# --------------------------------------------------------------------
APP_MODE = os.getenv("APP_MODE", "SANDBOX").upper()

# Primary env (as you provided)
DHAN_SAND_CLIENT_ID = os.getenv("DHAN_SAND_CLIENT_ID", "")
DHAN_SAND_TOKEN     = os.getenv("DHAN_SAND_TOKEN", "")
DHAN_LIVE_CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID", "")
DHAN_LIVE_TOKEN     = os.getenv("DHAN_LIVE_TOKEN", "")

# Optional fallbacks (some parts of the app read these)
DHAN_CLIENT_ID      = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN   = os.getenv("DHAN_ACCESS_TOKEN", "")

# Base URLs (default Dhan v2 host)
DHAN_BASE_URL_SANDBOX = os.getenv("DHAN_BASE_URL_SANDBOX", "https://api.dhan.co")
DHAN_BASE_URL_LIVE    = os.getenv("DHAN_BASE_URL_LIVE", "https://api.dhan.co")

# Dhan OC rate limit: 1 req / 3s
DEFAULT_SLEEP_SEC = 3.0


def _pick_creds() -> Tuple[str, str, str]:
    """
    Decide base_url, client_id, token from APP_MODE.
    Also respects DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN as fallback.
    """
    if APP_MODE == "LIVE":
        cid = DHAN_LIVE_CLIENT_ID or DHAN_CLIENT_ID
        tok = DHAN_LIVE_TOKEN or DHAN_ACCESS_TOKEN
        return (DHAN_BASE_URL_LIVE, cid, tok)
    else:
        cid = DHAN_SAND_CLIENT_ID or DHAN_CLIENT_ID
        tok = DHAN_SAND_TOKEN or DHAN_ACCESS_TOKEN
        return (DHAN_BASE_URL_SANDBOX, cid, tok)


def dhan_sleep(sec: float = DEFAULT_SLEEP_SEC) -> None:
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


def call_dhan_api(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Low-level POST caller for Dhan v2.
    Example paths:
      /v2/optionchain/expirylist
      /v2/optionchain
    """
    base_url, client_id, token = _pick_creds()
    if not client_id or not token:
        raise HTTPException(500, "Missing Dhan credentials (client-id / access-token)")

    url = f"{base_url.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=_headers(client_id, token), json=body)
        if resp.status_code >= 400:
            # bubble up Dhan's error body
            raise HTTPException(resp.status_code, resp.text)
        data = resp.json()
        return data if isinstance(data, dict) else {"data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Dhan API call failed: {e}")


# --------------------------------------------------------------------
# High-level wrappers
# --------------------------------------------------------------------
def fetch_expirylist(security_id: int, seg: str) -> List[str]:
    """
    POST /v2/optionchain/expirylist
    Body per docs:
      { "UnderlyingScrip": <int>, "UnderlyingSeg": "<enum>" }
    """
    body = {
        "UnderlyingScrip": int(security_id),
        "UnderlyingSeg": str(seg),
    }
    data = call_dhan_api("/v2/optionchain/expirylist", body)
    # Respect documented rate limit
    dhan_sleep()
    return data.get("data", [])


def fetch_optionchain(security_id: int, seg: str, expiry: str) -> Dict[str, Any]:
    """
    POST /v2/optionchain
    Body per docs (IMPORTANT CHANGE: Expiry, not ExpiryDate):
      {
        "UnderlyingScrip": <int>,
        "UnderlyingSeg":   "<enum>",
        "Expiry":          "YYYY-MM-DD"
      }
    """
    body = {
        "UnderlyingScrip": int(security_id),
        "UnderlyingSeg": str(seg),
        "Expiry": str(expiry),           # <-- FIXED HERE
    }
    data = call_dhan_api("/v2/optionchain", body)
    # Respect documented rate limit
    dhan_sleep()
    return data.get("data", {})
