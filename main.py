from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Body, Query
from pydantic import BaseModel
from dotenv import load_dotenv

# Optional SDK (for option-chain, expiry list, charts, marketfeed helpers)
from dhanhq import dhanhq

load_dotenv()

app = FastAPI(title="options-analysis", version="1.0")

# -------------------------
# Environment / Config
# -------------------------
MODE = os.getenv("MODE", "TEST").upper()  # LIVE or TEST
LIVE = MODE == "LIVE"

LIVE_BASE = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")
SBX_BASE = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")

LIVE_CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID", "")
LIVE_TOKEN = os.getenv("DHAN_LIVE_ACCESS_TOKEN", "")

SBX_CLIENT_ID = os.getenv("DHAN_SANDBOX_CLIENT_ID", "")
SBX_TOKEN = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN", "")

BASE_URL = LIVE_BASE if LIVE else SBX_BASE
CLIENT_ID = LIVE_CLIENT_ID if LIVE else SBX_CLIENT_ID
ACCESS_TOKEN = LIVE_TOKEN if LIVE else SBX_TOKEN

HEADERS = {
    "client-id": CLIENT_ID or "",
    "access-token": ACCESS_TOKEN or "",
    "Content-Type": "application/json",
}

# Dhan SDK (used for some convenience methods)
_dhan: Optional[dhanhq] = None
if CLIENT_ID and ACCESS_TOKEN:
    try:
        _dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
    except Exception:
        _dhan = None


# -------------------------
# Models
# -------------------------
class MarketQuoteBody(BaseModel):
    """
    For LTP / OHLC / Quote (full packet). Pass exactly the dict that Dhan expects.
    Example: {"NSE_EQ": [1333, 11915]}
    """
    securities: Dict[str, list[int]]


class OptionChainBody(BaseModel):
    under_security_id: int
    under_exchange_segment: str  # e.g. "IDX_I", "NSE_FNO"
    expiry: str                  # "YYYY-MM-DD"


# -------------------------
# Helpers
# -------------------------
async def _proxy_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=HEADERS, params=params)
        return {
            "status_code": r.status_code,
            "ok": r.is_success,
            "url": str(r.request.url),
            "data": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text,
        }


def _sdk_required(feature: str):
    if _dhan is None:
        return {
            "status": "failure",
            "remarks": f"Dhan SDK unavailable for {feature}. Check client id/token & MODE.",
            "mode": MODE,
            "client_id_present": bool(CLIENT_ID),
            "token_present": bool(ACCESS_TOKEN),
        }


# -------------------------
# Root & Health
# -------------------------
@app.get("/")
def root():
    return {
        "ok": True,
        "service": "options-analysis",
        "time": datetime.utcnow().isoformat() + "Z",
        "mode": MODE,
        "env": "LIVE" if LIVE else "SANDBOX",
    }


@app.get("/health")
def health():
    return {"status": "healthy", "mode": MODE, "env": "LIVE" if LIVE else "SANDBOX"}


# -------------------------
# Broker status (simple sanity)
# -------------------------
@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "env": "LIVE" if LIVE else "SANDBOX",
        "token_present": bool(ACCESS_TOKEN),
        "client_id_present": bool(CLIENT_ID),
        "base_url": BASE_URL,
    }


# -------------------------
# Orders / Positions / Holdings / Funds
# (pure REST proxy to Dhan v2)
# -------------------------
@app.get("/orders")
async def orders():
    return await _proxy_get("/orders")

@app.get("/positions")
async def positions():
    return await _proxy_get("/positions")

@app.get("/holdings")
async def holdings():
    return await _proxy_get("/holdings")

@app.get("/funds")
async def funds():
    return await _proxy_get("/funds")


# -------------------------
# Market Quote (LTP / OHLC / Quote)
# Dhan SDK call (single function ohlc_data returns snapshot).
# -------------------------
@app.post("/marketfeed/ltp")
def market_ltp(body: MarketQuoteBody = Body(...)):
    missing = _sdk_required("marketfeed ltp")
    if isinstance(missing, dict):
        return missing
    try:
        # SDK: ohlc_data returns dict with ticker/ohlc/quote sub-packets
        out = _dhan.ohlc_data(securities=body.securities)  # type: ignore
        return {"status": "success", "packet": "ticker_data", "data": out}
    except Exception as e:
        return {"status": "failure", "error": str(e)}

