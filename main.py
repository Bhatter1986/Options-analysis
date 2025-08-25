# main.py
import os
import json
import time
import threading
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---- DhanHQ SDK ----
# pip install dhanhq==2.0.2  (requirements.txt me "dhanhq" likha ho)
from dhanhq import dhanhq, marketfeed

APP_NAME = "Options-analysis (Dhan v2 + AI)"
MODE = "LIVE"

# ---------- ENV & SDK CLIENT ----------
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "").strip()
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "").strip()

if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
    # We won't crash import; we'll error only at runtime calls.
    dhan_client = None
else:
    dhan_client = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)

# ---------- FASTAPI ----------
app = FastAPI(title=APP_NAME)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ---------- Helpers ----------
def need_client():
    if dhan_client is None:
        raise HTTPException(status_code=500, detail="Dhan credentials missing. Set DHAN_CLIENT_ID & DHAN_ACCESS_TOKEN.")

def ok(data: Any) -> Dict[str, Any]:
    return {"status": "success", "data": data}

def fail(remarks: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "failure", "data": {"status": "failed", "remarks": remarks}}

def catch_exc(fn):
    try:
        return fn()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{type(e).__name__}: {e}")

# Basic symbol→underlying mapping for INDEX options (expand later if needed)
INDEX_UNDER = {
    "NIFTY":  {"under_security_id": 13, "under_exchange_segment": "IDX_I"},
    "BANKNIFTY": {"under_security_id": 25, "under_exchange_segment": "IDX_I"},
    # "FINNIFTY": {"under_security_id": <fill>, "under_exchange_segment": "IDX_I"},
}

# ---------- MODELS ----------
class PlaceOrder(BaseModel):
    security_id: str
    exchange_segment: str = Field(..., description="e.g. 'NSE', 'NSE_FNO', 'IDX_I'")
    transaction_type: str = Field(..., description="dhan.BUY / dhan.SELL (string ok)")
    quantity: int
    order_type: str = Field(..., description="dhan.MARKET / LIMIT etc. (string ok)")
    product_type: str = Field(..., description="dhan.INTRA / CNC / NRML etc. (string ok)")
    price: float = 0
    trigger_price: Optional[float] = None
    validity: Optional[str] = None
    disclosed_quantity: Optional[int] = None
    amo: Optional[bool] = False
    # any other kwargs supported by SDK

class ModifyOrder(BaseModel):
    order_id: str
    order_type: Optional[str] = None
    leg_name: Optional[str] = None
    quantity: Optional[int] = None
    price: Optional[float] = None
    trigger_price: Optional[float] = None

class ForeverOrder(BaseModel):
    security_id: str
    exchange_segment: str
    transaction_type: str
    product_type: str
    quantity: int
    price: float
    trigger_price: float

class RawREST(BaseModel):
    method: str = Field("POST", description="POST/GET")
    path: str = Field(..., description="e.g. '/v2/option/expiry-list'")
    payload: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None

class SDKExec(BaseModel):
    fn: str = Field(..., description="SDK function name, e.g. 'expiry_list'")
    kwargs: Dict[str, Any] = Field(default_factory=dict)

# ---------- HEALTH ----------
@app.get("/health")
def health():
    return ok({"app": APP_NAME, "mode": MODE})

@app.get("/broker_status")
def broker_status():
    return ok({
        "mode": MODE,
        "token_present": bool(DHAN_ACCESS_TOKEN),
        "client_id_present": bool(DHAN_CLIENT_ID),
        "openai_present": bool(os.getenv("OPENAI_API_KEY", "")),
    })

@app.get("/__selftest")
def selftest():
    status = {
        "env": True,
        "mode": MODE,
        "token_present": bool(DHAN_ACCESS_TOKEN),
        "client_id_present": bool(DHAN_CLIENT_ID),
        "openai_present": bool(os.getenv("OPENAI_API_KEY", "")),
    }
    sample: Dict[str, Any] = {}
    def _do():
        need_client()
        # lightweight call to verify auth; fund limits is cheap
        fl = dhan_client.get_fund_limits()
        sample["funds_ok"] = True if fl is not None else False
    try:
        if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
            _do()
    except Exception as e:
        sample["funds_ok"] = False
        sample["error"] = f"{type(e).__name__}: {e}"
    return ok({"status": status, "sample": sample})

# ---------- OPTION: EXPIRY LIST ----------
@app.get("/option/expirylist")
def option_expirylist(
    symbol: Optional[str] = Query(None, description="NIFTY / BANKNIFTY (optional helper)"),
    under_security_id: Optional[str] = None,
    under_exchange_segment: Optional[str] = None,
):
    """
    Wrapper over DhanHQ v2 expiry_list
    - pass either (symbol) OR (under_security_id + under_exchange_segment)
    """
    def _run():
        need_client()
        uid = under_security_id
        seg = under_exchange_segment
        if symbol:
            s = symbol.upper()
            if s in INDEX_UNDER:
                uid = str(INDEX_UNDER[s]["under_security_id"])
                seg = INDEX_UNDER[s]["under_exchange_segment"]
            else:
                return fail({"814": f"Unsupported symbol '{symbol}'. Provide under_security_id & under_exchange_segment."})

        if not uid or not seg:
            return fail({"814": "Invalid Request: need symbol OR under_security_id & under_exchange_segment"})

        # SDK call
        data = dhan_client.expiry_list(
            under_security_id=uid,
            under_exchange_segment=seg
        )
        return ok(data)
    return catch_exc(_run)

