# main.py
from fastapi import FastAPI, Request, HTTPException, Path
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Optional, Any
import os
import json
import asyncio

# --- Try httpx; fallback to requests (auto) ---
try:
    import httpx  # type: ignore
    _HAS_HTTPX = True
except Exception:
    import requests  # type: ignore
    _HAS_HTTPX = False

app = FastAPI(
    title="DhanHQ API Proxy",
    version="2.0.0",
    description="Pass-through proxy for DhanHQ v2 with CORS and env-based config",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------ Helpers ------------
def _pick_env() -> Dict[str, Optional[str]]:
    """
    Decide LIVE/SANDBOX and pick token/client/base_url from env.
    Defaults to LIVE base if sandbox URL not provided.
    """
    env = (os.getenv("DHAN_ENV") or "LIVE").strip().upper()
    if env not in {"SANDBOX", "LIVE"}:
        env = "LIVE"

    if env == "LIVE":
        token = os.getenv("DHAN_LIVE_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_LIVE_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")
        base_url = os.getenv("DHAN_LIVE_BASE_URL") or "https://api.dhan.co/v2"
    else:
        token = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_SANDBOX_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")
        # Dhan का official sandbox public नहीं होता – अगर दिया है तो use करें, वरना LIVE URL पर ही proxy करें
        base_url = os.getenv("DHAN_SANDBOX_BASE_URL") or "https://api.dhan.co/v2"

    return {"env": env, "token": token, "client_id": client_id, "base_url": base_url}

def _make_headers(token: str, client_id: str) -> Dict[str, str]:
    return {
        "access-token": token,
        "client-id": client_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

async def _request_upstream(
    method: str,
    path: str,
    json_body: Optional[Dict[str, Any]] = None,
    query_params: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """
    Core proxy: sends request to DhanHQ and relays response.
    Uses httpx (async) if available; else requests in a thread.
    """
    cfg = _pick_env()
    token, client_id, base_url = cfg["token"], cfg["client_id"], cfg["base_url"]

    if not token or not client_id:
        return JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": "Missing Dhan credentials",
                "details": {
                    "env": cfg["env"],
                    "token_present": bool(token),
                    "client_id_present": bool(client_id),
                },
            },
        )

    url = f"{base_url}{path}"
    headers = _make_headers(token, client_id)

    # httpx path (async)
    if _HAS_HTTPX:
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.request(
                    method.upper(), url, headers=headers,
                    json=json_body, params=query_params
                )
            except httpx.HTTPError as exc:
                return JSONResponse(
                    status_code=502,
                    content={
                        "ok": False,
                        "error": "Upstream HTTP error",
                        "details": str(exc),
                        "upstream": {"url": url},
                    },
                )

            try:
                data = resp.json()
                return JSONResponse(status_code=resp.status_code, content=data)
            except ValueError:
                return JSONResponse(
                    status_code=resp.status_code,
                    content={
                        "ok": False,
                        "error": "Non-JSON response from Dhan",
                        "status_code": resp.status_code,
                        "text": resp.text,
                    },
                )

    # requests fallback in a thread (non-blocking for asyncio loop)
    def _do():
        try:
            return requests.request(
                method.upper(), url, headers=headers,
                json=json_body, params=query_params, timeout=30
            )
        except requests.RequestException as exc:  # type: ignore
            return exc

    resp = await asyncio.to_thread(_do)
    if isinstance(resp, Exception):
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "error": "Upstream HTTP error",
                "details": str(resp),
                "upstream": {"url": url},
            },
        )

    try:
        data = resp.json()
        return JSONResponse(status_code=resp.status_code, content=data)
    except ValueError:
        return JSONResponse(
            status_code=resp.status_code,
            content={
                "ok": False,
                "error": "Non-JSON response from Dhan",
                "status_code": resp.status_code,
                "text": resp.text,
            },
        )

# ------------ Root & Health ------------
@app.get("/", response_class=PlainTextResponse, tags=["Health & Status"])
async def root():
    return "DhanHQ Proxy is running. See /docs"

@app.get("/health", tags=["Health & Status"])
async def health():
    return {"ok": True}

@app.get("/broker_status", tags=["Health & Status"])
async def broker_status():
    cfg = _pick_env()
    return {
        "env": cfg["env"],
        "base_url": cfg["base_url"],
        "token_present": bool(cfg["token"]),
        "client_id_present": bool(cfg["client_id"]),
        "has_httpx": _HAS_HTTPX,
        "mode": os.getenv("MODE", "DRY").upper(),
    }

