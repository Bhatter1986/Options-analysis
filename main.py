# main.py
import os, logging, random
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# --- Optional OpenAI (guarded) ---
try:
    from openai import OpenAI
except Exception:  # package may not be installed during first boot
    OpenAI = None  # type: ignore

# ========= ENV & CONFIG =========
load_dotenv()

MODE = os.getenv("MODE", "SANDBOX").upper()  # SANDBOX | LIVE
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

DHAN_ACCESS_TOKEN = (
    os.getenv("DHAN_LIVE_ACCESS_TOKEN") if MODE == "LIVE"
    else os.getenv("DHAN_SANDBOX_ACCESS_TOKEN")
)
DHAN_CLIENT_ID = (
    os.getenv("DHAN_LIVE_CLIENT_ID") if MODE == "LIVE"
    else os.getenv("DHAN_SANDBOX_CLIENT_ID")
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if (OpenAI and OPENAI_API_KEY) else None

# ========= APP =========
app = FastAPI(title="Options-analysis (Dhan v2 + AI)")

# serve /public
app.mount("/static", StaticFiles(directory="public"), name="static")

@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("public/index.html")

@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    return FileResponse("public/dashboard.html")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("options-analysis")

# ========= SECURITY =========
def verify_secret(req: Request):
    token = req.headers.get("X-Webhook-Secret")
    if WEBHOOK_SECRET and token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid Webhook Secret")
    return True

# ========= BASIC =========
@app.get("/health")
def health():
    return {"status": "ok", "mode": MODE}

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "token_present": bool(DHAN_ACCESS_TOKEN),
        "client_id_present": bool(DHAN_CLIENT_ID),
    }

# ========= SELFTEST (FIX) =========
@app.get("/__selftest")
def selftest():
    return {
        "app": "Options-analysis (Dhan v2 + AI)",
        "mode": MODE,
        "env": MODE,
        "now": datetime.utcnow().isoformat(),
        "endpoints": [
            "/health",
            "/broker_status",
            "/marketfeed/ltp",
            "/marketfeed/ohlc",
            "/marketfeed/quote",
            "/optionchain",
            "/optionchain/expirylist",
            "/orders",
            "/positions",
            "/holdings",
            "/funds",
            "/charts/intraday",
            "/charts/historical",
            "/option_analysis",
            "/ai/marketview",
            "/ai/strategy",
            "/ai/payoff",
            "/ai/test",
            "/__selftest",
        ],
    }

# ========= MINIMAL DATA ENDPOINTS (demo-safe) =========
# These return lightweight demo payloads so the UI renders even if Dhan creds are absent.
# Replace with real Dhan SDK calls when you’re ready.

@app.get("/marketfeed/ltp")
def marketfeed_ltp(exchange_segment: str = "NSE", security_id: int = 1333):
    # demo LTP drifting around 1500–1700
    ltp = round(1500 + random.random() * 200, 2)
    return {"data": {"data": {f"{exchange_segment}_EQ": [{"security_id": security_id, "ltp": ltp}]}}}

@app.get("/optionchain/expirylist")
def optionchain_expirylist(under_security_id: int, under_exchange_segment: str = "IDX_I"):
    # demo: next four Thursdays
    today = datetime.utcnow()
    # simple 7-day steps (placeholder)
    exps = [(today.replace(hour=0, minute=0, second=0, microsecond=0) + 
             (i+1) * (today - today)).strftime("%Y-%m-%d") for i in range(4)]
    # stable list if above looks odd on some hosts:
    exps = exps or ["2025-08-28", "2025-09-04", "2025-09-11", "2025-09-18"]
    return {"data": {"data": exps}}

@app.post("/optionchain")
async def optionchain(payload: Dict[str, Any]):
    """
    Expected JSON:
    { "under_security_id": 25, "under_exchange_segment": "IDX_I", "expiry": "YYYY-MM-DD" }
    Returns the minimal shape your front-end expects: { <strike>: { CE:{...}, PE:{...} }, ... }
    """
    # Build a tiny synthetic chain around a center strike
    center = 43800
    strikes = [center + k*100 for k in range(-5, 6)]
    chain: Dict[str, Any] = {}
    for sp in strikes:
        ce_oi = max(0, int(8000 + (center - sp) * 8 + random.randint(-800, 800)))
        pe_oi = max(0, int(8000 + (sp - center) * 8 + random.randint(-800, 800)))
        chain[str(sp)] = {
            "CE": {
                "oi": ce_oi,
                "previous_oi": ce_oi - random.randint(-500, 500),
                "volume": max(0, int(3000 + random.randint(-800, 800))),
                "implied_volatility": round(16 + random.random() * 3, 2),
                "last_price": round(max(5, 200 - abs(center - sp) / 8 + random.randint(-10, 10)), 2),
                "change": round(random.uniform(-10, 10), 2),
            },
            "PE": {
                "oi": pe_oi,
                "previous_oi": pe_oi - random.randint(-500, 500),
                "volume": max(0, int(3000 + random.randint(-800, 800))),
                "implied_volatility": round(16 + random.random() * 3, 2),
                "last_price": round(max(5, 200 - abs(center - sp) / 8 + random.randint(-10, 10)), 2),
                "change": round(random.uniform(-10, 10), 2),
            },
        }
    return {"data": {"data": chain}}

# ========= AI ENDPOINTS =========
def _ensure_ai():
    if not client:
        raise HTTPException(status_code=503, detail="OpenAI key not configured")

@app.post("/ai/marketview")
async def ai_marketview(req: Dict[str, Any], auth: bool = Depends(verify_secret)):
    _ensure_ai()
    try:
        prompt = f"Analyze Indian index options market snapshot and give concise insights. Data: {req}"
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return {"ai_reply": res.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI Error (marketview): {e}")
        raise HTTPException(status_code=500, detail="AI marketview failed")

@app.post("/ai/strategy")
async def ai_strategy(req: Dict[str, Any], auth: bool = Depends(verify_secret)):
    _ensure_ai()
    try:
        prompt = f"Suggest an options strategy with risk, payoff, and adjustments. Inputs: {req}"
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return {"ai_strategy": res.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI Error (strategy): {e}")
        raise HTTPException(status_code=500, detail="AI strategy failed")

@app.post("/ai/payoff")
async def ai_payoff(req: Dict[str, Any], auth: bool = Depends(verify_secret)):
    _ensure_ai()
    try:
        prompt = f"Compute and explain payoff profile (breakevens, max P/L) for: {req}"
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return {"ai_payoff": res.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI Error (payoff): {e}")
        raise HTTPException(status_code=500, detail="AI payoff failed")

@app.post("/ai/test")
async def ai_test(req: Dict[str, Any] = None):
    if not client:
        return {"ai_test_reply": "OpenAI key not set; AI disabled."}
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello, test response"}],
    )
    return {"ai_test_reply": res.choices[0].message.content}

# ========= GLOBAL ERROR =========
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"error": str(exc)})
