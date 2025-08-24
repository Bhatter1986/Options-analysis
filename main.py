import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import FastAPI, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Dhan SDK
from dhanhq import dhanhq as DhanHQ

app = FastAPI(title="Options-analysis (Dhan v2)")

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ---------- ENV / MODE ----------
def _pick(*keys: str) -> Optional[str]:
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return None

MODE = os.getenv("MODE", "TEST").upper()          # LIVE or TEST(SANDBOX)
ENV_NOTE = "LIVE" if MODE == "LIVE" else "SANDBOX"

if MODE == "LIVE":
    CLIENT_ID = _pick("DHAN_LIVE_CLIENT_ID", "DHAN_CLIENT_ID")
    ACCESS_TOKEN = _pick("DHAN_LIVE_ACCESS_TOKEN", "DHAN_ACCESS_TOKEN")
else:
    CLIENT_ID = _pick("DHAN_SANDBOX_CLIENT_ID", "DHAN_CLIENT_ID")
    ACCESS_TOKEN = _pick("DHAN_SANDBOX_ACCESS_TOKEN", "DHAN_ACCESS_TOKEN")

# One Dhan client for entire app
dhan = DhanHQ(CLIENT_ID or "", ACCESS_TOKEN or "")

# ---------- Helpers ----------
def ok(data: Any, remarks: str = "") -> Dict[str, Any]:
    return {"status": "success", "remarks": remarks, "data": data}

def fail(msg: str, code: Optional[str] = None, etype: Optional[str] = None, data: Any = None) -> Dict[str, Any]:
    return {"status": "failure", "remarks": {"error_code": code, "error_type": etype, "error_message": msg}, "data": data}

def _quote_key(seg: str) -> str:
    s = seg.upper().strip()
    if s in ("NSE", "NSE_EQ"): return "NSE_EQ"
    if s in ("BSE", "BSE_EQ"): return "BSE_EQ"
    if s in ("NSE_FNO",):      return "NSE_FNO"
    if s in ("MCX", "MCX_COMM"): return "MCX_COMM"
    return s

# ---------- Root ----------
@app.get("/")
def root():
    return {
        "app": app.title,
        "mode": MODE,
        "env": ENV_NOTE,
        "now": datetime.now(timezone.utc).isoformat(),
        "endpoints": [
            "/health", "/broker_status",
            "/marketfeed/ltp", "/marketfeed/ohlc", "/marketfeed/quote",
            "/optionchain", "/optionchain/expirylist",
            "/orders", "/positions", "/holdings", "/funds",
            "/charts/intraday", "/charts/historical",
            "/option_analysis", "/__selftest"
        ],
    }

# ---------- Health / Status ----------
@app.get("/health")
def health():
    return ok({"ok": True, "time": datetime.now(timezone.utc).isoformat()})

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "env": ENV_NOTE,
        "token_present": bool(ACCESS_TOKEN),
        "client_id_present": bool(CLIENT_ID),
    }

# ---------- Portfolio ----------
@app.get("/orders")
def orders():
    try:
        return ok(dhan.get_order_list())
    except Exception as e:
        return fail("orders fetch failed", data=str(e))

@app.get("/positions")
def positions():
    try:
        return ok(dhan.get_positions())
    except Exception as e:
        return fail("positions fetch failed", data=str(e))

@app.get("/holdings")
def holdings():
    try:
        return ok(dhan.get_holdings())
    except Exception as e:
        return fail("holdings fetch failed", data=str(e))

@app.get("/funds")
def funds():
    try:
        return ok(dhan.get_fund_limits())
    except Exception as e:
        return fail("funds fetch failed", data=str(e))

# ---------- Market Quote (snapshot REST) ----------
@app.get("/marketfeed/ltp")
def market_ltp(exchange_segment: str = Query(...), security_id: int = Query(...)):
    try:
        payload = { _quote_key(exchange_segment): [int(security_id)] }
        return ok(dhan.ticker_data(securities=payload))
    except Exception as e:
        return fail("ltp fetch failed", data=str(e))

@app.get("/marketfeed/ohlc")
def market_ohlc(exchange_segment: str = Query(...), security_id: int = Query(...)):
    try:
        payload = { _quote_key(exchange_segment): [int(security_id)] }
        return ok(dhan.ohlc_data(securities=payload))
    except Exception as e:
        return fail("ohlc fetch failed", data=str(e))

@app.get("/marketfeed/quote")
def market_quote(exchange_segment: str = Query(...), security_id: int = Query(...)):
    try:
        payload = { _quote_key(exchange_segment): [int(security_id)] }
        return ok(dhan.quote_data(securities=payload))
    except Exception as e:
        return fail("quote fetch failed", data=str(e))

# ---------- Option Chain ----------
class OptionChainBody(BaseModel):
    under_security_id: int
    under_exchange_segment: str
    expiry: str

@app.get("/optionchain/expirylist")
def optionchain_expirylist(
    under_security_id: int = Query(...),
    under_exchange_segment: str = Query(...)
):
    try:
        return ok(dhan.expiry_list(under_security_id=under_security_id,
                                   under_exchange_segment=under_exchange_segment))
    except Exception as e:
        return fail("expiry list failed", data=str(e))

