from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from datetime import datetime, timezone

app = FastAPI(title="Options-analysis (Dhan v2 + AI)")

# ---------- CORS ----------
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "")
ALLOWED_ORIGINS = [FRONTEND_ORIGIN] if FRONTEND_ORIGIN else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

@app.get("/")
def root():
    return {
        "app": "Options-analysis (Dhan v2 + AI)",
        "mode": os.getenv("MODE", "LIVE"),
        "env": "LIVE",
        "now": now_iso(),
        "endpoints": [
            "/health","/broker_status",
            "/marketfeed/ltp","/marketfeed/ohlc","/marketfeed/quote",
            "/optionchain","/optionchain/expirylist",
            "/orders","/positions","/holdings","/funds",
            "/charts/intraday","/charts/historical",
            "/option_analysis",
            "/ai/marketview","/ai/strategy","/ai/payoff","/ai/test",
            "/__selftest"
        ],
    }

@app.get("/health")
def health():
    return {"ok": True, "now": now_iso()}

@app.get("/broker_status")
def broker_status():
    token_present = bool(os.getenv("DHAN_ACCESS_TOKEN"))
    client_id_present = bool(os.getenv("DHAN_CLIENT_ID"))
    return {"ok": token_present and client_id_present,
            "token_present": token_present,
            "client_id_present": client_id_present}

# -------- Option chain (stub) --------
from typing import Optional

class OCReq(BaseModel):
    under_security_id: int
    under_exchange_segment: str
    expiry: str

@app.post("/optionchain")
def optionchain(req: OCReq):
    sample = {
        "43500": {"CE": {"oi": 12345, "previous_oi": 11111, "volume": 4567,
                         "implied_volatility": 16.8, "last_price": 125.5, "change": 5.25},
                  "PE": {"oi": 9876,  "previous_oi": 10443, "volume": 3456,
                         "implied_volatility": 18.2, "last_price": 84.25, "change": -3.75}},
        "43700": {"CE": {"oi": 9876,  "previous_oi": 7889,  "volume": 6789,
                         "implied_volatility": 17.8, "last_price": 76.25, "change": 3.75},
                  "PE": {"oi": 7654,  "previous_oi": 7999,  "volume": 5432,
                         "implied_volatility": 17.5, "last_price": 105.75, "change": -1.50}},
        "43900": {"CE": {"oi": 7654,  "previous_oi": 6420,  "volume": 5432,
                         "implied_volatility": 18.5, "last_price": 51.75, "change": 2.50},
                  "PE": {"oi": 5432,  "previous_oi": 4976,  "volume": 4321,
                         "implied_volatility": 16.9, "last_price": 145.50,"change": 1.25}},
    }
    return {"ok": True, "data": {"data": sample}, "req": req}

@app.get("/optionchain/expirylist")
def expirylist(under_security_id: int, under_exchange_segment: str):
    return {"ok": True, "data": {"data": ["2025-08-28", "2025-09-04", "2025-09-11"]}}

# -------- Marketfeed (spot stub) --------
@app.get("/marketfeed/ltp")
def marketfeed_ltp(exchange_segment: str, security_id: int):
    return {"ok": True, "data": {"data": {"NSE_EQ": [{"ltp": 1642.55}]}}}

# -------- AI endpoints (stubs) --------
class MarketReq(BaseModel):
    under_security_id: int
    under_exchange_segment: str

class StratReq(MarketReq):
    risk: str = "moderate"
    capital: float = 50000
    bias: str = "neutral"

@app.post("/ai/marketview")
def ai_marketview(req: MarketReq):
    return {
        "ok": True,
        "insight": "Neutral to slightly bullish bias; support 43,500 / resistance 44,200.",
        "confidence": 0.67,
        "req": req,
    }

@app.post("/ai/strategy")
def ai_strategy(req: StratReq):
    if req.bias == "neutral":
        legs = [
            {"side":"SELL","type":"CALL","strike":44200,"price":120.5},
            {"side":"BUY","type":"CALL","strike":44400,"price": 85.25},
            {"side":"SELL","type":"PUT","strike":43400,"price": 95.75},
            {"side":"BUY","type":"PUT","strike":43200,"price": 70.50},
        ]
    elif req.bias == "bullish":
        legs = [
            {"side":"BUY","type":"CALL","strike":43800,"price":220.5},
            {"side":"SELL","type":"CALL","strike":44200,"price":125.75},
        ]
    else:
        legs = [
            {"side":"BUY","type":"PUT","strike":43800,"price":180.25},
            {"side":"SELL","type":"PUT","strike":43400,"price":125.50},
        ]
    return {"ok": True, "strategy": {"bias": req.bias, "risk": req.risk, "legs": legs}, "req": req}

@app.post("/ai/payoff")
def ai_payoff(req: MarketReq):
    pts = [{"px": 42800, "pnl": -3800},
           {"px": 43600, "pnl":  6200},
           {"px": 44400, "pnl": -3800}]
    return {"ok": True, "payoff": pts, "req": req}

@app.get("/__selftest")
def selftest():
    st = broker_status()
    return {
        "status": {
            "mode": os.getenv("MODE", "LIVE"),
            "env": "LIVE",
            "token_present": st["token_present"],
            "client_id_present": st["client_id_present"],
        },
        "samples": {
            "root": "https://options-analysis.onrender.com/",
            "health": "https://options-analysis.onrender.com/health",
            "broker_status": "https://options-analysis.onrender.com/broker_status",
            "expiryllist_sample": "https://options-analysis.onrender.com/optionchain/expirylist?under_security_id=13&under_exchange_segment=IDX_I",
            "ai_test": "https://options-analysis.onrender.com/ai/marketview",
        },
        "now": now_iso(),
    }
