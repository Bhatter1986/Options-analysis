import os
import csv
import json
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel
from dhanhq import dhanhq

# =============================
# ENV Vars
# =============================
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# Init SDK
dhan = dhanhq(client_id=DHAN_CLIENT_ID, access_token=DHAN_ACCESS_TOKEN)

# FastAPI app
app = FastAPI(title="Options-analysis (Dhan v2 + AI)", version="2.0")

# =============================
# Instrument Lookup (CSV)
# =============================
INSTRUMENTS_FILE = "instruments.csv"  # path to uploaded file

def lookup_instrument(symbol: str):
    """Auto lookup symbol → security_id + exchange_segment"""
    with open(INSTRUMENTS_FILE, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("symbol") == symbol.upper():
                return {
                    "security_id": row.get("security_id"),
                    "exchange_segment": row.get("exchange_segment"),
                }
    return None

# =============================
# MODELS
# =============================
class OptionChainRequest(BaseModel):
    symbol: Optional[str] = None
    under_security_id: Optional[str] = None
    under_exchange_segment: Optional[str] = None
    expiry: str

class OrderRequest(BaseModel):
    security_id: str
    exchange_segment: str
    transaction_type: str
    quantity: int
    order_type: str
    product_type: str
    price: Optional[float] = 0.0

# =============================
# ROUTES
# =============================

@app.get("/")
def root():
    return {"status": "success", "data": {"message": "Options-analysis (Dhan v2 + AI) running", "docs": "/docs"}}

@app.get("/health")
def health():
    return {"status": "ok", "mode": "LIVE"}

@app.get("/broker_status")
def broker_status():
    return {"status": "success", "data": dhan.get_broker_status()}

# ---------- OPTION ----------
@app.get("/option/expirylist")
def option_expirylist(symbol: Optional[str] = None, under_security_id: Optional[str] = None, under_exchange_segment: Optional[str] = None):
    try:
        if symbol:
            inst = lookup_instrument(symbol)
            if not inst:
                return {"status": "error", "error": f"Symbol {symbol} not found"}
            under_security_id = inst["security_id"]
            under_exchange_segment = inst["exchange_segment"]

        res = dhan.expiry_list(under_security_id, under_exchange_segment)
        return {"status": "success", "data": res}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/option/chain")
def option_chain(req: OptionChainRequest):
    try:
        under_security_id = req.under_security_id
        under_exchange_segment = req.under_exchange_segment
        if req.symbol:
            inst = lookup_instrument(req.symbol)
            if not inst:
                return {"status": "error", "error": f"Symbol {req.symbol} not found"}
            under_security_id = inst["security_id"]
            under_exchange_segment = inst["exchange_segment"]

        res = dhan.option_chain(under_security_id, under_exchange_segment, req.expiry)
        return {"status": "success", "data": res}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ---------- MARKET ----------
@app.get("/market/quote")
def market_quote(symbol: str):
    try:
        inst = lookup_instrument(symbol)
        if not inst:
            return {"status": "error", "error": f"Symbol {symbol} not found"}
        res = dhan.market_quote(inst["exchange_segment"], inst["security_id"])
        return {"status": "success", "data": res}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ---------- ORDERS ----------
@app.post("/orders/place")
def orders_place(req: OrderRequest):
    try:
        res = dhan.place_order(
            security_id=req.security_id,
            exchange_segment=req.exchange_segment,
            transaction_type=req.transaction_type,
            quantity=req.quantity,
            order_type=req.order_type,
            product_type=req.product_type,
            price=req.price,
        )
        return {"status": "success", "data": res}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/orders")
def get_orders():
    return {"status": "success", "data": dhan.get_order_list()}

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    return {"status": "success", "data": dhan.get_order_by_id(order_id)}

@app.get("/tradebook/{order_id}")
def get_tradebook(order_id: str):
    return {"status": "success", "data": dhan.get_trade_book(order_id)}

@app.get("/tradehistory")
def get_tradehistory(from_date: str, to_date: str, page: int = 0):
    return {"status": "success", "data": dhan.get_trade_history(from_date, to_date, page)}

# ---------- PORTFOLIO ----------
@app.get("/positions")
def positions():
    return {"status": "success", "data": dhan.get_positions()}

@app.get("/holdings")
def holdings():
    return {"status": "success", "data": dhan.get_holdings()}

@app.get("/funds")
def funds():
    return {"status": "success", "data": dhan.get_fund_limits()}

# ---------- HISTORICAL ----------
@app.get("/charts/intraday")
def charts_intraday(symbol: str):
    inst = lookup_instrument(symbol)
    return {"status": "success", "data": dhan.intraday_minute_data(inst["security_id"], inst["exchange_segment"], "IDX_I")}

@app.get("/charts/historical")
def charts_historical(symbol: str, expiry_code: str, from_date: str, to_date: str):
    inst = lookup_instrument(symbol)
    return {"status": "success", "data": dhan.historical_daily_data(inst["security_id"], inst["exchange_segment"], "IDX_I", expiry_code, from_date, to_date)}

# ---------- FOREVER ORDERS ----------
@app.post("/forever/place")
def forever_place(req: OrderRequest):
    return {"status": "success", "data": dhan.place_forever(**req.dict())}

# ---------- EDIS ----------
@app.post("/edis/generate_tpin")
def generate_tpin():
    return {"status": "success", "data": dhan.generate_tpin()}

@app.get("/edis/inquiry")
def edis_inquiry():
    return {"status": "success", "data": dhan.edis_inquiry()}