# ---------- OPTION: FULL CHAIN ----------
@app.get("/option/chain")
def option_chain(
    under_security_id: str = Query(...),
    under_exchange_segment: str = Query(..., description="IDX_I for index options, NSE_FNO for stock options"),
    expiry_date: Optional[str] = Query(None, description="YYYY-MM-DD (optional; if omitted, SDK may default to nearest)")
):
    def _run():
        need_client()
        # Most SDKs accept either only underlying+segment or also expiry; keep both safe:
        if expiry_date:
            data = dhan_client.option_chain(
                under_security_id=under_security_id,
                under_exchange_segment=under_exchange_segment,
                expiry_date=expiry_date
            )
        else:
            data = dhan_client.option_chain(
                under_security_id=under_security_id,
                under_exchange_segment=under_exchange_segment
            )
        return ok(data)
    return catch_exc(_run)

# ---------- MARKET QUOTE (snapshot) ----------
@app.get("/market/quote")
def market_quote(
    exchange_segment: str = Query(..., description="e.g. NSE, NSE_FNO, IDX_I"),
    security_id: str = Query(..., description="e.g. '1333' for HDFCBANK"),
    mode: str = Query("full", description="ticker | quote | full"),
):
    def _run():
        need_client()
        # Many SDKs expose quote via: dhan_client.quote(...) or market_quote(...)
        # Dhan v2 SDK offers 'market_quote' with (exchange_segment, security_id, mode)
        data = dhan_client.market_quote(
            exchange_segment=exchange_segment,
            security_id=security_id,
            mode=mode
        )
        return ok(data)
    return catch_exc(_run)

# ---------- HISTORICAL / INTRADAY ----------
@app.get("/charts/intraday")
def charts_intraday(
    security_id: str,
    exchange_segment: str,
    instrument_type: str = Query(..., description="e.g. 'EQUITY', 'INDEX', 'FUTIDX', etc."),
    interval: str = Query("1m", description="Supported by SDK internally"),
):
    def _run():
        need_client()
        data = dhan_client.intraday_minute_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type
        )
        return ok({"interval": interval, "data": data})
    return catch_exc(_run)

@app.get("/charts/historical")
def charts_historical(
    security_id: str,
    exchange_segment: str,
    instrument_type: str,
    expiry_code: Optional[str] = None,
    from_date: str = Query(..., description="YYYY-MM-DD"),
    to_date: str = Query(..., description="YYYY-MM-DD"),
):
    def _run():
        need_client()
        data = dhan_client.historical_daily_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            expiry_code=expiry_code,
            from_date=from_date,
            to_date=to_date
        )
        return ok(data)
    return catch_exc(_run)

# ---------- ORDERS ----------
@app.post("/orders/place")
def orders_place(body: PlaceOrder):
    def _run():
        need_client()
        payload = body.dict(exclude_none=True)
        data = dhan_client.place_order(**payload)
        return ok(data)
    return catch_exc(_run)

@app.post("/orders/modify")
def orders_modify(body: ModifyOrder):
    def _run():
        need_client()
        data = dhan_client.modify_order(
            order_id=body.order_id,
            order_type=body.order_type,
            leg_name=body.leg_name,
            quantity=body.quantity,
            price=body.price,
            trigger_price=body.trigger_price
        )
        return ok(data)
    return catch_exc(_run)

@app.post("/orders/cancel")
def orders_cancel(order_id: str = Body(..., embed=True)):
    def _run():
        need_client()
        data = dhan_client.cancel_order(order_id)
        return ok(data)
    return catch_exc(_run)

@app.get("/orders/{order_id}")
def orders_get(order_id: str):
    def _run():
        need_client()
        data = dhan_client.get_order_by_id(order_id)
        return ok(data)
    return catch_exc(_run)

@app.get("/tradebook/{order_id}")
def trade_book(order_id: str):
    def _run():
        need_client()
        data = dhan_client.get_trade_book(order_id)
        return ok(data)
    return catch_exc(_run)

@app.get("/tradehistory")
def trade_history(from_date: str, to_date: str, page_number: int = 0):
    def _run():
        need_client()
        data = dhan_client.get_trade_history(from_date, to_date, page_number=page_number)
        return ok(data)
    return catch_exc(_run)

# ---------- PORTFOLIO / FUNDS ----------
@app.get("/positions")
def positions():
    return catch_exc(lambda: ok(dhan_client.get_positions()) if need_client() is None else None)

@app.get("/holdings")
def holdings():
    return catch_exc(lambda: ok(dhan_client.get_holdings()) if need_client() is None else None)

@app.get("/funds")
def funds():
    return catch_exc(lambda: ok(dhan_client.get_fund_limits()) if need_client() is None else None)