@app.post("/optionchain")
def optionchain(body: OptionChainBody = Body(...)):
    try:
        return ok(dhan.option_chain(
            under_security_id=body.under_security_id,
            under_exchange_segment=body.under_exchange_segment,
            expiry=body.expiry
        ))
    except Exception as e:
        return fail("option chain failed", data=str(e))

# ---------- Charts ----------
@app.get("/charts/intraday")
def charts_intraday(
    security_id: int = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: str = Query(...),
):
    try:
        return ok(dhan.intraday_minute_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type
        ))
    except Exception as e:
        return fail("intraday data failed", data=str(e))

@app.get("/charts/historical")
def charts_historical(
    security_id: int = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: str = Query(...),
    expiry_code: int = Query(0),
    from_date: str = Query(..., description="YYYY-MM-DD"),
    to_date: str = Query(..., description="YYYY-MM-DD"),
):
    try:
        return ok(dhan.historical_daily_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            expiry_code=expiry_code,
            from_date=from_date,
            to_date=to_date
        ))
    except Exception as e:
        return fail("historical data failed", data=str(e))

# ---------- Aggregate: Option Analysis (data only) ----------
@app.get("/option_analysis")
def option_analysis(
    under_security_id: int = Query(13, description="NIFTY"),
    under_exchange_segment: str = Query("IDX_I"),
    equity_security_id: int = Query(1333, description="HDFC Bank eq for demo"),
    equity_exchange_segment: str = Query("NSE")
):
    try:
        # 1) Expiries
        expiries = dhan.expiry_list(under_security_id=under_security_id,
                                    under_exchange_segment=under_exchange_segment)

        expiry_pick = None
        try:
            expiry_pick = (expiries or {}).get("data", {}).get("data", [None])[0]
        except Exception:
            expiry_pick = None

        # 2) Option chain (first expiry if available)
        chain = {}
        if expiry_pick:
            chain = dhan.option_chain(
                under_security_id=under_security_id,
                under_exchange_segment=under_exchange_segment,
                expiry=expiry_pick
            )

        # 3) Market snapshots for an example equity
        key = _quote_key(equity_exchange_segment)
        payload = { key: [int(equity_security_id)] }
        market = {
            "ltp": dhan.ticker_data(securities=payload),
            "ohlc": dhan.ohlc_data(securities=payload),
            "quote": dhan.quote_data(securities=payload)
        }

        # 4) Portfolio snapshot
        portfolio = {
            "orders": dhan.get_order_list(),
            "positions": dhan.get_positions(),
            "holdings": dhan.get_holdings(),
            "funds": dhan.get_fund_limits()
        }

        return ok({
            "params": {
                "under_security_id": under_security_id,
                "under_exchange_segment": under_exchange_segment,
                "used_expiry": expiry_pick
            },
            "expiry_list": expiries,
            "option_chain": chain,
            "market": market,
            "portfolio": portfolio
        })
    except Exception as e:
        return fail("option_analysis failed", data=str(e))

# ---------- Self-test ----------
@app.get("/__selftest")
def __selftest(request: Request):
    base = str(request.base_url).rstrip("/")
    samples = {
        "root": "/",
        "health": "/health",
        "broker_status": "/broker_status",
        "orders": "/orders",
        "positions": "/positions",
        "holdings": "/holdings",
        "funds": "/funds",
        "expiryllist_sample": "/optionchain/expirylist?under_security_id=13&under_exchange_segment=IDX_I",
        "intraday_sample": "/charts/intraday?security_id=1333&exchange_segment=NSE&instrument_type=EQUITY",
        "historical_sample": "/charts/historical?security_id=1333&exchange_segment=NSE&instrument_type=EQUITY&expiry_code=0&from_date=2024-01-01&to_date=2024-02-01",
        "option_analysis": "/option_analysis"
    }
    return {
        "status": {
            "mode": MODE, "env": ENV_NOTE,
            "token_present": bool(ACCESS_TOKEN),
            "client_id_present": bool(CLIENT_ID),
            "base_url_note": "MODE=LIVE uses LIVE_… keys; otherwise SANDBOX",
        },
        "samples": {k: f"{base}{v}" for k, v in samples.items()},
        "now": datetime.now(timezone.utc).isoformat()
    }

# --- ADD THESE IMPORTS AT THE TOP WITH YOUR OTHER FASTAPI IMPORTS ---
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ... your existing main.py code (FastAPI app, routes, etc.) ...

# --- STATIC MOUNT (place near the top after app = FastAPI(...)) ---
# Serve everything inside /public at /public URL path
app.mount("/public", StaticFiles(directory="public"), name="public")

# --- DASHBOARD ROUTE (place anywhere after app is defined) ---
@app.get("/dashboard")
def serve_dashboard():
    # This loads the separate HTML file. No inline HTML inside Python.
    return FileResponse("public/dashboard.html")
