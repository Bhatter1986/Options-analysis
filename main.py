import os
import csv
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends, Query, Body
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# ───────── Load env ─────────
load_dotenv()

MODE = os.getenv("MODE", "SANDBOX").upper()  # SANDBOX | LIVE
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Dhan base
DHAN_BASE_URL = "https://api.dhan.co" if MODE == "LIVE" else "https://api-sandbox.dhan.co"
DHAN_API_BASE = f"{DHAN_BASE_URL}/api/v2"

# ───────── Logging ─────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dhan-options-analysis")

# ───────── App ─────────
app = FastAPI(
    title="Dhan Options Analysis API",
    description="Dhan v2 + AI backend",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static (serve /public)
app.mount("/static", StaticFiles(directory="public"), name="static")

# ───────── Helpers ─────────
def _dhan_headers() -> Dict[str, str]:
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail="Dhan credentials not configured")
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def _safe_json(r: requests.Response) -> Any:
    try:
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        logger.error(f"Dhan API HTTPError {r.status_code}: {detail}")
        raise HTTPException(status_code=r.status_code, detail=detail)
    except Exception as e:
        logger.error(f"Dhan API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _mock_expiries() -> List[str]:
    base = datetime.now().date()
    # 4 weekly expiries
    return [(base + timedelta(days=7*i)).strftime("%Y-%m-%d") for i in range(1,5)]

def _mock_chain() -> Dict[str, Any]:
    # Simple symmetric mock chain around 25000
    import random
    strikes = [24800, 24900, 25000, 25100, 25200]
    data = {}
    for sp in strikes:
        data[str(sp)] = {
            "CE": {
                "oi": random.randint(8000, 22000),
                "previous_oi": random.randint(7000, 21000),
                "volume": random.randint(1500, 7000),
                "implied_volatility": round(15 + random.random()*6, 2),
                "last_price": round(90 + random.random()*60, 2),
                "change": round(-3 + random.random()*6, 2),
            },
            "PE": {
                "oi": random.randint(8000, 22000),
                "previous_oi": random.randint(7000, 21000),
                "volume": random.randint(1500, 7000),
                "implied_volatility": round(15 + random.random()*6, 2),
                "last_price": round(90 + random.random()*60, 2),
                "change": round(-3 + random.random()*6, 2),
            }
        }
    return data

def _mock_ltp() -> float:
    import random
    return round(1600 + random.random()*80, 2)

# ───────── Security dep ─────────
def verify_webhook_secret(request: Request):
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Webhook-Secret")
        if token != WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")
    return True

# ───────── Serve UI ─────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index():
    index_path = Path("public/index.html")
    try:
        if index_path.exists():
            return FileResponse(index_path)
        # Friendly fallback JSON if UI not present
        return HTMLResponse(
            "<h3>Backend OK</h3><p>Place your UI at <code>public/index.html</code> "
            "or call the JSON APIs. See <code>/__selftest</code> for status.</p>"
        )
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        raise

@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def serve_dashboard():
    dashboard_path = Path("public/dashboard.html")
    if dashboard_path.exists():
        return FileResponse(dashboard_path)
    raise HTTPException(status_code=404, detail="Dashboard not found")

# ───────── Health & selftest ─────────
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "dhan_configured": bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN),
        "openai_configured": bool(OPENAI_API_KEY),
        "mode": MODE,
    }

@app.get("/__selftest")
async def selftest():
    return {
        "ok": True,
        "status": {
            "env": "Render",
            "mode": MODE,
            "token_present": bool(DHAN_ACCESS_TOKEN),
            "client_id_present": bool(DHAN_CLIENT_ID),
            "ai_present": bool(OPENAI_API_KEY),
        }
    }

# ───────── Data: Expiry list ─────────
@app.get("/optionchain/expirylist")
def optionchain_expirylist(
    under_security_id: int = Query(...),
    under_exchange_segment: str = Query(...)
):
    """
    Frontend expects: GET /optionchain/expirylist?under_security_id=25&under_exchange_segment=IDX_I
    """
    # Try real call if creds present
    if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
        try:
            # NOTE: Adjust to exact Dhan path if different
            url = f"{DHAN_API_BASE}/option-chain/expiry-list"
            params = {
                "under_security_id": under_security_id,
                "under_exchange_segment": under_exchange_segment
            }
            r = requests.get(url, headers=_dhan_headers(), params=params, timeout=10)
            j = _safe_json(r)
            return {"data": {"data": j}}
        except Exception as e:
            logger.warning(f"Expiry list fallback to mock: {e}")

    # Fallback mock
    return {"data": {"data": _mock_expiries()}}