# ------------ Market Data (Market Quote) ------------
@app.post("/marketfeed/ltp", tags=["Market Data"])
async def marketfeed_ltp(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/marketfeed/ltp", json_body=body)

@app.post("/marketfeed/ohlc", tags=["Market Data"])
async def marketfeed_ohlc(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/marketfeed/ohlc", json_body=body)

@app.post("/marketfeed/quote", tags=["Market Data"])
async def marketfeed_quote(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/marketfeed/quote", json_body=body)

# ------------ Charts ------------
@app.post("/charts/intraday", tags=["Data API's"])
async def charts_intraday(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/charts/intraday", json_body=body)

@app.post("/charts/historical", tags=["Data API's"])
async def charts_historical(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/charts/historical", json_body=body)

# ------------ Option Chain ------------
@app.post("/optionchain", tags=["Option Chain"])
async def option_chain(request: Request):
    """
    Body must match Dhan docs exactly:
    {
      "UnderlyingScrip": 13,
      "UnderlyingSeg": "IDX_I",
      "Expiry": "YYYY-MM-DD"
    }
    """
    body = await request.json()
    return await _request_upstream("POST", "/optionchain", json_body=body)

@app.post("/optionchain/expirylist", tags=["Option Chain"])
async def option_chain_expirylist(request: Request):
    """
    {
      "UnderlyingScrip": 13,
      "UnderlyingSeg": "IDX_I"
    }
    """
    body = await request.json()
    return await _request_upstream("POST", "/optionchain/expirylist", json_body=body)

# ------------ Orders ------------
@app.get("/orders", tags=["Orders"])
async def get_orders():
    return await _request_upstream("GET", "/orders")

@app.post("/orders", tags=["Orders"])
async def place_order(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/orders", json_body=body)

@app.get("/orders/{order_id}", tags=["Orders"])
async def get_order_by_id(order_id: str = Path(..., alias="order-id")):
    return await _request_upstream("GET", f"/orders/{order_id}")

@app.put("/orders/{order_id}", tags=["Orders"])
async def modify_order(order_id: str, request: Request):
    body = await request.json()
    return await _request_upstream("PUT", f"/orders/{order_id}", json_body=body)

@app.delete("/orders/{order_id}", tags=["Orders"])
async def cancel_order(order_id: str):
    return await _request_upstream("DELETE", f"/orders/{order_id}")

@app.post("/orders/slicing", tags=["Orders"])
async def place_slice_order(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/orders/slicing", json_body=body)

@app.get("/orders/external/{correlation_id}", tags=["Orders"])
async def get_order_by_correlation(correlation_id: str):
    return await _request_upstream("GET", f"/orders/external/{correlation_id}")

# Trades
@app.get("/trades", tags=["Orders"])
async def get_all_trades():
    return await _request_upstream("GET", "/trades")

@app.get("/trades/{order_id}", tags=["Orders"])
async def get_trades_by_order(order_id: str):
    return await _request_upstream("GET", f"/trades/{order_id}")

@app.get("/trades/{from_date}/{to_date}/{page_number}", tags=["Orders"])
async def get_trade_history(from_date: str, to_date: str, page_number: str):
    return await _request_upstream("GET", f"/trades/{from_date}/{to_date}/{page_number}")

# ------------ Super Orders ------------
@app.get("/super/orders", tags=["Super Order"])
async def get_super_orders():
    return await _request_upstream("GET", "/super/orders")

@app.post("/super/orders", tags=["Super Order"])
async def place_super_order(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/super/orders", json_body=body)

@app.put("/super/orders/{order_id}", tags=["Super Order"])
async def modify_super_order(order_id: str, request: Request):
    body = await request.json()
    return await _request_upstream("PUT", f"/super/orders/{order_id}", json_body=body)

@app.delete("/super/orders/{order_id}/{order_leg}", tags=["Super Order"])
async def cancel_super_leg(order_id: str, order_leg: str):
    return await _request_upstream("DELETE", f"/super/orders/{order_id}/{order_leg}")

# ------------ Forever Orders ------------
@app.get("/forever/orders", tags=["Forever Order"])
async def get_forever_orders():
    return await _request_upstream("GET", "/forever/orders")

@app.post("/forever/orders", tags=["Forever Order"])
async def place_forever_order(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/forever/orders", json_body=body)

@app.put("/forever/orders/{order_id}", tags=["Forever Order"])
async def modify_forever_order(order_id: str, request: Request):
    body = await request.json()
    return await _request_upstream("PUT", f"/forever/orders/{order_id}", json_body=body)

@app.delete("/forever/orders/{order_id}", tags=["Forever Order"])
async def cancel_forever_order(order_id: str):
    return await _request_upstream("DELETE", f"/forever/orders/{order_id}")

# ------------ Portfolio ------------
@app.get("/positions", tags=["Portfolio"])
async def get_positions():
    return await _request_upstream("GET", "/positions")

@app.post("/positions/convert", tags=["Portfolio"])
async def convert_position(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/positions/convert", json_body=body)

@app.get("/holdings", tags=["Portfolio"])
async def get_holdings():
    return await _request_upstream("GET", "/holdings")

@app.get("/fundlimit", tags=["Funds"])
async def get_fund_limit():
    return await _request_upstream("GET", "/fundlimit")

# ------------ Statements ------------
@app.get("/ledger", tags=["Statements"])
async def get_ledger(request: Request):
    # Dhan allows optional ?from-date=&to-date= in query
    q = dict(request.query_params)
    return await _request_upstream("GET", "/ledger", query_params=q)

# ------------ EDIS ------------
@app.post("/edis/form", tags=["EDIS"])
async def edis_form(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/edis/form", json_body=body)

@app.post("/edis/bulkform", tags=["EDIS"])
async def edis_bulk_form(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/edis/bulkform", json_body=body)

@app.get("/edis/tpin", tags=["EDIS"])
async def edis_tpin():
    return await _request_upstream("GET", "/edis/tpin")

@app.get("/edis/inquire/{isin}", tags=["EDIS"])
async def edis_inquire(isin: str):
    return await _request_upstream("GET", f"/edis/inquire/{isin}")

# ------------ Trader's Control ------------
@app.get("/killswitch", tags=["Trader's Control"])
async def killswitch_status():
    return await _request_upstream("GET", "/killswitch")

@app.post("/killswitch", tags=["Trader's Control"])
async def killswitch_post(request: Request):
    # Dhan expects killSwitchStatus as query param
    q = dict(request.query_params)
    return await _request_upstream("POST", "/killswitch", query_params=q)

# ------------ Funds / Margin ------------
@app.post("/margincalculator", tags=["Funds"])
async def margin_calculator(request: Request):
    body = await request.json()
    return await _request_upstream("POST", "/margincalculator", json_body=body)

# ------------ Error Handler ------------
@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})

# ------------ Local Run ------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=bool(os.getenv("RELOAD", "")),
    )
