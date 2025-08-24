# main.py  — Dhan v2 DATA proxy (single file)
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import os, requests
from typing import Optional, Dict, Any, List

app = FastAPI(title="options-data-api", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- CONFIG ----------
def MODE() -> str:
    m = (os.getenv("MODE") or "LIVE").strip().upper()
    return m if m in {"DRY","LIVE","SANDBOX"} else "LIVE"

def pick(live_key: str, sbx_key: str) -> Optional[str]:
    return os.getenv(live_key) if MODE()=="LIVE" else os.getenv(sbx_key)

def BASE_URL() -> str:
    return (pick("DHAN_LIVE_BASE_URL","DHAN_SANDBOX_BASE_URL") or "").rstrip("/")

def CLIENT_ID() -> str:
    return pick("DHAN_LIVE_CLIENT_ID","DHAN_SANDBOX_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID","")

def ACCESS_TOKEN() -> str:
    return pick("DHAN_LIVE_ACCESS_TOKEN","DHAN_SANDBOX_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN","")

def headers() -> Dict[str,str]:
    if MODE()=="DRY":  # not used, but keep consistent
        return {"accept":"application/json","content-type":"application/json"}
    if not CLIENT_ID() or not ACCESS_TOKEN():
        raise HTTPException(400, "Missing CLIENT_ID or ACCESS_TOKEN env vars.")
    return {
        "accept":"application/json",
        "content-type":"application/json",
        "client-id": CLIENT_ID(),
        "access-token": ACCESS_TOKEN(),
    }

# Dhan REST paths (edit here if vendor changes)
DH_PATHS = {
    "orders": "/orders",
    "positions": "/positions",
    "expiry_list": "/expiry-list",
    "option_chain": "/option-chain",
    "ohlc_data": "/ohlc-data",                   # Market Quote API (LTP/Quote/Full)
    "holdings": "/holdings",
    "fund_limits": "/fund-limits",
    "trade_book": "/tradebook",                  # GET /tradebook?order_id=
    "trade_history": "/trade-history",           # GET /trade-history?from_date=&to_date=&page_number=
    "intraday_minute": "/intraday-minute-data",  # GET with query
    "historical_daily": "/historical-daily-data" # GET with query
}

def is_dry(): return MODE()=="DRY"

def GET(path: str, params: Dict[str,Any]|None=None):
    if is_dry(): return {"status":"success","remarks":"DRY","data":[]}
    url = f"{BASE_URL()}{path}"
    try:
        r = requests.get(url, headers=headers(), params=params, timeout=30)
        if r.status_code>=400: raise HTTPException(r.status_code, r.text)
        return r.json()
    except requests.RequestException as e:
        raise HTTPException(502, f"Upstream GET failed: {e}")

def POST(path: str, payload: Dict[str,Any]):
    if is_dry(): return {"status":"success","remarks":"DRY","data":payload}
    url = f"{BASE_URL()}{path}"
    try:
        r = requests.post(url, headers=headers(), json=payload, timeout=30)
        if r.status_code>=400: raise HTTPException(r.status_code, r.text)
        return r.json()
    except requests.RequestException as e:
        raise HTTPException(502, f"Upstream POST failed: {e}")

# ---------- MODELS (request bodies) ----------
class OptionChainBody(BaseModel):
    under_security_id: int = Field(..., example=13, description="e.g. 13 = NIFTY")
    under_exchange_segment: str = Field(..., example="IDX_I")
    expiry: str = Field(..., example="2025-09-25", description="YYYY-MM-DD from /expiry_list")

class MarketQuoteBody(BaseModel):
    # Dhan docs: {"NSE_EQ":[1333]} etc.
    securities: Dict[str, List[int]]
    # mode choose: ticker_data / ohlc_data / quote_data  (server passes through as-is)

class TradeHistoryQuery(BaseModel):
    from_date: str = Field(..., example="2025-08-01")
    to_date: str = Field(..., example="2025-08-24")
    page_number: int = 0

# ---------- UTILS ----------
def flatten_option_chain(raw: dict) -> dict:
    rows=[]
    try:
        data = raw.get("data") or {}
        strikes = data.get("data") or data.get("option_chain") or []
        for s in strikes:
            strike = s.get("strike_price") or s.get("strike") or s.get("sp")
            ce = s.get("CE") or s.get("call") or {}
            pe = s.get("PE") or s.get("put") or {}
            rows.append({
                "strike": strike,
                "ce_ltp": ce.get("ltp"), "ce_oi": ce.get("oi"), "ce_iv": ce.get("iv"),
                "ce_bid": ce.get("bid"), "ce_ask": ce.get("ask"),
                "pe_ltp": pe.get("ltp"), "pe_oi": pe.get("oi"), "pe_iv": pe.get("iv"),
                "pe_bid": pe.get("bid"), "pe_ask": pe.get("ask"),
            })
    except Exception:
        rows=[]
    return {"rows": rows, "raw": raw}

# ---------- ROUTES ----------
@app.get("/")
def root(): return {"service":"options-data-api","ok":True,"mode":MODE()}

@app.get("/health")
def health(): return {"ok":True}

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE(), "env": MODE(),
        "token_present": bool(ACCESS_TOKEN()),
        "client_id_present": bool(CLIENT_ID()),
        "base_url": BASE_URL(),
    }

