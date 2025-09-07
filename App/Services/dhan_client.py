# App/Services/dhan_client.py
from __future__ import annotations

import os
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

# Optional WS helpers (agar aap use karna chahen)
try:
    import asyncio
    import json
    import websockets  # type: ignore
except Exception:  # package optional
    websockets = None  # noqa: N816


# =========================
# Base URL & Auth
# =========================
DHAN_BASE = "https://api.dhan.co/v2"

DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")


def _headers() -> Dict[str, str]:
    """
    Dhan required headers.
    """
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json",
    }


# =========================
# Instruments (official)
# =========================
def get_instruments_csv(detailed: bool = True) -> str:
    """
    Return Dhan instruments CSV URL.

    detailed=True  -> https://images.dhan.co/api-data/api-scrip-master-detailed.csv
    detailed=False -> https://images.dhan.co/api-data/api-scrip-master.csv
    """
    if detailed:
        return "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
    return "https://images.dhan.co/api-data/api-scrip-master.csv"


async def get_instruments_by_segment(exchange_segment: str) -> Any:
    """
    GET /v2/instrument/{exchangeSegment}

    Examples:
      NSE_EQ, BSE_EQ, NSE_FNO, MCX_COMM, NSE_CURR, ...
      (exact mapping Dhan Annexure me hai)
    """
    url = f"{DHAN_BASE}/instrument/{exchange_segment}"
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(url, headers=_headers())
        r.raise_for_status()
        return r.json()


# =========================
# Option Chain
# =========================
async def get_expiry_list(
    under_security_id: int,
    under_exchange_segment: str,
) -> List[Dict[str, Any]]:
    """
    POST /v2/optionchain/expirylist
    Body:
      {
        "UnderlyingScrip": <int SecurityID>,
        "UnderlyingSeg": "<exchangeSegment>"
      }
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
        # Dhan usually wraps under {"data": [...]}
        return data.get("data", data if isinstance(data, list) else [])


async def get_option_chain_raw(
    under_security_id: int,
    under_exchange_segment: str,
    expiry: str,
) -> Dict[str, Any]:
    """
    POST /v2/optionchain
    Body:
      {
        "UnderlyingScrip": <int SecurityID>,
        "UnderlyingSeg": "<exchangeSegment>",
        "Expiry": "YYYY-MM-DD"  # Dhan format
      }
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


# =========================
# Market Feed / Quote
# =========================
async def market_ltp(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST /v2/marketfeed/ltp
    Body structure Dhan docs ke mutabik pass karein.
    """
    url = f"{DHAN_BASE}/marketfeed/ltp"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=_headers(), json=body)
        r.raise_for_status()
        return r.json()


async def market_ohlc(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST /v2/marketfeed/ohlc
    """
    url = f"{DHAN_BASE}/marketfeed/ohlc"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=_headers(), json=body)
        r.raise_for_status()
        return r.json()


async def market_quote(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST /v2/marketfeed/quote
    """
    url = f"{DHAN_BASE}/marketfeed/quote"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=_headers(), json=body)
        r.raise_for_status()
        return r.json()


# =========================
# Historical
# =========================
async def _post_dhan(path: str, payload: Dict[str, Any]) -> Any:
    """
    Internal helper for POST calls to Dhan base.
    """
    url = f"{DHAN_BASE}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()


async def historical_raw(payload: Dict[str, Any]) -> Any:
    """
    POST /v2/historical-data/ohlc
    """
    return await _post_dhan("/historical-data/ohlc", payload)


async def historical_to(path_suffix: str, payload: Dict[str, Any]) -> Any:
    """
    Proxy to any other historical sub-endpoint:
      e.g. historical_to("/historical-data/indices-ohlc", {...})
    """
    if not path_suffix.startswith("/"):
        path_suffix = "/" + path_suffix
    return await _post_dhan(path_suffix, payload)


# =========================
# (Optional) WebSocket Helpers – Live feed / 20-Depth
# NOTE: Dhan WS auth/URL alag se ho sakta hai. Isko aapke
# depth20_ws.py / live_feed.py ki exact expectations ke
# hisaab se tweak karen. Ye basic skeleton hai.
# =========================
async def connect_live_feed(ws_url: str, subscribe_msg: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Example usage:
      async for msg in connect_live_feed("wss://...", {"action": "subscribe", ...}):
          ...process msg...

    Agar 'websockets' package available na ho to RuntimeError raise hoga.
    """
    if websockets is None:
        raise RuntimeError("websockets package unavailable")

    async with websockets.connect(ws_url, extra_headers=_headers(), ping_interval=20) as ws:
        await ws.send(json.dumps(subscribe_msg))
        while True:
            raw = await ws.recv()
            try:
                yield json.loads(raw)
            except Exception:
                yield {"raw": raw}


async def connect_depth20(ws_url: str, subscribe_msg: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Same pattern as connect_live_feed for 20-market-depth.
    """
    async for item in connect_live_feed(ws_url, subscribe_msg):
        yield item