# ---------- FOREVER ORDERS ----------
@app.post("/forever/place")
def forever_place(body: ForeverOrder):
    def _run():
        need_client()
        data = dhan_client.place_forever(
            security_id=body.security_id,
            exchange_segment=body.exchange_segment,
            transaction_type=body.transaction_type,
            product_type=body.product_type,
            quantity=body.quantity,
            price=body.price,
            trigger_price=body.trigger_price
        )
        return ok(data)
    return catch_exc(_run)

@app.post("/forever/modify")
def forever_modify(order_id: str = Body(...), price: Optional[float] = Body(None), trigger_price: Optional[float] = Body(None)):
    def _run():
        need_client()
        data = dhan_client.modify_forever(order_id, price=price, trigger_price=trigger_price)
        return ok(data)
    return catch_exc(_run)

@app.post("/forever/cancel")
def forever_cancel(order_id: str = Body(..., embed=True)):
    def _run():
        need_client()
        data = dhan_client.cancel_forever(order_id)
        return ok(data)
    return catch_exc(_run)

# ---------- eDIS ----------
@app.post("/edis/generate_tpin")
def edis_generate_tpin():
    return catch_exc(lambda: ok(dhan_client.generate_tpin()) if need_client() is None else None)

@app.post("/edis/open_browser_for_tpin")
def edis_open_browser_for_tpin(isin: str = Body(...), qty: int = Body(1), exchange: str = Body("NSE")):
    def _run():
        need_client()
        data = dhan_client.open_browser_for_tpin(isin=isin, qty=qty, exchange=exchange)
        return ok(data)
    return catch_exc(_run)

@app.get("/edis/inquiry")
def edis_inquiry():
    return catch_exc(lambda: ok(dhan_client.edis_inquiry()) if need_client() is None else None)

# ---------- MARKETFEED (utility) ----------
# NOTE: True realtime websocket run karna server pe background thread me kiya ja sakta hai.
# Yahan simple ping & last cache structure diya hai.
_feed_thread = None
_feed_running = False
_last_ticks: Dict[str, Any] = {}
_feed_lock = threading.Lock()

def _feed_callback(msg):
    try:
        # message structure depends on SDK; store by (segment|id|type)
        with _feed_lock:
            _last_ticks[str(msg.get("security_id", ""))] = msg
    except Exception:
        pass

def _start_feed(instruments: List[List[Any]]):
    global _feed_thread, _feed_running
    if _feed_running:  # already running
        return
    need_client()
    def run():
        global _feed_running
        _feed_running = True
        client = marketfeed.DhanFeed(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
        try:
            client.run_socket(instruments, on_data=_feed_callback)
        except Exception:
            _feed_running = False
    _feed_thread = threading.Thread(target=run, daemon=True)
    _feed_thread.start()

@app.post("/marketfeed/ping")
def marketfeed_ping(instruments: List[List[Any]] = Body(default=[["NSE", "1333", "Ticker"]])):
    """
    instruments = [[exchange_segment, security_id, subscription_type], ...]
    Example: [["NSE","1333","Ticker"], ["NSE","1333","Quote"]]
    """
    def _run():
        _start_feed(instruments)
        return ok({"running": True, "subscribed": instruments})
    return catch_exc(_run)

@app.get("/marketfeed/last")
def marketfeed_last(security_id: str):
    with _feed_lock:
        return ok(_last_ticks.get(security_id) or {})

# ---------- RAW REST (escape hatch) ----------
@app.post("/dhan/raw")
def dhanhq_raw(body: RawREST):
    """
    Directly call Dhan REST, signed with your headers.
    Example: {"method":"POST","path":"/v2/option/expiry-list","payload":{"under_security_id":"13","under_exchange_segment":"IDX_I"}}
    """
    def _run():
        need_client()
        url = "https://api.dhan.co" + body.path
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "client-id": DHAN_CLIENT_ID,
            "access-token": DHAN_ACCESS_TOKEN,
        }
        method = body.method.upper()
        if method == "POST":
            r = requests.post(url, headers=headers, json=body.payload or {}, params=body.params)
        elif method == "GET":
            r = requests.get(url, headers=headers, params=body.params)
        else:
            raise HTTPException(400, f"Unsupported method {method}")
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        if r.status_code >= 400:
            return fail({"code": r.status_code, "data": data})
        return ok(data)
    return catch_exc(_run)

# ---------- SDK EXECUTOR (escape hatch) ----------
@app.post("/dhan/exec")
def dhanhq_exec(body: SDKExec):
    """
    Call any dhanhq SDK function by name:
    { "fn": "expiry_list", "kwargs": {"under_security_id":"13","under_exchange_segment":"IDX_I"} }
    """
    def _run():
        need_client()
        fn = getattr(dhan_client, body.fn, None)
        if not fn or not callable(fn):
            raise HTTPException(400, f"SDK method '{body.fn}' not found.")
        data = fn(**body.kwargs)
        return ok(data)
    return catch_exc(_run)

# ---------- ROOT ----------
@app.get("/")
def root():
    return ok({"message": f"{APP_NAME} up", "docs": "/docs"})
