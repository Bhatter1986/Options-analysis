# main.py
import os
import sys
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ---- Dhan SDK ----
try:
    from dhanhq import dhanhq, marketfeed, orderupdate
except Exception as e:
    print("DhanHQ SDK import error:", e, file=sys.stderr)
    raise

load_dotenv()

CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "").strip()
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "").strip()

if not CLIENT_ID or not ACCESS_TOKEN:
    print("WARNING: DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN not set", file=sys.stderr)

# Init SDK (lazy, but here global)
dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)

app = FastAPI(title="Options-analysis (Dhan v2 + AI)", version="1.0.0")

# ---- CORS ----
allowed = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed if allowed != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- Helpers ----------
IDX_MAP = {
    "NIFTY": {"under_security_id": "13", "under_exchange_segment": "IDX_I"},
    "BANKNIFTY": {"under_security_id": "25", "under_exchange_segment": "IDX_I"},
    "FINNIFTY": {"under_security_id": "256265", "under_exchange_segment": "IDX_I"},  # update if needed
}

def ok(data: Any) -> Dict[str, Any]:
    return {"status": "success", "data": data}

def fail(detail: str, code: int = 400) -> None:
    raise HTTPException(status_code=code, detail=detail)

# --------- Models ----------
class PlaceOrderReq(BaseModel):
    security_id: str
    exchange_segment: str
    transaction_type: str  # dhan.BUY / dhan.SELL
    quantity: int
    order_type: str        # dhan.MARKET / dhan.LIMIT / etc.
    product_type: str      # dhan.INTRA / dhan.CNC / etc.
    price: Optional[float] = 0.0
    trigger_price: Optional[float] = 0.0
    validity: Optional[str] = None
    link_id: Optional[str] = None

class ModifyOrderReq(BaseModel):
    order_id: str
    order_type: Optional[str] = None
    leg_name: Optional[str] = None
    quantity: Optional[int] = None
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    disclosed_quantity: Optional[int] = None

class ForeverOrderReq(BaseModel):
    security_id: str
    exchange_segment: str
    transaction_type: str
    product_type: str
    product: str           # SINGLE / OCO
    quantity: int
    price: float
    trigger_price: float
    remarks: Optional[str] = None

# --------- Basic ----------
@app.get("/health")
def health():
    return ok({"app": app.title, "version": app.version})

@app.get("/broker_status")
def broker_status():
    return ok({
        "mode": "LIVE",
        "token_present": bool(ACCESS_TOKEN),
        "client_id_present": bool(CLIENT_ID),
        "openai_present": bool(os.getenv("OPENAI_API_KEY", "").strip()),
    })

@app.get("/__selftest")
def selftest():
    status = {
        "env": True,
        "mode": "LIVE",
        "token_present": bool(ACCESS_TOKEN),
        "client_id_present": bool(CLIENT_ID),
        "openai_present": bool(os.getenv("OPENAI_API_KEY", "").strip()),
    }
    sample = {}
    try:
        # Try a lightweight call – get funds (doesn't require params)
        funds = dhan.get_fund_limits()
        sample["funds_ok"] = True if isinstance(funds, dict) else False
    except Exception as e:
        sample["funds_ok"] = False
        sample["error"] = str(e)
    return {"status": "success", "data": {"status": status, "sample": sample}}

# --------- Market Quote / Data ----------
@app.get("/market/quote")
def market_quote(
    security_id: str = Query(..., description="e.g., '13' for NIFTY underlying OR script id"),
    exchange_segment: str = Query(..., description="e.g., 'IDX_I', 'NSE', etc."),
    mode: str = Query("full", description="ticker|quote|full (SDK handles internally)")
):
    try:
        data = dhan.get_quote(security_id, exchange_segment)
        return ok(data)
    except Exception as e:
        fail(f"quote error: {e}", 502)

@app.get("/charts/intraday")
def charts_intraday(
    security_id: str = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: str = Query("OPTIDX")
):
    try:
        data = dhan.intraday_minute_data(security_id, exchange_segment, instrument_type)
        return ok(data)
    except Exception as e:
        fail(f"intraday error: {e}", 502)