@app.post("/marketfeed/ohlc")
def market_ohlc(body: MarketQuoteBody = Body(...)):
    missing = _sdk_required("marketfeed ohlc")
    if isinstance(missing, dict):
        return missing
    try:
        out = _dhan.ohlc_data(securities=body.securities)  # type: ignore
        return {"status": "success", "packet": "ohlc_data", "data": out}
    except Exception as e:
        return {"status": "failure", "error": str(e)}

@app.post("/marketfeed/quote")
def market_quote(body: MarketQuoteBody = Body(...)):
    missing = _sdk_required("marketfeed quote")
    if isinstance(missing, dict):
        return missing
    try:
        out = _dhan.ohlc_data(securities=body.securities)  # type: ignore
        return {"status": "success", "packet": "quote_data", "data": out}
    except Exception as e:
        return {"status": "failure", "error": str(e)}


# -------------------------
# Option chain + expiry list (SDK)
# -------------------------
@app.get("/optionchain/expirylist")
def optionchain_expirylist(
    under_security_id: int = Query(..., alias="under_security_id"),
    under_exchange_segment: str = Query(..., alias="under_exchange_segment")
):
    missing = _sdk_required("expiry_list")
    if isinstance(missing, dict):
        return missing
    try:
        out = _dhan.expiry_list(  # type: ignore
            under_security_id=under_security_id,
            under_exchange_segment=under_exchange_segment
        )
        return {"status": "success", "data": out}
    except Exception as e:
        return {"status": "failure", "error": str(e)}


@app.post("/optionchain")
def optionchain(body: OptionChainBody):
    missing = _sdk_required("option_chain")
    if isinstance(missing, dict):
        return missing
    try:
        out = _dhan.option_chain(  # type: ignore
            under_security_id=body.under_security_id,
            under_exchange_segment=body.under_exchange_segment,
            expiry=body.expiry
        )
        return {"status": "success", "data": out}
    except Exception as e:
        return {"status": "failure", "error": str(e)}


# -------------------------
# Charts (SDK)
# -------------------------
@app.get("/charts/intraday")
def charts_intraday(
    security_id: int = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: str = Query(...)
):
    missing = _sdk_required("intraday_minute_data")
    if isinstance(missing, dict):
        return missing
    try:
        out = _dhan.intraday_minute_data(  # type: ignore
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type
        )
        return {"status": "success", "data": out}
    except Exception as e:
        return {"status": "failure", "error": str(e)}


@app.get("/charts/historical")
def charts_historical(
    security_id: int = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: str = Query(...),
    expiry_code: int = Query(0),
    from_date: str = Query(..., description="YYYY-MM-DD"),
    to_date: str = Query(..., description="YYYY-MM-DD"),
):
    missing = _sdk_required("historical_daily_data")
    if isinstance(missing, dict):
        return missing
    try:
        out = _dhan.historical_daily_data(  # type: ignore
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            expiry_code=expiry_code,
            from_date=from_date,
            to_date=to_date
        )
        return {"status": "success", "data": out}
    except Exception as e:
        return {"status": "failure", "error": str(e)}


# -------------------------
# Self-test page (quick links + status)
# -------------------------
@app.get("/__selftest")
async def selftest():
    status = broker_status()
    samples = {
        "root": "/",
        "health": "/health",
        "broker_status": "/broker_status",
        "orders": "/orders",
        "positions": "/positions",
        "holdings": "/holdings",
        "funds": "/funds",
        "expirylist_sample": "/optionchain/expirylist?under_security_id=13&under_exchange_segment=IDX_I",
        "intraday_sample": "/charts/intraday?security_id=1333&exchange_segment=NSE&instrument_type=EQUITY",
        "historical_sample": "/charts/historical?security_id=1333&exchange_segment=NSE&instrument_type=EQUITY&expiry_code=0&from_date=2024-01-01&to_date=2024-02-01",
    }
    return {
        "status": status,
        "mode_note": "MODE=LIVE uses LIVE_... keys, otherwise SANDBOX (TEST).",
        "samples": samples,
        "now": datetime.utcnow().isoformat() + "Z",
    }
