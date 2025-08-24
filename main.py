# main.py
import os
from fastapi import FastAPI, Body, HTTPException
from dhanhq import dhanhq

app = FastAPI(title="Options analysis (Dhan v2 SDK)")

# --- ENV ---
CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

def get_dhan():
    if not CLIENT_ID or not ACCESS_TOKEN:
        raise HTTPException(status_code=500,
            detail="Missing DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN env vars.")
    return dhanhq(CLIENT_ID, ACCESS_TOKEN)

# --- Health/Info ---
@app.get("/broker_status")
def broker_status():
    return {
        "mode": os.getenv("MODE", "DRY"),
        "env": "SANDBOX" if "sandbox" in (os.getenv("DHAN_BASE_URL","").lower()) else "LIVE",
        "token_present": bool(ACCESS_TOKEN),
        "client_id_present": bool(CLIENT_ID),
    }

# --- Orders (GET) ---
@app.get("/orders")
def get_orders():
    d = get_dhan()
    try:
        return d.get_order_list()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Dhan error: {e}")

# --- Option Chain (POST) ---
@app.post("/optionchain")
def option_chain(
    payload: dict = Body(..., example={
        "under_security_id": 13,
        "under_exchange_segment": "IDX_I",
        "expiry": "2024-10-31"
    })
):
    d = get_dhan()
    try:
        return d.option_chain(
            under_security_id = payload.get("under_security_id"),
            under_exchange_segment = payload.get("under_exchange_segment"),
            expiry = payload.get("expiry"),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Dhan error: {e}")
