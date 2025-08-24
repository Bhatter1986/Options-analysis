from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
from dhanhq import dhanhq
import os

app = FastAPI(title="Options Analysis (DhanHQ v2)", version="1.0.0")

# ---- Env / Client ----
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

def get_dhan():
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        raise RuntimeError("Missing DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN")
    # DhanHQ SDK client
    return dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)

# ---- Health / Status ----
@app.get("/broker_status")
def broker_status():
    return {
        "mode": "LIVE",                 # Render env me LIVE; sandbox use karna ho to SDK-level/calls change karna hoga
        "token_present": bool(DHAN_ACCESS_TOKEN),
        "client_id_present": bool(DHAN_CLIENT_ID),
    }

# ---- Orders / Portfolio ----
@app.get("/orders")
def get_orders():
    try:
        return get_dhan().get_order_list()
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)

@app.get("/positions")
def get_positions():
    try:
        return get_dhan().get_positions()
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)

@app.get("/holdings")
def get_holdings():
    try:
        return get_dhan().get_holdings()
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)

# ---- Option Chain ----
@app.post("/option_chain")
def option_chain(
    body: dict = Body(
        example={
            "under_security_id": 13,            # NIFTY
            "under_exchange_segment": "IDX_I",  # Index F&O
            "expiry": "2024-10-31"              # optional; latest available dekhne ko empty bhi chalta
        }
    )
):
    try:
        u_sid = body.get("under_security_id", 13)
        u_seg = body.get("under_exchange_segment", "IDX_I")
        expiry = body.get("expiry")  # may be None

        return get_dhan().option_chain(
            under_security_id=u_sid,
            under_exchange_segment=u_seg,
            expiry=expiry
        )
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)

# ---- Quick quote / OHLC snapshot (optional helper) ----
@app.get("/ohlc")
def ohlc(security_id: str = "1333", segment: str = "NSE_EQ"):
    """
    Example: /ohlc?security_id=1333&segment=NSE_EQ  (HDFC)
    For multiple, enhance to accept CSV and map to dict {"NSE_EQ":[1333,14436]}
    """
    try:
        data = {segment: [int(security_id)]}
        return get_dhan().ohlc_data(securities=data)
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)

# ---- Root ----
@app.get("/")
def root():
    return {
        "service": "Options Analysis API (DhanHQ v2)",
        "docs": "/docs",
        "endpoints": ["/broker_status", "/orders", "/positions", "/holdings", "/option_chain (POST)", "/ohlc"]
    }