@app.get("/charts/historical")
def charts_historical(
    security_id: str = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: str = Query("OPTIDX"),
    expiry_code: Optional[str] = None,
    from_date: Optional[str] = None,  # 'YYYY-MM-DD'
    to_date: Optional[str] = None,
    interval: Optional[str] = None    # depends on SDK support
):
    try:
        data = dhan.historical_daily_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            expiry_code=expiry_code or "",
            from_date=from_date or "",
            to_date=to_date or "",
        )
        return ok(data)
    except Exception as e:
        fail(f"historical error: {e}", 502)

# --------- Option Chain / Expiry ----------
@app.get("/option/expirylist")
def option_expirylist(
    under_security_id: Optional[str] = Query(None),
    under_exchange_segment: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None, description="Shortcut: NIFTY/BANKNIFTY/FINNIFTY")
):
    try:
        if symbol:
            sym = symbol.upper()
            if sym not in IDX_MAP:
                fail("Unknown symbol; use NIFTY/BANKNIFTY/FINNIFTY")
            under_security_id = IDX_MAP[sym]["under_security_id"]
            under_exchange_segment = IDX_MAP[sym]["under_exchange_segment"]

        if not under_security_id or not under_exchange_segment:
            fail("under_security_id & under_exchange_segment required")

        data = dhan.expiry_list(
            under_security_id=under_security_id,
            under_exchange_segment=under_exchange_segment
        )
        return ok(data)
    except Exception as e:
        fail(f"expirylist error: {e}", 502)

@app.get("/optionchain")
def option_chain(
    under_security_id: Optional[str] = Query(None),
    under_exchange_segment: Optional[str] = Query(None),
    expiry_code: str = Query(...),
    symbol: Optional[str] = Query(None)
):
    try:
        if symbol:
            sym = symbol.upper()
            if sym not in IDX_MAP:
                fail("Unknown symbol; use NIFTY/BANKNIFTY/FINNIFTY")
            under_security_id = IDX_MAP[sym]["under_security_id"]
            under_exchange_segment = IDX_MAP[sym]["under_exchange_segment"]

        if not under_security_id or not under_exchange_segment:
            fail("under_security_id & under_exchange_segment required")

        data = dhan.option_chain(
            under_security_id=under_security_id,
            under_exchange_segment=under_exchange_segment,
            expiry_code=expiry_code
        )
        return ok(data)
    except Exception as e:
        fail(f"optionchain error: {e}", 502)

# --------- Orders ----------
@app.post("/orders/place")
def orders_place(req: PlaceOrderReq):
    try:
        res = dhan.place_order(
            security_id=req.security_id,
            exchange_segment=req.exchange_segment,
            transaction_type=req.transaction_type,
            quantity=req.quantity,
            order_type=req.order_type,
            product_type=req.product_type,
            price=req.price or 0,
            trigger_price=req.trigger_price or 0,
            validity=req.validity,
            link_id=req.link_id
        )
        return ok(res)
    except Exception as e:
        fail(f"place_order error: {e}", 502)

@app.post("/orders/modify")
def orders_modify(req: ModifyOrderReq):
    try:
        res = dhan.modify_order(
            order_id=req.order_id,
            order_type=req.order_type,
            leg_name=req.leg_name,
            quantity=req.quantity,
            price=req.price,
            trigger_price=req.trigger_price,
            disclosed_quantity=req.disclosed_quantity
        )
        return ok(res)
    except Exception as e:
        fail(f"modify_order error: {e}", 502)

@app.post("/orders/cancel")
def orders_cancel(order_id: str = Body(..., embed=True)):
    try:
        res = dhan.cancel_order(order_id)
        return ok(res)
    except Exception as e:
        fail(f"cancel_order error: {e}", 502)

@app.get("/orders/{order_id}")
def order_by_id(order_id: str):
    try:
        res = dhan.get_order_by_id(order_id)
        return ok(res)
    except Exception as e:
        fail(f"get_order_by_id error: {e}", 502)

