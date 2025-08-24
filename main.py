import os
import json
import logging
from typing import Optional, Any, Dict

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Third-party
import requests
from openai import OpenAI

# -------------------------------------------------
# Load environment
# -------------------------------------------------
load_dotenv()

MODE = os.getenv("MODE", "SANDBOX").upper()          # "LIVE" | "SANDBOX"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")     # (optional) for your own front-end calls
TV_WEBHOOK_SECRET = os.getenv("TV_WEBHOOK_SECRET", "")  # TradingView alerts secret

# Dhan access tokens (optional if you only want demo data)
DHAN_ACCESS_TOKEN = (
    os.getenv("DHAN_LIVE_ACCESS_TOKEN")
    if MODE == "LIVE"
    else os.getenv("DHAN_SANDBOX_ACCESS_TOKEN")
)
DHAN_CLIENT_ID = (
    os.getenv("DHAN_LIVE_CLIENT_ID")
    if MODE == "LIVE"
    else os.getenv("DHAN_SANDBOX_CLIENT_ID")
)

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client: Optional[OpenAI] = None
if OPENAI_API_KEY:
    # Important: OpenAI==1.x style
    client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------------------------------------
# App
# -------------------------------------------------
app = FastAPI(title="Options-analysis (Dhan + AI + TV Webhook)")

# Static: serve / -> public/index.html
if not os.path.isdir("public"):
    os.makedirs("public", exist_ok=True)
app.mount("/static", StaticFiles(directory="public"), name="static")

@app.get("/", include_in_schema=False)
def serve_index():
    index_path = os.path.join("public", "index.html")
    if not os.path.isfile(index_path):
        return JSONResponse({"error": "public/index.html not found"}, status_code=404)
    return FileResponse(index_path)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # loosen for FE experiments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("options-analysis")

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def ok_status():
    return {
        "env": os.getenv("RENDER", "local"),
        "mode": MODE,
        "token_present": bool(DHAN_ACCESS_TOKEN),
        "client_id_present": bool(DHAN_CLIENT_ID),
        "openai_present": bool(OPENAI_API_KEY),
    }

def require_openai():
    if client is None:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY missing or OpenAI not initialized.")

def verify_webhook_secret(req: Request):
    """
    Optional header check: X-Webhook-Secret must match, if WEBHOOK_SECRET is set.
    Frontend me aap is header ko bhejna chaho to bhej sakte ho.
    """
    if not WEBHOOK_SECRET:
        return True
    token = req.headers.get("X-Webhook-Secret")
    if token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid Webhook Secret")
    return True

# -------------------------------------------------
# BASIC / DIAGNOSTIC
# -------------------------------------------------
@app.get("/__selftest")
def selftest():
    return {
        "ok": True,
        "status": ok_status(),
    }

@app.get("/health")
def health():
    return {"status": "ok", "mode": MODE}

@app.get("/broker_status")
def broker_status():
    return ok_status()

# -------------------------------------------------
# AI ENDPOINTS
# (no secret required to avoid FE 401 confusion)
# -------------------------------------------------
@app.post("/ai/marketview")
async def ai_marketview(req: Dict[str, Any]):
    """
    High-level market view + context from your payload
    """
    require_openai()
    try:
        prompt = (
            "You are an options market assistant for Indian markets. "
            "Analyze this context and return concise insights with bullet points, "
            "risk notes, and key strike levels if relevant.\n\n"
            f"Context JSON:\n{json.dumps(req, indent=2)}"
        )
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return {"ok": True, "ai_reply": res.choices[0].message.content}
    except Exception as e:
        logger.exception("AI marketview failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ai/strategy")
async def ai_strategy(req: Dict[str, Any]):
    """
    Recommend an options strategy: include entries, SL, targets, payoff table idea.
    """
    require_openai()
    try:
        prompt = (
            "Given the inputs (bias, risk, capital, symbol/expiry if any), "
            "recommend 1-2 options strategies with lots, strikes, net credit/debit, "
            "max profit/loss, breakevens and monitoring plan. Return in bullet points.\n\n"
            f"Inputs:\n{json.dumps(req, indent=2)}"
        )
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return {"ok": True, "ai_strategy": res.choices[0].message.content}
    except Exception as e:
        logger.exception("AI strategy failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ai/payoff")
async def ai_payoff(req: Dict[str, Any]):
    """
    Explain payoff behaviour (qualitative) based on legs user passes.
    """
    require_openai()
    try:
        prompt = (
            "Explain the payoff of the given option legs (CALL/PUT; buy/sell; strike; premium), "
            "summarize P/L at different underlying prices and list breakevens.\n\n"
            f"Legs JSON:\n{json.dumps(req, indent=2)}"
        )
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return {"ok": True, "ai_payoff": res.choices[0].message.content}
    except Exception as e:
        logger.exception("AI payoff failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ai/test")
