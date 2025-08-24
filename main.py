import os
import json
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ---- Load env ----
load_dotenv()
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "").strip()
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "").strip()

# ---- DhanHQ SDK ----
# pip install dhanhq  (v2.x)
try:
    from dhanhq import dhanhq, marketfeed, orderupdate  # type: ignore
except Exception as e:
    dhanhq = None  # so we can boot and explain in /health
    marketfeed = None
    orderupdate = None
    _import_error = str(e)
else:
    _import_error = None

app = FastAPI(title="Options-analysis (Dhan v2 + AI)", version="2.0")

# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ---- Dhan client (lazy) ----
_dhan_client = None
def dhan_client():
    global _dhan_client
    if _dhan_client is None:
        if dhanhq is None:
            raise RuntimeError(f"dhanhq import failed: {_import_error}")
        if not (DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN):
            raise RuntimeError("DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN missing")
        _dhan_client = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
    return _dhan_client

# ---------- Schemas (minimal) ----------
class PlaceOrderReq(BaseModel):
    security_id: str
    exchange_segment: str  # e.g., "NSE", "NSE_FNO", "MCX", etc.
    transaction_type: str  # dhan.BUY / dhan.SELL
    quantity: int
    order_type: str        # dhan.MARKET / LIMIT / SL / SLM
    product_type: str      # dhan.INTRA / CNC / NRML
    price: Optional[float] = 0
    trigger_price: Optional[float] = 0
    disclosed_quantity: Optional[int] = 0
    validity: Optional[str] = None
    after_market_order: Optional[bool] = False
    bo_profit_value: Optional[float] = None
    bo_stop_loss_Value: Optional[float] = None
    drv_expiry_date: Optional[str] = None
    drv_option_type: Optional[str] = None
    drv_strike_price: Optional[float] = None
    tag: Optional[str] = None

class ModifyOrderReq(BaseModel):
    order_id: str
    order_type: Optional[str] = None
    leg_name: Optional[str] = None
    quantity: Optional[int] = None
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    disclosed_quantity: Optional[int] = None
    validity: Optional[str] = None

class ForeverOrderReq(BaseModel):
    security_id: str
    exchange_segment: str
    transaction_type: str
    product_type: str
    quantity: int
    price: float
    trigger_price: float

# ---------- Helpers ----------
def ok(data: Any, **extra):
    return {"status": "success", "data": data, **extra}

def err(e: Exception, **extra):
    return {"status": "error", "error": str(e), **extra}

# ---------- Meta ----------
@app.get("/")
def root():
    return ok(
        {
            "app": app.title,
            "mode": "LIVE",
            "env": "LIVE",
            "endpoints": [
                "/health", "/broker_status",
                "/market/quote", "/marketfeed/ping",
                "/option/expirylist",
                "/orders", "/orders/place", "/orders/modify", "/orders/cancel",
                "/orders/{order_id}", "/tradebook/{order_id}",
                "/tradehistory",
                "/positions", "/holdings", "/funds",
                "/charts/intraday", "/charts/historical",
                "/forever/place", "/forever/modify", "/forever/cancel",
                "/edis/generate_tpin", "/edis/open_browser_for_tpin", "/edis/inquiry",
                "/dhan/exec", "/__selftest",
            ]
        }
    )

@app.get("/health")
def health():
    return ok({
        "python": os.getenv("PYTHON_VERSION", "3.x"),
        "dhanhq_import": "ok" if _import_error is None else f"failed: {_import_error}",
        "client_id_present": bool(DHAN_CLIENT_ID),
        "token_present": bool(DHAN_ACCESS_TOKEN),
    })

@app.get("/broker_status")
def broker_status():
    return ok({
        "mode": "LIVE",
        "token_present": bool(DHAN_ACCESS_TOKEN),
        "client_id_present": bool(DHAN_CLIENT_ID),
    })

