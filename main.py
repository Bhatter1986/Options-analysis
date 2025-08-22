# main.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import requests

app = FastAPI(title="Options-Analysis API", version="1.0")

# Allow browser/tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ───────────────────────────────────────────────────────────────────────────────
# ENV / SETTINGS
# ───────────────────────────────────────────────────────────────────────────────
WEBHOOK_SECRET     = os.getenv("WEBHOOK_SECRET", "change-me")

# Dhan creds (sandbox/live same code; URL + MODE decide behaviour)
DHAN_CLIENT_ID     = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN  = os.getenv("DHAN_ACCESS_TOKEN", "")
DHAN_BASE_URL      = os.getenv("DHAN_BASE_URL", "https://sandbox.dhan.co/v2").rstrip("/")
MODE               = os.getenv("MODE", "DRY").upper()   # DRY or LIVE


# ───────────────────────────────────────────────────────────────────────────────
# Small helper to call Dhan REST
# ───────────────────────────────────────────────────────────────────────────────
def _dhan_request(path: str, method: str = "GET", json: dict | None = None):
    """
    Minimal wrapper around Dhan v2 REST.
    Raises HTTPException for error status codes.
    """
    if not (DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN):
        raise HTTPException(status_code=500, detail="Dhan credentials missing")

    url = f"{DHAN_BASE_URL}/{path.lstrip('/')}"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "client-id": DHAN_CLIENT_ID,
        "access-token": DHAN_ACCESS_TOKEN,
    }

    try:
        resp = requests.request(method.upper(), url, headers=headers, json=json, timeout=20)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Dhan request failed: {e}")

    try:
        data = resp.json()
    except Exception:
        data = {"text": resp.text}

    if resp.status_code >= 400:
        # bubble up broker error payload
        raise HTTPException(status_code=resp.status_code, detail=data)

    return {"status": resp.status_code, "data": data}


# ───────────────────────────────────────────────────────────────────────────────
# Health / root / sample endpoints
# ───────────────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "Hello India Market 🚀"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/options")
def options_analysis():
    # dummy data for now
    data = {
        "symbol": "NIFTY",
        "strike": 25000,
        "trend": "Bullish",
        "iv": 12.5,
        "delta": 0.62,
    }
    return {"options_data": data}


# ───────────────────────────────────────────────────────────────────────────────
# Broker status & quick proxies (for testing)
# ───────────────────────────────────────────────────────────────────────────────
@app.get("/broker_status")
def broker_status():
    ok_creds = bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN)
    return {"mode": MODE, "has_lib": True, "has_creds": ok_creds, "client_ready": ok_creds}

@app.get("/dhan/orders")
def list_orders():
    # NOTE: Works only if Dhan exposes list endpoint for your account/keys.
    return _dhan_request("orders", "GET")

@app.get("/dhan/proxy")
def dhan_proxy(path: str, method: str = "GET"):
    """
    Generic proxy for quick testing:
    /dhan/proxy?path=portfolio/positions
    /dhan/proxy?path=funds
    """
    return _dhan_request(path, method.upper())


# ───────────────────────────────────────────────────────────────────────────────
# Webhook to receive trade signals
# ───────────────────────────────────────────────────────────────────────────────
@app.post("/webhook")
async def webhook(request: Request):
    """
    Expected JSON body (example):
    {
      "secret": "my$ecret123",
      "symbol": "NIFTY",
      "action": "BUY",
      "expiry": "2025-08-28",
      "strike": 25100,
      "option_type": "CE",
      "qty": 50,
      "price": "MARKET",
      "security_id": "12345",               # REQUIRED in LIVE mode
      "exchange_segment": "NSE_FNO",        # optional (LIVE default)
      "product_type": "INTRADAY",           # optional (LIVE default)
      "validity": "DAY"                     # optional (LIVE default)
    }
    """
    data = await request.json()

    # 1) Secret check
    secret = str(data.get("secret", ""))
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 2) Extract user-friendly fields
    symbol      = data.get("symbol")
    action      = data.get("action")          # BUY / SELL
    expiry      = data.get("expiry")          # yyyy-mm-dd (info only)
    strike      = data.get("strike")          # info only
    option_type = data.get("option_type")     # CE/PE (info only)
    qty         = data.get("qty")
    price       = data.get("price", "MARKET") # MARKET/LIMIT
    security_id = data.get("security_id")     # must in LIVE

    # Basic validations
    if not all([symbol, action, qty]):
        raise HTTPException(status_code=422, detail="symbol/action/qty required")

    # Build an echo "order" summary (for logs/response)
    human_order = {
        "side": action,
        "symbol": symbol,
        "expiry": expiry,
        "strike": strike,
        "type": option_type,
        "qty": qty,
        "price": price,
        "security_id": security_id,
    }

    # 3) Default broker response (DRY)
    broker_resp: dict = {"status": "dry-run", "note": "LIVE trade disabled in DRY mode."}

    # 4) If LIVE, place order to Dhan (minimal payload)
    if MODE == "LIVE":
        if not security_id:
            raise HTTPException(status_code=422, detail="security_id required in LIVE mode")

        # Defaults (can be overridden by sender)
        exchange_segment = data.get("exchange_segment", "NSE_FNO")
        product_type     = data.get("product_type", "INTRADAY")
        validity         = data.get("validity", "DAY")
        order_type       = price  # MARKET/LIMIT (same as input)

        # Minimal order payload for Dhan v2
        # (Fields naming follow Dhan docs; adjust if your account needs extras.)
        payload = {
            "transactionType": action,          # BUY / SELL
            "exchangeSegment": exchange_segment,
            "productType": product_type,        # e.g., INTRADAY / CARRYFORWARD
            "orderType": order_type,            # MARKET / LIMIT
            "validity": validity,               # DAY / IOC etc.
            "securityId": str(security_id),
            "quantity": int(qty),
        }
        # Optional limit price
        if order_type == "LIMIT" and "limit_price" in data:
            payload["price"] = float(data["limit_price"])

        # Fire to Dhan
        broker_resp = _dhan_request("orders", "POST", payload)

    return {
        "ok": True,
        "mode": MODE,
        "received": data,
        "order": human_order,
        "broker_response": broker_resp,
    }