async def ai_test():
    require_openai()
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say 'Sudarshan Chakra online'"}],
    )
    return {"ok": True, "ai_test_reply": res.choices[0].message.content}

# -------------------------------------------------
# TRADINGVIEW WEBHOOK
# -------------------------------------------------
class TVAlert(BaseModel):
    secret: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None    # BUY/SELL or custom
    price: Optional[float] = None
    payload: Optional[Dict[str, Any]] = None

@app.post("/tv/webhook")
async def tv_webhook(alert: TVAlert):
    """
    TradingView alert receiver.
    Configure TV → Alert → Webhook URL = https://<your-app>/tv/webhook
    Message JSON (example):
      {"secret":"YOUR_TV_WEBHOOK_SECRET","symbol":"NSE:BANKNIFTY","side":"BUY","price":{{close}}}
    """
    if TV_WEBHOOK_SECRET and (alert.secret != TV_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid TV secret")

    logger.info(f"[TV] alert: {alert.model_dump()}")

    if client is None:
        # Just echo if AI not configured
        return {"ok": True, "ai_reply": "AI disabled. TV alert received.", "echo": alert.model_dump()}

    # Pipe alert to AI for instant trading note
    try:
        prompt = (
            "TradingView alert has arrived. Provide a 3-5 line actionable note. "
            "Include bias, immediate risk, and a simple stop/target idea if possible.\n"
            f"Alert:\n{json.dumps(alert.model_dump(), indent=2)}"
        )
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return {"ok": True, "ai_reply": res.choices[0].message.content}
    except Exception as e:
        logger.exception("TV AI error")
        return {"ok": False, "error": str(e)}

# -------------------------------------------------
# DATA ENDPOINTS (demo fallback)
# NOTE: Replace with real DHAN API if you want live data. These demo endpoints
# return structure compatible with your FE so UI works immediately.
# -------------------------------------------------
@app.get("/marketfeed/ltp")
def marketfeed_ltp(exchange_segment: str = "NSE", security_id: int = 1333):
    """
    Demo: returns mock LTP if token missing. Replace with real DHAN call if needed.
    """
    if DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID and MODE == "LIVE":
        try:
            # Example (update to real Dhan endpoint you use)
            # url = "https://api.dhan.co/some/ltp"
            # headers = {"access-token": DHAN_ACCESS_TOKEN, "client-id": DHAN_CLIENT_ID}
            # r = requests.get(url, headers=headers, timeout=10)
            # return r.json()
            pass
        except Exception as e:
            logger.warning(f"Dhan LTP error: {e}")

    # Demo fallback
    return {
        "status": "success",
        "data": {
            "data": {
                "NSE_EQ": [{"security_id": security_id, "ltp": 1642.55}]
            }
        }
    }

@app.get("/optionchain/expirylist")
def optionchain_expirylist(under_security_id: str, under_exchange_segment: str):
    """
    Demo: returns a rolling list of future expiries in YYYY-MM-DD (like earlier)
    """
    demo = [
        "2025-08-28","2025-09-02","2025-09-09","2025-09-16","2025-09-23","2025-09-30",
        "2025-10-28","2025-12-30","2026-03-31","2026-06-30","2026-12-29","2027-06-29",
        "2027-12-28","2028-06-27","2028-12-26","2029-06-26","2029-12-24","2030-06-25"
    ]
    return {"status": "success", "data": {"status": "success", "data": demo}}

class OCReq(BaseModel):
    under_security_id: int
    under_exchange_segment: str
    expiry: str

@app.post("/optionchain")
def optionchain(req: OCReq):
    """
    Demo: returns a small synthetic chain around 5 strikes. UI uses same shape as earlier.
    Replace with DHAN option-chain call if available.
    """
    # Build symmetric strikes around a mid
    spot = 43800
    step = 100
    strikes = [spot-200, spot-100, spot, spot+100, spot+200]

    def mk_leg(ltp, iv, vol, oi, prev_oi):
        return {
            "last_price": float(ltp),
            "implied_volatility": float(iv),
            "volume": int(vol),
            "oi": int(oi),
            "previous_oi": int(prev_oi),
            "change": round((ltp - (ltp * 0.95)), 2)  # simple change
        }

    data = {}
    for i, sp in enumerate(strikes):
        ce = mk_leg(ltp=50 + i*8, iv=17.0+i*0.3, vol=3500+i*500, oi=9000+i*1100, prev_oi=8500+i*900)
        pe = mk_leg(ltp=60 + (len(strikes)-i-1)*7, iv=18.0+i*0.2, vol=3200+i*450, oi=8700+i*900, prev_oi=8100+i*800)
        data[str(sp)] = {"CE": ce, "PE": pe}

    return {"status": "success", "data": {"status": "success", "data": data}}

# -------------------------------------------------
# Global error handler
# -------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"error": str(exc)})