# ---------- Option Chain: Expiry List ----------
@app.get("/option/expirylist")
def expiry_list(
    under_security_id: str = Query(..., description="e.g., 13 for NIFTY, 25 for BANKNIFTY"),
    under_exchange_segment: str = Query(..., description="e.g., IDX_I for Index, NSE for cash underlying"),
):
    """
    Dhan v2 SDK: dhan.expiry_list(under_security_id, under_exchange_segment)
    """
    try:
        d = dhan_client()
        data = d.expiry_list(under_security_id=under_security_id, under_exchange_segment=under_exchange_segment)
        return ok(data)
    except Exception as e:
        return err(e, hint="Check under_security_id & under_exchange_segment")

# ---------- Market Quote (REST snapshot) ----------
@app.get("/market/quote")
def market_quote(
    security_id: str = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: Optional[str] = Query(None, description="If API requires"),
    subscription_type: Optional[int] = Query(None, description="Ticker/Quote/Full mode integers if applicable"),
):
    """
    Snapshot quote via SDK (method name may differ by SDK version).
    If method isn't available, return 501 gracefully.
    """
    try:
        d = dhan_client()
        if hasattr(d, "get_quote"):
            data = d.get_quote(
                security_id=security_id,
                exchange_segment=exchange_segment,
                instrument_type=instrument_type,
                subscription_type=subscription_type,
            )
            return ok(data)
        return {"status": "not_supported", "message": "SDK method get_quote not found in this version"}
    except Exception as e:
        return err(e)

# ---------- Orders ----------
@app.get("/orders")
def orders_list():
    try:
        d = dhan_client()
        return ok(d.get_order_list())
    except Exception as e:
        return err(e)

@app.get("/orders/{order_id}")
def order_by_id(order_id: str):
    try:
        d = dhan_client()
        return ok(d.get_order_by_id(order_id))
    except Exception as e:
        return err(e)

@app.post("/orders/place")
def place_order(req: PlaceOrderReq):
    try:
        d = dhan_client()
        resp = d.place_order(**req.model_dump(exclude_none=True))
        return ok(resp)
    except Exception as e:
        return err(e)

@app.post("/orders/modify")
def modify_order(req: ModifyOrderReq):
    try:
        d = dhan_client()
        resp = d.modify_order(**req.model_dump(exclude_none=True))
        return ok(resp)
    except Exception as e:
        return err(e)

@app.post("/orders/cancel")
def cancel_order(order_id: str = Body(..., embed=True)):
    try:
        d = dhan_client()
        return ok(d.cancel_order(order_id))
    except Exception as e:
        return err(e)

# ---------- Trades ----------
@app.get("/tradebook/{order_id}")
def trade_book(order_id: str):
    try:
        d = dhan_client()
        return ok(d.get_trade_book(order_id))
    except Exception as e:
        return err(e)

@app.get("/tradehistory")
def trade_history(
    from_date: str = Query(..., description="YYYY-MM-DD"),
    to_date: str = Query(..., description="YYYY-MM-DD"),
    page_number: int = Query(0)
):
    try:
        d = dhan_client()
        return ok(d.get_trade_history(from_date, to_date, page_number))
    except Exception as e:
        return err(e)

# ---------- Portfolio ----------
@app.get("/positions")
def positions():
    try:
        d = dhan_client()
        return ok(d.get_positions())
    except Exception as e:
        return err(e)

@app.get("/holdings")
def holdings():
    try:
        d = dhan_client()
        return ok(d.get_holdings())
    except Exception as e:
        return err(e)

@app.get("/funds")
def funds():
    try:
        d = dhan_client()
        return ok(d.get_fund_limits())
    except Exception as e:
        return err(e)

# ---------- Historical / Intraday ----------
@app.get("/charts/intraday")
def intraday_minute_data(
    security_id: str = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: str = Query(...),
    interval: Optional[int] = Query(1, description="minute interval supported by API"),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD HH:MM"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD HH:MM"),
):
    try:
        d = dhan_client()
        data = d.intraday_minute_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type
        )
        # SDK returns full set; client can filter for interval/time as needed
        return ok({"raw": data, "note": "Filter by interval/from/to on client if needed"})
    except Exception as e:
        return err(e)

