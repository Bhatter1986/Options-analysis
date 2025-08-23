# main.py — DhanHQ passthrough (exact endpoints + exact JSON)
from fastapi import FastAPI, Body, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os, httpx
from typing import Any, Dict, Optional

app = FastAPI(
    title="DhanHQ API Proxy",
    version="2.0",
    description="Forwards EXACT Dhan endpoints & JSON. Only injects headers from env.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# ───────── Env helpers ─────────
def _pick_env() -> Dict[str, Optional[str]]:
    env = (os.getenv("DHAN_ENV") or "SANDBOX").strip().upper()
    if env not in {"SANDBOX", "LIVE"}:
        env = "SANDBOX"

    if env == "LIVE":
        base = os.getenv("DHAN_LIVE_BASE_URL") or "https://api.dhan.co/v2"
        token = os.getenv("DHAN_LIVE_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
        cid = os.getenv("DHAN_LIVE_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")
    else:
        base = os.getenv("DHAN_SANDBOX_BASE_URL") or "https://sandbox.dhan.co/v2"
        token = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
        cid = os.getenv("DHAN_SANDBOX_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")

    return {"env": env, "base_url": base, "token": token, "client_id": cid}

def _headers(token: str, client_id: str) -> Dict[str, str]:
    return {
        "access-token": token,
        "client-id": client_id,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

async def _post(path: str, body: Dict[str, Any]) -> JSONResponse:
    cfg = _pick_env()
    base, token, cid = cfg["base_url"], cfg["token"], cfg["client_id"]
    if not token or not cid:
        raise HTTPException(
            status_code=401,
            detail={
                "ok": False,
                "error": "Missing Dhan credentials",
                "env": cfg["env"],
                "token_present": bool(token),
                "client_id_present": bool(cid),
            },
        )
    url = f"{base.rstrip('/')}{path}"
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.post(url, json=body, headers=_headers(token, cid))
        except httpx.HTTPError as exc:
            return JSONResponse(status_code=502, content={
                "ok": False, "error": "Upstream HTTP error", "details": str(exc), "upstream": {"url": url}
            })
    try:
        return JSONResponse(status_code=r.status_code, content=r.json())
    except ValueError:
        return JSONResponse(status_code=r.status_code, content={
            "ok": False, "error": "Non-JSON response from Dhan", "status_code": r.status_code, "text": r.text
        })

# ───────── Health / Status ─────────
@app.get("/health")
def health(): return {"ok": True}

@app.get("/broker_status")
def broker_status():
    cfg = _pick_env()
    return {
        "env": cfg["env"],
        "base_url": cfg["base_url"],
        "token_present": bool(cfg["token"]),
        "client_id_present": bool(cfg["client_id"]),
    }

# ───────── Dhan OFFICIAL endpoints (exact paths & body) ─────────
# Market Quote (docs: /market-quote)
@app.post("/marketfeed/ltp")
async def marketfeed_ltp(body: Dict[str, Any] = Body(...)):
    # Expect EXACT Dhan body, e.g. { "NSE_EQ":[11536], "NSE_FNO":[49081,49082] }
    return await _post("/marketfeed/ltp", body)

@app.post("/marketfeed/ohlc")
async def marketfeed_ohlc(body: Dict[str, Any] = Body(...)):
    return await _post("/marketfeed/ohlc", body)

@app.post("/marketfeed/quote")
async def marketfeed_quote(body: Dict[str, Any] = Body(...)):
    return await _post("/marketfeed/quote", body)

# Option Chain (docs: /option-chain)
@app.post("/optionchain")
async def optionchain(body: Dict[str, Any] = Body(...)):
    # Expect EXACT Dhan body, e.g. { "UnderlyingScrip":13, "UnderlyingSeg":"IDX_I", "Expiry":"YYYY-MM-DD" }
    return await _post("/optionchain", body)

@app.post("/optionchain/expirylist")
async def optionchain_expirylist(body: Dict[str, Any] = Body(...)):
    # Expect EXACT Dhan body, e.g. { "UnderlyingScrip":13, "UnderlyingSeg":"IDX_I" }
    return await _post("/optionchain/expirylist", body)

# Local run
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=bool(os.getenv("RELOAD", "")))
