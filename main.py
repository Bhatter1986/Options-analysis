# main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Optional, Any, List
import httpx, os, time

# ---- App ----
app = FastAPI(
    title="Options-Analysis – Dhan Proxy",
    version="2.0.0",
    description="Proxy for DhanHQ v2 with TEST mode & diagnostics",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- MODE / ENV ----
START_TS = int(time.time())
LAST_UPSTREAM: Dict[str, Any] = {}

def _pick_env() -> Dict[str, Optional[str]]:
    env = (os.getenv("DHAN_ENV") or "SANDBOX").strip().upper()
    if env not in {"SANDBOX","LIVE"}: env = "SANDBOX"

    if env == "LIVE":
        token     = os.getenv("DHAN_LIVE_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_LIVE_CLIENT_ID")    or os.getenv("DHAN_CLIENT_ID")
        base_url  = os.getenv("DHAN_LIVE_BASE_URL")     or "https://api.dhan.co/v2"
    else:
        token     = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_SANDBOX_CLIENT_ID")    or os.getenv("DHAN_CLIENT_ID")
        base_url  = os.getenv("DHAN_SANDBOX_BASE_URL")     or "https://sandbox.dhan.co/v2"

    return {"env": env, "token": token, "client_id": client_id, "base_url": base_url}

def _make_headers(token: str, client_id: str) -> Dict[str,str]:
    return {
        "access-token": token,
        "client-id": client_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

# ---- Proxy Core ----
async def _proxy_request(method: str, path: str, payload: Any = None) -> JSONResponse:
    mode = (os.getenv("MODE") or "LIVE").strip().upper()
    cfg = _pick_env()

    # TEST MODE → return mock from testmode.py
    if mode == "TEST":
        from testmode import mock_dispatch  # local import
        mocked = mock_dispatch(method, path, payload)
        return JSONResponse(status_code=200, content={"mode":"TEST","data": mocked})

    # LIVE / SANDBOX → call upstream
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
    timeout = httpx.Timeout(20.0, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            if method == "POST":
                resp = await client.post(url, json=payload, headers=headers)
            elif method == "GET":
                # for GET with query dict
                if isinstance(payload, dict) and payload:
                    resp = await client.get(url, params=payload, headers=headers)
                else:
                    resp = await client.get(url, headers=headers)
            elif method == "PUT":
                resp = await client.put(url, json=payload, headers=headers)
            elif method == "DELETE":
                resp = await client.delete(url, headers=headers)
            else:
                return JSONResponse(status_code=400, content={"ok":False,"error":f"Unsupported method: {method}"})
        except httpx.HTTPError as exc:
            return JSONResponse(
                status_code=502,
                content={"ok":False, "error":"Upstream HTTP error", "details":str(exc), "upstream":{"url":url}},
            )

    # record last upstream info (for /__last_upstream)
    LAST_UPSTREAM.update({
        "ts": int(time.time()), "method": method, "url": url, "status": resp.status_code
    })

    try:
        data = resp.json()
        return JSONResponse(status_code=resp.status_code, content=data)
    except ValueError:
        return JSONResponse(
            status_code=resp.status_code,
            content={"ok":False,"error":"Non-JSON response from Dhan","status_code":resp.status_code,"text":resp.text},
        )

# ---- Schemas ----
class MarketfeedRequest(BaseModel):
    NSE_EQ:  Optional[List[int]] = Field(None)
    NSE_FNO: Optional[List[int]] = Field(None)
    BSE_EQ:  Optional[List[int]] = Field(None)

class OptionChainReq(BaseModel):
    UnderlyingScrip: int
    UnderlyingSeg: str
    Expiry: Optional[str] = None

class ExpiryListReq(BaseModel):
    UnderlyingScrip: int
    UnderlyingSeg: str

class IntradayChartsRequest(BaseModel):
    securityId: str
    exchangeSegment: str
    instrument: str
    interval: str
    oi: Optional[bool] = False
    fromDate: Optional[str] = None
    toDate: Optional[str] = None

class HistoricalChartsRequest(BaseModel):
    securityId: str
    exchangeSegment: str
    instrument: str
    expiryCode: Optional[int] = None
    oi: Optional[bool] = False
    fromDate: Optional[str] = None
    toDate: Optional[str] = None

# ---- Health / Diagnostics ----
@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/broker_status")
async def broker_status():
    cfg = _pick_env()
    return {
        "mode": (os.getenv("MODE") or "LIVE").upper(),
        "env": cfg["env"],
        "base_url": cfg["base_url"],
        "has_creds": bool(cfg["token"] and cfg["client_id"]),
        "token_present": bool(cfg["token"]),
        "client_id_present": bool(cfg["client_id"]),
    }

@app.get("/__version")
async def __version():
    return {
        "app": app.title,
        "version": app.version,
        "mode": (os.getenv("MODE") or "LIVE").upper(),
        "env": (_pick_env()["env"]),
        "uptime_sec": int(time.time()) - START_TS,
    }

@app.get("/__routes")
async def __routes():
    return sorted([r.path for r in app.routes])

@app.post("/__echo")
async def __echo(body: dict):
    return {"received": body}

@app.get("/__last_upstream")
async def __last_upstream():
    return LAST_UPSTREAM or {"note": "no upstream calls yet (maybe MODE=TEST?)"}

# ---- Marketfeed ----
@app.post("/marketfeed/ltp")
async def marketfeed_ltp(body: MarketfeedRequest):
    return await _proxy_request("POST", "/marketfeed/ltp", body.model_dump(exclude_none=True))

@app.post("/marketfeed/ohlc")
async def marketfeed_ohlc(body: MarketfeedRequest):
    return await _proxy_request("POST", "/marketfeed/ohlc", body.model_dump(exclude_none=True))

@app.post("/marketfeed/quote")
async def marketfeed_quote(body: MarketfeedRequest):
    return await _proxy_request("POST", "/marketfeed/quote", body.model_dump(exclude_none=True))

# ---- Option Chain ----
@app.post("/optionchain")
async def optionchain(body: OptionChainReq):
    # LIVE/SANDBOX: Dhan needs Expiry. If missing, advise client to hit /optionchain/expirylist first.
    return await _proxy_request("POST", "/optionchain", body.model_dump(exclude_none=True))

@app.post("/optionchain/expirylist")
async def optionchain_expirylist(body: ExpiryListReq):
    return await _proxy_request("POST", "/optionchain/expirylist", body.model_dump(exclude_none=True))

# ---- Portfolio / Funds ----
@app.get("/orders")
async def orders():
    return await _proxy_request("GET", "/orders")

@app.get("/positions")
async def positions():
    return await _proxy_request("GET", "/positions")

@app.get("/holdings")
async def holdings():
    return await _proxy_request("GET", "/holdings")

@app.get("/funds")
async def funds():
    return await _proxy_request("GET", "/funds")

# ---- Charts ----
@app.post("/charts/intraday")
async def charts_intraday(body: IntradayChartsRequest):
    return await _proxy_request("POST", "/charts/intraday", body.model_dump(exclude_none=True))

@app.post("/charts/historical")
async def charts_historical(body: HistoricalChartsRequest):
    return await _proxy_request("POST", "/charts/historical", body.model_dump(exclude_none=True))

# ---- Local run ----
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT","8000")))