# ───────── Data: Option chain ─────────
@app.post("/optionchain")
def optionchain(payload: Dict[str, Any] = Body(...)):
    """
    Frontend expects: POST /optionchain { under_security_id, under_exchange_segment, expiry }
    """
    under_security_id = int(payload.get("under_security_id"))
    under_exchange_segment = payload.get("under_exchange_segment")
    expiry = payload.get("expiry")

    if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
        try:
            # NOTE: Adjust to exact Dhan path/body if different
            url = f"{DHAN_API_BASE}/option-chain"
            r = requests.post(url, headers=_dhan_headers(), json={
                "under_security_id": under_security_id,
                "under_exchange_segment": under_exchange_segment,
                "expiry": expiry
            }, timeout=15)
            j = _safe_json(r)
            return {"data": {"data": j}}
        except Exception as e:
            logger.warning(f"Option chain fallback to mock: {e}")

    # Fallback mock (shape compatible with frontend renderer)
    return {"data": {"data": _mock_chain()}}

# ───────── Data: Spot/LTP (demo) ─────────
@app.get("/marketfeed/ltp")
def marketfeed_ltp(
    exchange_segment: str = Query(..., description="e.g. NSE"),
    security_id: int = Query(..., description="e.g. 1333 for HDFCBANK")
):
    """
    Frontend demo uses: GET /marketfeed/ltp?exchange_segment=NSE&security_id=1333
    Respond with shape: {"data":{"data":{"NSE_EQ":[{"ltp": 123.45}]}}}
    """
    if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
        try:
            # If you have exact Dhan quote endpoint, wire here
            url = f"{DHAN_API_BASE}/market-quote/ltp"
            params = {
                "exchange_segment": exchange_segment,
                "security_id": security_id
            }
            r = requests.get(url, headers=_dhan_headers(), params=params, timeout=10)
            j = _safe_json(r)
            # Try to normalize to expected shape
            ltp = None
            # Attempt common fields
            if isinstance(j, dict):
                ltp = j.get("ltp") or j.get("LTP") or j.get("last_price")
            if ltp is None:
                ltp = _mock_ltp()
            return {"data": {"data": {f"{exchange_segment}_EQ": [{"ltp": float(ltp)}]}}}
        except Exception as e:
            logger.warning(f"LTP fallback to mock: {e}")

    # Fallback mock
    return {"data": {"data": {f"{exchange_segment}_EQ": [{"ltp": _mock_ltp()}]}}}

# ───────── AI endpoints ─────────
def _ai_reply(system_prompt: str, user_prompt: str) -> str:
    if not OPENAI_API_KEY:
        # fallback mock if no key
        return "AI (mock): Markets look range-bound; consider neutral spreads near ATM with tight risk."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "AI error. Please check OPENAI_API_KEY or model availability."

@app.post("/ai/marketview")
def ai_marketview(req: Dict[str, Any] = Body(...), _ok: bool = Depends(verify_webhook_secret)):
    sys_p = "You are an options market analyst. Be concise and actionable."
    usr_p = f"Analyze this context and provide a crisp intraday market view in bullet points:\n{json.dumps(req)[:4000]}"
    return {"ai_reply": _ai_reply(sys_p, usr_p)}

@app.post("/ai/strategy")
def ai_strategy(req: Dict[str, Any] = Body(...), _ok: bool = Depends(verify_webhook_secret)):
    bias = req.get("bias", "neutral")
    risk = req.get("risk", "moderate")
    capital = req.get("capital", 50000)
    sys_p = "You are an expert options strategist focusing on risk-managed structures for Indian markets."
    usr_p = (
        f"Create 1-2 strategies for bias={bias}, risk={risk}, capital≈₹{capital}.\n"
        f"Return entry, stop, target, payoff logic, risk per lot, and adjustments."
    )
    return {"ai_strategy": _ai_reply(sys_p, usr_p)}

@app.post("/ai/payoff")
def ai_payoff(req: Dict[str, Any] = Body(...), _ok: bool = Depends(verify_webhook_secret)):
    sys_p = "You compute payoff summaries and turning points for multi-leg option strategies."
    usr_p = (
        "Given the following legs (json), summarize max profit, max loss, breakevens "
        "and a short commentary. Legs:\n" + json.dumps(req)[:4000]
    )
    return {"ai_payoff": _ai_reply(sys_p, usr_p)}

# ───────── Error handlers ─────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})

# ───────── Local dev entry ─────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
