import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from dotenv import load_dotenv
from openai import OpenAI

# Local testing ke liye load dotenv (Render pe auto pickup hoga)
load_dotenv()

app = FastAPI(title="Options-analysis (Dhan v2 + AI)")

# =========================
# ENV CONFIG
# =========================
MODE = os.getenv("MODE", "TEST").upper()

if MODE == "LIVE":
    CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID")
    ACCESS_TOKEN = os.getenv("DHAN_LIVE_ACCESS_TOKEN")
    BASE_URL = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")
else:
    CLIENT_ID = os.getenv("DHAN_SANDBOX_CLIENT_ID")
    ACCESS_TOKEN = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN")
    BASE_URL = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret")
INSTRUMENTS_URL = os.getenv("INSTRUMENTS_URL")

# =========================
# HELPERS
# =========================
HEADERS = {
    "Content-Type": "application/json",
    "access-token": ACCESS_TOKEN,
    "client-id": CLIENT_ID
}

client = OpenAI(api_key=OPENAI_API_KEY)

def dhan_get(path: str, params=None):
    url = f"{BASE_URL}{path}"
    r = requests.get(url, headers=HEADERS, params=params)
    if not r.ok:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()

def dhan_post(path: str, payload: dict):
    url = f"{BASE_URL}{path}"
    r = requests.post(url, headers=HEADERS, json=payload)
    if not r.ok:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()

# =========================
# MODELS
# =========================
class OptionChainRequest(BaseModel):
    under_security_id: int
    under_exchange_segment: str
    expiry: str

class AIRequest(BaseModel):
    prompt: str
    risk: str = "moderate"
    capital: int = 50000

# =========================
# HEALTH / SELFTEST
# =========================
@app.get("/__selftest")
def selftest():
    return {
        "app": "Options-analysis (Dhan v2 + AI)",
        "mode": MODE,
        "env": MODE,
        "endpoints": [
            "/health","/broker_status","/marketfeed/ltp","/marketfeed/ohlc","/marketfeed/quote",
            "/optionchain","/optionchain/expirylist","/orders","/positions","/holdings","/funds",
            "/charts/intraday","/charts/historical",
            "/option_analysis","/ai/marketview","/ai/strategy","/ai/payoff","/ai/test","/__selftest"
        ]
    }

@app.get("/health")
def health():
    return {"status": "ok", "mode": MODE}

# =========================
# BROKER STATUS
# =========================
@app.get("/broker_status")
def broker_status():
    return {
        "client_id_present": bool(CLIENT_ID),
        "token_present": bool(ACCESS_TOKEN),
        "mode": MODE,
        "base_url": BASE_URL
    }

# =========================
# DHAN ENDPOINTS
# =========================
@app.post("/optionchain")
def option_chain(req: OptionChainRequest):
    return dhan_post("/option-chain", req.dict())

@app.get("/optionchain/expirylist")
def option_expirylist(under_security_id: int, under_exchange_segment: str):
    return dhan_get("/option-chain/expiry-list", {
        "under_security_id": under_security_id,
        "under_exchange_segment": under_exchange_segment
    })

@app.get("/orders")
def orders():
    return dhan_get("/orders")

@app.get("/positions")
def positions():
    return dhan_get("/positions")

@app.get("/holdings")
def holdings():
    return dhan_get("/holdings")

@app.get("/funds")
def funds():
    return dhan_get("/funds")

@app.get("/marketfeed/ltp")
def market_ltp(exchange_segment: str, security_id: int):
    return dhan_get("/marketfeed/ltp", {
        "exchange_segment": exchange_segment,
        "security_id": security_id
    })

@app.get("/marketfeed/ohlc")
def market_ohlc(exchange_segment: str, security_id: int):
    return dhan_get("/marketfeed/ohlc", {
        "exchange_segment": exchange_segment,
        "security_id": security_id
    })

@app.get("/marketfeed/quote")
def market_quote(exchange_segment: str, security_id: int):
    return dhan_get("/marketfeed/quote", {
        "exchange_segment": exchange_segment,
        "security_id": security_id
    })

# =========================
# AI ENDPOINTS
# =========================
@app.post("/ai/marketview")
def ai_marketview(req: AIRequest):
    """
    Input: Market prompt (ex: 'NIFTY option chain trend analysis')
    Output: AI summary of sentiment / direction
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a financial analyst specialized in Indian Options (NIFTY, BANKNIFTY)."},
            {"role": "user", "content": f"Analyse the market: {req.prompt}. Risk: {req.risk}, Capital: {req.capital}"}
        ]
    )
    return {"analysis": response.choices[0].message.content}

@app.post("/ai/strategy")
def ai_strategy(req: AIRequest):
    """
    Suggest an options strategy (buy CE/PE, spreads, straddle/strangle etc.)
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert Options Strategy Builder for Indian indices."},
            {"role": "user", "content": f"Suggest an option strategy for {req.prompt} with {req.capital} capital and {req.risk} risk appetite."}
        ]
    )
    return {"strategy": response.choices[0].message.content}

@app.post("/ai/payoff")
def ai_payoff(req: AIRequest):
    """
    Generate payoff explanation
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert options payoff analyzer."},
            {"role": "user", "content": f"Explain the payoff profile for this trade: {req.prompt}"}
        ]
    )
    return {"payoff": response.choices[0].message.content}

@app.post("/ai/test")
def ai_test(req: AIRequest):
    """
    Simple test endpoint
    """
    return {"echo": req.prompt, "risk": req.risk, "capital": req.capital}