@app.get("/charts/historical")
def historical_daily_data(
    security_id: str = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: str = Query(...),
    expiry_code: Optional[str] = Query(None),
    from_date: str = Query(..., description="YYYY-MM-DD"),
    to_date: str = Query(..., description="YYYY-MM-DD"),
):
    try:
        d = dhan_client()
        data = d.historical_daily_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            expiry_code=expiry_code,
            from_date=from_date,
            to_date=to_date,
        )
        return ok(data)
    except Exception as e:
        return err(e)

# ---------- Forever Orders ----------
@app.post("/forever/place")
def forever_place(req: ForeverOrderReq):
    try:
        d = dhan_client()
        return ok(d.place_forever(**req.model_dump()))
    except Exception as e:
        return err(e)

@app.post("/forever/modify")
def forever_modify(
    order_id: str = Body(...),
    price: float = Body(...),
    trigger_price: float = Body(...)
):
    try:
        d = dhan_client()
        return ok(d.modify_forever(order_id, price, trigger_price))
    except Exception as e:
        return err(e)

@app.post("/forever/cancel")
def forever_cancel(order_id: str = Body(..., embed=True)):
    try:
        d = dhan_client()
        return ok(d.cancel_forever(order_id))
    except Exception as e:
        return err(e)

# ---------- eDIS ----------
@app.post("/edis/generate_tpin")
def edis_generate_tpin():
    try:
        d = dhan_client()
        return ok(d.generate_tpin())
    except Exception as e:
        return err(e)

@app.post("/edis/open_browser_for_tpin")
def edis_open_browser_for_tpin(isin: str = Body(...), qty: int = Body(1), exchange: str = Body("NSE")):
    try:
        d = dhan_client()
        return ok(d.open_browser_for_tpin(isin=isin, qty=qty, exchange=exchange))
    except Exception as e:
        return err(e)

@app.get("/edis/inquiry")
def edis_inquiry():
    try:
        d = dhan_client()
        return ok(d.edis_inquiry())
    except Exception as e:
        return err(e)

# ---------- Marketfeed placeholders (WS handled client-side) ----------
@app.get("/marketfeed/ping")
def marketfeed_ping():
    return ok({"ws": "Use client-side dhanhq.marketfeed to connect to live feed WS."})

# ---------- Generic executor (power-user) ----------
class ExecReq(BaseModel):
    method: str
    args: Dict[str, Any] = {}

@app.post("/dhan/exec")
def dhan_exec(req: ExecReq):
    """
    Call any dhanhq SDK method dynamically:
    POST /dhan/exec { "method": "fetch_security_list", "args": {"mode": "compact"} }
    """
    try:
        d = dhan_client()
        if not hasattr(d, req.method):
            return {"status": "error", "error": f"Method {req.method} not found on sdk"}
        fn = getattr(d, req.method)
        out = fn(**req.args) if isinstance(req.args, dict) else fn(req.args)
        # ensure JSON serializable
        try:
            json.dumps(out)
            return ok(out)
        except TypeError:
            return ok({"repr": repr(out)})
    except Exception as e:
        return err(e, called=req.method, args=req.args)

# ---------- Self test ----------
@app.get("/__selftest")
def __selftest():
    res = {
        "ok": True,
        "status": {
            "env": bool(DHAN_ACCESS_TOKEN or DHAN_CLIENT_ID),
            "mode": "LIVE",
            "token_present": bool(DHAN_ACCESS_TOKEN),
            "client_id_present": bool(DHAN_CLIENT_ID),
        }
    }
    # Try a small sample call if possible
    try:
        d = dhan_client()
        sample = d.expiry_list(under_security_id="13", under_exchange_segment="IDX_I")
    except Exception as e:
        sample = {"status": "error", "error": str(e)}
    res["sample_expirylist"] = sample
    return res
