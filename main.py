# --- main.py (full) ---
import os
from fastapi import FastAPI, HTTPException, Request

# Try import dhanhq (installed via requirements.txt)
try:
    from dhanhq import dhanhq
except Exception:
    dhanhq = None

app = FastAPI()

# Config / Secrets
WEBHOOK_SECRET   = os.getenv("WEBHOOK_SECRET", "change-me")
DHAN_CLIENT_ID   = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN= os.getenv("DHAN_ACCESS_TOKEN")
MODE             = os.getenv("MODE", "DRY").upper()   # DRY or LIVE

# Create Dhan client if creds and library present
DHAN = None
if dhanhq and DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
    try:
        DHAN = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
        print("✅ Dhan client initialized")
    except Exception as e:
        print("❌ Dhan init failed:", e)

# --- basic endpoints ---
@app.get("/")
def root():
    return {"message": "Hello India Market 🚀"}

@app.get("/health")
def health():
    return {"ok": True}

# Check broker status quickly
@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "has_lib": bool(dhanhq),
        "has_creds": bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN),
        "client_ready": bool(DHAN),
    }

# Sample options dummy (kept from earlier)
@app.get("/options")
def options_analysis():
    data = {
        "symbol": "NIFTY",
        "strike": 25000,
        "trend": "Bullish",
        "iv": 12.5,
        "delta": 0.62
    }
    return {"options_data": data}

# --- webhook to accept TV / external alerts ---
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    # Secret check
    secret = data.get("secret")
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract fields (accept both detailed or direct security_id)
    action      = data.get("action")          # BUY/SELL
    qty         = data.get("qty")             # int
    price       = data.get("price", "MARKET") # MARKET/LIMIT
    security_id = data.get("security_id")     # strongly recommended for LIVE

    # Optional detail fields (TV style): not used if security_id given
    symbol     = data.get("symbol")
    expiry     = data.get("expiry")
    strike     = data.get("strike")
    option_typ = data.get("option_type")      # CE/PE

    # Minimal validation
    if not action or not qty:
        raise HTTPException(status_code=422, detail="Missing action/qty")

    # Prepare echo order
    order = {
        "side": action,
        "symbol": symbol,
        "expiry": expiry,
        "strike": strike,
        "type": option_typ,
        "qty": qty,
        "price": price,
        "security_id": security_id
    }

    # DRY mode or client missing? just echo back
    if MODE != "LIVE" or not DHAN:
        return {
            "ok": True,
            "mode": MODE,
            "received": data,
            "order": order,
            "note": "LIVE trade disabled. Set MODE=LIVE and send security_id to place order."
        }

    # LIVE mode: require security_id
    if not security_id:
        raise HTTPException(
            status_code=400,
            detail="LIVE mode requires 'security_id' (instrument token)."
        )

    # Map fields for Dhan API
    exchange_segment = data.get("exchange_segment", "NSE_FNO")  # override if needed
    transaction_type = action  # BUY or SELL
    order_type = "MARKET" if str(price).upper() == "MARKET" else "LIMIT"
    product_type = data.get("product_type", "INTRADAY")  # CNC/MARGIN/INTRADAY etc.
    limit_price = 0 if order_type == "MARKET" else float(price)

    # Place order via Dhan
    try:
        resp = DHAN.place_order(
            security_id = security_id,
            exchange_segment = exchange_segment,
            transaction_type = transaction_type,
            quantity = int(qty),
            order_type = order_type,
            product_type = product_type,
            price = limit_price
        )
        return {
            "ok": True,
            "mode": MODE,
            "received": data,
            "order": order,
            "broker_response": resp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dhan order failed: {e}")
# --- end of file ---
