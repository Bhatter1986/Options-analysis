# main.py
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import httpx
import os

app = FastAPI(
    title="DhanHQ API Proxy",
    version="2.0",
    description="Proxy service for DhanHQ API with CORS support",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- ENV HELPERS ----------------
def _pick_env() -> Dict[str, Optional[str]]:
    env = (os.getenv("DHAN_ENV") or "SANDBOX").strip().upper()
    if env not in {"SANDBOX", "LIVE"}:
        env = "SANDBOX"

    if env == "LIVE":
        token = os.getenv("DHAN_LIVE_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_LIVE_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")
        base_url = os.getenv("DHAN_LIVE_BASE_URL") or "https://api.dhan.co/v2"
    else:
        token = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_SANDBOX_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")
        base_url = os.getenv("DHAN_SANDBOX_BASE_URL") or "https://sandbox.dhan.co/v2"

    return {"env": env, "token": token, "client_id": client_id, "base_url": base_url}

def _make_headers(token: str, client_id: str) -> Dict[str, str]:
    return {
        "access-token": token,
        "client-id": client_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

async def _proxy_request(method: str, path: str, payload: Any = None) -> JSONResponse:
    """
    Generic proxy to Dhan API. `payload` is sent as JSON for POST/PUT.
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

    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            m = method.upper()
            if m == "POST":
                resp = await client.post(url, json=payload, headers=headers)
            elif m == "GET":
                # For GET, if payload is dict, send as params
                params = payload if isinstance(payload, dict) else None
                resp = await client.get(url, headers=headers, params=params)
            elif m == "PUT":
                resp = await client.put(url, json=payload, headers=headers)
            elif m == "DELETE":
                resp = await client.delete(url, headers=headers)
            else:
                return JSONResponse(
                    status_code=400,
                    content={"ok": False, "error": f"Unsupported HTTP method: {method}"},
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

    # Relay upstream JSON verbatim; if not JSON, wrap it.
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

# ---------------- MODELS (Marketfeed) ----------------
class MarketfeedRequest(BaseModel):
    # Dhan Market Quote accepts multiple segments as keys
    NSE_EQ: Optional[List[int]] = Field(None, description="NSE Equity security IDs")
    NSE_FNO: Optional[List[int]] = Field(None, description="NSE F&O security IDs")
    BSE_EQ: Optional[List[int]] = Field(None, description="BSE Equity security IDs")
    # add more segments if you need
    class Config:
        schema_extra = {
            "example": {"NSE_EQ": [11536], "NSE_FNO": [49081, 49082]}
        }

# ---------------- ROOT & STATUS ----------------
@app.get("/", tags=["Health & Status"])
async def root():
    return {"ok": True, "service": "DhanHQ API Proxy", "docs": "/docs"}

@app.get("/health", tags=["Health & Status"])
async def health():
    return {"ok": True}

@app.get("/broker_status", tags=["Health & Status"])
async def broker_status():
    cfg = _pick_env()
    return {
        "mode": os.getenv("MODE", "DRY").upper(),
        "env": cfg["env"],
        "base_url": cfg["base_url"],
        "token_present": bool(cfg["token"]),
        "client_id_present": bool(cfg["client_id"]),
        "has_creds": bool(cfg["token"] and cfg["client_id"]),
    }

# ---------------- MARKETFEED (LTP/OHLC/QUOTE) ----------------
# LTP
@app.post("/marketfeed/ltp", tags=["Marketfeed"])
@app.post("/marketfeed/ltp/", tags=["Marketfeed"])
async def marketfeed_ltp(request: MarketfeedRequest):
    return await _proxy_request("POST", "/marketfeed/ltp", request.dict(exclude_none=True))

# OHLC
@app.post("/marketfeed/ohlc", tags=["Marketfeed"])
@app.post("/marketfeed/ohlc/", tags=["Marketfeed"])
async def marketfeed_ohlc(request: MarketfeedRequest):
    return await _proxy_request("POST", "/marketfeed/ohlc", request.dict(exclude_none=True))

# Quote (depth)
@app.post("/marketfeed/quote", tags=["Marketfeed"])
@app.post("/marketfeed/quote/", tags=["Marketfeed"])
async def marketfeed_quote(request: MarketfeedRequest):
    return await _proxy_request("POST", "/marketfeed/quote", request.dict(exclude_none=True))

# ---------------- OPTION CHAIN ----------------
# Dhan docs use: { "UnderlyingScrip": 13, "UnderlyingSeg": "IDX_I", "Expiry": "YYYY-MM-DD" }

@app.post("/optionchain", tags=["Option Chain"])
@app.post("/optionchain/", tags=["Option Chain"])
async def option_chain(body: dict = Body(...)):
    # Body is relayed exactly as given
    return await _proxy_request("POST", "/optionchain", body)

@app.post("/optionchain/expirylist", tags=["Option Chain"])
@app.post("/optionchain/expirylist/", tags=["Option Chain"])
async def option_chain_expirylist(body: dict = Body(...)):
    return await _proxy_request("POST", "/optionchain/expirylist", body)

# ---------------- ERROR HANDLER ----------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})

# ---------------- LOCAL RUN ----------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=bool(os.getenv("RELOAD", "")))
