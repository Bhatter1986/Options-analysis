import os
import logging
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# SDKs
from dhanhq import dhanhq  # DhanHQ v2.0.2
from openai import OpenAI   # OpenAI

# ========== CONFIG ==========
load_dotenv()

MODE = os.getenv("MODE", "SANDBOX")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Dhan credentials
CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID" if MODE == "LIVE" else "DHAN_SANDBOX_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_LIVE_ACCESS_TOKEN" if MODE == "LIVE" else "DHAN_SANDBOX_ACCESS_TOKEN")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ai_client = OpenAI(api_key=OPENAI_API_KEY)

# Dhan client
dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)

# ========== APP ==========
app = FastAPI(title="Options Analysis (Dhan v2 + AI)")

app.mount("/static", StaticFiles(directory="public"), name="static")

@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("public/index.html")

# ========== CORS ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== LOGGER ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("options-analysis")

# ========== SECURITY ==========
def verify_secret(req: Request):
    token = req.headers.get("X-Webhook-Secret")
    if WEBHOOK_SECRET and token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid Webhook Secret")
    return True

# ========== BASIC ==========
@app.get("/health")
def health():
    return {"status": "ok", "mode": MODE}

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "client_id": bool(CLIENT_ID),
        "token": bool(ACCESS_TOKEN)
    }

# ========== DHAN ENDPOINTS ==========
@app.get("/instruments")
def instruments():
    """Fetch instrument list"""
    return dhan.instruments()

@app.get("/expiry")
def expiry(symbol: str, exchange_segment: str = "NSE_FNO"):
    """Fetch expiry dates"""
    return dhan.expiry(exchange_segment=exchange_segment, security_id=symbol)

@app.get("/option_chain")
def option_chain(symbol: str, expiry_code: int = 0):
    """Fetch option chain"""
    return dhan.option_chain(symbol, expiry_code=expiry_code)

@app.get("/market_quote")
def market_quote(symbol: str):
    """Fetch market quote snapshot"""
    return dhan.market_quote("NSE_EQ", symbol)

@app.get("/market_depth")
def market_depth(symbol: str):
    """20 market depth"""
    return dhan.market_depth("NSE_EQ", symbol)

@app.get("/historical")
def historical(symbol: str, interval: str = "1d", from_date: str = "2025-01-01", to_date: str = "2025-08-01"):
    """Historical OHLC"""
    return dhan.historical_data("NSE_EQ", symbol, interval, from_date, to_date)

@app.get("/funds")
def funds():
    """Funds / balance"""
    return dhan.get_fund_limits()

@app.get("/portfolio")
def portfolio():
    """Portfolio positions"""
    return dhan.get_positions()

# ========== AI ENDPOINTS ==========
@app.post("/ai/marketview")
async def ai_marketview(req: dict, auth: bool = Depends(verify_secret)):
    prompt = f"Analyze market and give insights: {req}"
    try:
        res = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return {"ai_reply": res.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail="AI marketview failed")

@app.post("/ai/strategy")
async def ai_strategy(req: dict, auth: bool = Depends(verify_secret)):
    prompt = f"Suggest an options trading strategy: {req}"
    try:
        res = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return {"ai_strategy": res.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail="AI strategy failed")

@app.post("/ai/payoff")
async def ai_payoff(req: dict, auth: bool = Depends(verify_secret)):
    prompt = f"Generate payoff analysis for: {req}"
    try:
        res = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return {"ai_payoff": res.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail="AI payoff failed")

@app.post("/ai/test")
async def ai_test(req: dict = {}):
    res = ai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello, AI test check"}]
    )
    return {"ai_test_reply": res.choices[0].message.content}

# ========== ERROR HANDLER ==========
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"error": str(exc)})