# Core account data
@app.get("/orders")    def orders():    return GET(DH_PATHS["orders"])
@app.get("/positions") def positions(): return GET(DH_PATHS["positions"])
@app.get("/holdings")  def holdings():  return GET(DH_PATHS["holdings"])
@app.get("/fund_limits") def fund_limits(): return GET(DH_PATHS["fund_limits"])

# Trade book & history
@app.get("/trade_book")
def trade_book(order_id: str = Query(...)):
    return GET(DH_PATHS["trade_book"], params={"order_id": order_id})

@app.post("/trade_history")
def trade_history(q: TradeHistoryQuery):
    return GET(DH_PATHS["trade_history"], params=q.model_dump())

# Expiry list (GET with query params)
@app.get("/expiry_list")
def expiry_list(
    under_security_id: int = Query(..., example=13),
    under_exchange_segment: str = Query(..., example="IDX_I"),
):
    return GET(DH_PATHS["expiry_list"], params={
        "under_security_id": under_security_id,
        "under_exchange_segment": under_exchange_segment
    })

# Option chain (POST), plus flattened table
@app.post("/option_chain")
def option_chain(body: OptionChainBody):
    return POST(DH_PATHS["option_chain"], payload=body.model_dump())

@app.post("/option_chain_table")
def option_chain_table(body: OptionChainBody):
    raw = option_chain(body)
    return flatten_option_chain(raw)

# Market Quote / LTP / Depth (POST)
@app.post("/market_quote")
def market_quote(body: MarketQuoteBody):
    return POST(DH_PATHS["ohlc_data"], payload=body.model_dump())

# Intraday minute OHLCV (last 5 trading days) — GET with query params
@app.get("/intraday_minute_data")
def intraday_minute_data(
    security_id: int = Query(..., example=1333),
    exchange_segment: str = Query(..., example="NSE"),
    instrument_type: str = Query(..., example="EQ"),  # e.g., EQ / IDX_I / NSE_FNO
    interval: Optional[str] = Query(None, description="Optional timeframe like 1,5,15,25,60 if supported"),
):
    params = {
        "security_id": security_id,
        "exchange_segment": exchange_segment,
        "instrument_type": instrument_type,
    }
    if interval: params["interval"] = interval
    return GET(DH_PATHS["intraday_minute"], params=params)

# Historical daily OHLC — GET with query params
@app.get("/historical_daily_data")
def historical_daily_data(
    security_id: int = Query(..., example=1333),
    exchange_segment: str = Query(..., example="NSE"),
    instrument_type: str = Query(..., example="EQ"),
    expiry_code: Optional[str] = Query(None, description="For derivatives if required"),
    from_date: str = Query(..., example="2025-01-01"),
    to_date: str = Query(..., example="2025-08-24"),
):
    params = {
        "security_id": security_id,
        "exchange_segment": exchange_segment,
        "instrument_type": instrument_type,
        "from_date": from_date,
        "to_date": to_date,
    }
    if expiry_code: params["expiry_code"]=expiry_code
    return GET(DH_PATHS["historical_daily"], params=params)

# ---------- WebSocket placeholders ----------
@app.get("/marketfeed")
def marketfeed_info():
    return {
        "supported": False,
        "why": "Market feed is a client WebSocket stream. Connect from your client using Dhan SDK.",
    }

@app.get("/order_update")
def order_update_info():
    return {
        "supported": False,
        "why": "Order updates are WebSocket events. Consume directly from client.",
    }
