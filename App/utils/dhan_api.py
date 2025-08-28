# App/utils/dhan_api.py
from __future__ import annotations

import os
import time
import json
from typing import Any, Dict, Optional, Tuple

import requests
from fastapi import HTTPException

# ---- Configuration -----------------------------------------------------------

# Pick environment: default SANDBOX
APP_MODE = os.getenv("APP_MODE", "SANDBOX").upper().strip()

# Accept both naming styles to keep backward-compat
# Sandbox
DHAN_SANDBOX_CLIENT_ID = (
    os.getenv("DHAN_SANDBOX_CLIENT_ID")
    or os.getenv("DHAN_SAND_CLIENT_ID")
    or os.getenv("DHAN_CLIENT_ID_SAND")
)
DHAN_SANDBOX_TOKEN = (
    os.getenv("DHAN_SANDBOX_TOKEN")
    or os.getenv("DHAN_SAND_TOKEN")
    or os.getenv("DHAN_ACCESS_TOKEN_SAND")
)

# Live
DHAN_LIVE_CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID")
DHAN_LIVE_TOKEN = os.getenv("DHAN_LIVE_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN_LIVE")

# Base URLs (Dhan v2)
# If your account uses a dedicated sandbox host, set DHAN_BASE_URL_SANDBOX env.
DHAN_BASE_URL_SANDBOX = os.getenv("DHAN_BASE_URL_SANDBOX", "https://api.dhan.co/v2")
DHAN_BASE_URL_LIVE = os.getenv("DHAN_BASE_URL_LIVE", "https://api.dhan.co/v2")

# Request defaults
REQUEST_TIMEOUT = float(os.getenv("DHAN_HTTP_TIMEOUT", "20"))  # seconds
USER_AGENT = os.getenv("DHAN_HTTP_UA", "options-analysis/1.0 (+fastapi)")


def _active_creds() -> Tuple[str, str, str]:
    """
    Returns (base_url, client_id, token) based on APP_MODE.
    Raises HTTPException 503 if missing.
    """
    if APP_MODE == "LIVE":
        base = DHAN_BASE_URL_LIVE
        cid = DHAN_LIVE_CLIENT_ID or ""
        tok = DHAN_LIVE_TOKEN or ""
    else:
        base = DHAN_BASE_URL_SANDBOX
        cid = DHAN_SANDBOX_CLIENT_ID or ""
        tok = DHAN_SANDBOX_TOKEN or ""

    if not cid or not tok:
        raise HTTPException(
            status_code=503,
            detail=(
                "Dhan credentials missing. "
                "Ensure client-id & access-token are set for the selected APP_MODE."
            ),
        )
    return base, cid, tok


def _headers(client_id: str, token: str) -> Dict[str, str]:
    return {
        "accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        # Dhan v2 expects these:
        "access-token": token,
        "client-id": client_id,
    }


# ---- Public helpers ----------------------------------------------------------

def call_dhan_api(
    endpoint: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    method: str = "POST",
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Generic Dhan API caller.
    - endpoint: like '/optionchain/expirylist' or '/optionchain'
    - payload: JSON body for POST; ignored for GET
    - params:  query params for GET (rare for these endpoints)
    """
    base, client_id, token = _active_creds()
    url = f"{base.rstrip('/')}{endpoint}"

    hdrs = _headers(client_id, token)
    timeout = timeout or REQUEST_TIMEOUT

    try:
        if method.upper() == "GET":
            resp = requests.get(url, headers=hdrs, params=params, timeout=timeout)
        else:
            # Default to POST
            resp = requests.post(url, headers=hdrs, json=payload or {}, timeout=timeout)

    except requests.Timeout:
        raise HTTPException(504, f"Dhan API timeout: {endpoint}")

    except requests.RequestException as e:
        # Network/SSL/connection issues
        raise HTTPException(502, f"Dhan API network error: {e}")

    # Non-200 handling with details surfaced
    if resp.status_code != 200:
        # Try to extract useful body
        body = resp.text
        try:
            jb = resp.json()
            body = json.dumps(jb)
        except Exception:
            pass
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Dhan API {endpoint} failed ({resp.status_code}): {body}",
        )

    try:
        return resp.json()
    except ValueError:
        raise HTTPException(502, "Dhan API returned non-JSON response")


def dhan_sleep(seconds: float = 3.0) -> None:
    """
    Respect Dhan rate-limit for Option Chain (1 req / 3s).
    """
    time.sleep(seconds)


# ---- Convenience wrappers (clean usage in routers) --------------------------

def fetch_expirylist(underlying_scrip: int, underlying_seg: str) -> Dict[str, Any]:
    """
    POST /optionchain/expirylist
    payload:
      { "UnderlyingScrip": <int>, "UnderlyingSeg": "<enum>" }
    """
    body = {
        "UnderlyingScrip": int(underlying_scrip),
        "UnderlyingSeg": str(underlying_seg),
    }
    return call_dhan_api("/optionchain/expirylist", payload=body, method="POST")


def fetch_optionchain(
    underlying_scrip: int,
    underlying_seg: str,
    expiry: str,
) -> Dict[str, Any]:
    """
    POST /optionchain
    payload:
      { "UnderlyingScrip": <int>, "UnderlyingSeg": "<enum>", "Expiry": "YYYY-MM-DD" }
    """
    body = {
        "UnderlyingScrip": int(underlying_scrip),
        "UnderlyingSeg": str(underlying_seg),
        "Expiry": str(expiry),
    }
    return call_dhan_api("/optionchain", payload=body, method="POST")
