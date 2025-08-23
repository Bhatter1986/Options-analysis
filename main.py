# main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from typing import Any, Dict, Optional

app = FastAPI(title="Options-analysis – Dhan proxy", version="1.0.0")

# --- CORS (safe defaults; allow Hoppscotch/Postman/browser) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Environment helpers ----------
def _pick_env() -> Dict[str, Optional[str]]:
    """
    Decide whether to use SANDBOX or LIVE creds.
    Priority:
      - DHAN_ENV = LIVE|SANDBOX (default SANDBOX)
      - For LIVE:  DHAN_LIVE_ACCESS_TOKEN, DHAN_LIVE_CLIENT_ID, DHAN_LIVE_BASE_URL
      - For SANDBOX: DHAN_SANDBOX_ACCESS_TOKEN, DHAN_SANDBOX_CLIENT_ID, DHAN_SANDBOX_BASE_URL
    Fallbacks:
      - DHAN_ACCESS_TOKEN, DHAN_CLIENT_ID
      - BASE URL defaults to api.dhan.co/v2 (LIVE) or sandbox.dhan.co/v2 (SANDBOX)
    """
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

    return {
        "env": env,
        "token": token,
        "client_id": client_id,
        "base_url": base_url,
    }


def _make_headers(token: str, client_id: str) -> Dict[str, str]:
    return {
        "access-token": token,
        "client-id": client_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _proxy_post(path: str, payload: Dict[str, Any]) -> JSONResponse:
    """
    Forward POST to Dhan v2 keeping their request/response format.
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
            resp = await client.post(url, json=payload, headers=headers)
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

    # Try to relay JSON verbatim; if not JSON, send text
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


# ---------- Health & Status ----------
@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/broker_status")
async def broker_status():
    cfg = _pick_env()
    return {
        "mode": os.getenv("MODE", "DRY").upper(),
        "env": cfg["env"],
        "base_url": cfg["base_url"],
        "has_creds": bool(cfg["token"] and cfg["client_id"]),
        "token_present": bool(cfg["token"]),
        "client_id_present": bool(cfg["client_id"]),
    }


# ---------- Dhan-format endpoints (POST) ----------
# Data APIs → Marketfeed
@app.post("/dhan/marketfeed/ltp")
async def dhan_ltp(req: Request):
    body = await req.json()
    return await _proxy_post("/marketfeed/ltp", body)


@app.post("/dhan/marketfeed/ohlc")
async def dhan_ohlc(req: Request):
    body = await req.json()
    return await _proxy_post("/marketfeed/ohlc", body)


@app.post("/dhan/marketfeed/quote")
async def dhan_quote(req: Request):
    body = await req.json()
    return await _proxy_post("/marketfeed/quote", body)


# Data APIs → Option Chain
@app.post("/dhan/optionchain")
async def dhan_optionchain(req: Request):
    body = await req.json()
    return await _proxy_post("/optionchain", body)


@app.post("/dhan/optionchain/expirylist")
async def dhan_optionchain_expirylist(req: Request):
    body = await req.json()
    return await _proxy_post("/optionchain/expirylist", body)


# ---------- Local run ----------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=bool(os.getenv("RELOAD", "")),
    )