@app.get("/orders")
def order_list():
    try:
        res = dhan.get_order_list()
        return ok(res)
    except Exception as e:
        fail(f"get_order_list error: {e}", 502)

@app.get("/tradebook/{order_id}")
def tradebook(order_id: str):
    try:
        res = dhan.get_trade_book(order_id)
        return ok(res)
    except Exception as e:
        fail(f"tradebook error: {e}", 502)

@app.get("/tradehistory")
def tradehistory(from_date: Optional[str] = None, to_date: Optional[str] = None, page_number: int = 0):
    try:
        res = dhan.get_trade_history(from_date or "", to_date or "", page_number)
        return ok(res)
    except Exception as e:
        fail(f"tradehistory error: {e}", 502)

# --------- Portfolio / Funds ----------
@app.get("/positions")
def positions():
    try:
        res = dhan.get_positions()
        return ok(res)
    except Exception as e:
        fail(f"positions error: {e}", 502)

@app.get("/holdings")
def holdings():
    try:
        res = dhan.get_holdings()
        return ok(res)
    except Exception as e:
        fail(f"holdings error: {e}", 502)

@app.get("/funds")
def funds():
    try:
        res = dhan.get_fund_limits()
        return ok(res)
    except Exception as e:
        fail(f"funds error: {e}", 502)

# --------- Forever Orders ----------
@app.post("/forever/place")
def forever_place(req: ForeverOrderReq):
    try:
        res = dhan.place_forever(
            security_id=req.security_id,
            exchange_segment=req.exchange_segment,
            transaction_type=req.transaction_type,
            product_type=req.product_type,
            product=req.product,
            quantity=req.quantity,
            price=req.price,
            trigger_price=req.trigger_price,
            remarks=req.remarks
        )
        return ok(res)
    except Exception as e:
        fail(f"forever_place error: {e}", 502)

@app.post("/forever/modify")
def forever_modify(order_id: str = Body(...), price: float = Body(...), trigger_price: float = Body(...)):
    try:
        res = dhan.modify_forever(order_id=order_id, price=price, trigger_price=trigger_price)
        return ok(res)
    except Exception as e:
        fail(f"forever_modify error: {e}", 502)

@app.post("/forever/cancel")
def forever_cancel(order_id: str = Body(..., embed=True)):
    try:
        res = dhan.cancel_forever(order_id)
        return ok(res)
    except Exception as e:
        fail(f"forever_cancel error: {e}", 502)

# --------- eDIS / TPIN ----------
@app.post("/edis/generate_tpin")
def edis_generate_tpin():
    try:
        res = dhan.generate_tpin()
        return ok(res)
    except Exception as e:
        fail(f"generate_tpin error: {e}", 502)

class OpenTPINReq(BaseModel):
    isin: str
    qty: int = 1
    exchange: str = "NSE"

@app.post("/edis/open_browser_for_tpin")
def edis_open_browser_for_tpin(req: OpenTPINReq):
    try:
        res = dhan.open_browser_for_tpin(isin=req.isin, qty=req.qty, exchange=req.exchange)
        return ok(res)
    except Exception as e:
        fail(f"open_browser_for_tpin error: {e}", 502)

@app.get("/edis/inquiry")
def edis_inquiry():
    try:
        res = dhan.edis_inquiry()
        return ok(res)
    except Exception as e:
        fail(f"edis_inquiry error: {e}", 502)

# --------- Utility: exec a minimal SDK method by name (for debugging only) ----------
@app.post("/dhan/exec")
def dhan_exec(method: str = Body(...), payload: Dict[str, Any] = Body(default={})):
    """
    Dangerous in prod; keep it for quick checks. Calls dhan.<method>(**payload).
    """
    try:
        fn = getattr(dhan, method)
        res = fn(**payload) if payload else fn()
        return ok({"method": method, "result": res})
    except Exception as e:
        fail(f"dhan_exec error: {e}", 500)
