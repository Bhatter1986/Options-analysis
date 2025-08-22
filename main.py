# main.py — Dhan REST integration + routes (FastAPI)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import csv
import io
import requests
from datetime import datetime

app = FastAPI(title="Options Analysis API", version="2.0")

# ─────────────────────────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────
# ENV & CONSTANTS
# ─────────────────────────────────────────────────────────────────
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
MODE = os.getenv("MODE", "DRY").upper()  # DRY / LIVE

DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
DHAN_API_BASE = "https://api.dhan.co/v2"  # sandbox: https://sandbox.dhan.co/v2

INSTR_CSV_COMPACT = "https://images.dhan.co/api-data/api-scrip-master.csv"
INSTR_CSV_DETAILED = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

REQ_TIMEOUT = 30


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def dhan_headers():
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="Dhan credentials missing")
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "client-id": DHAN_CLIENT_ID,
        "access-token": DHAN_ACCESS_TOKEN,
    }


def broker_ready():
    return bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN)


def fetch_instruments_csv(detailed: bool = False) -> str:
    url = INSTR_CSV_DETAILED if detailed else INSTR_CSV_COMPACT
    r = requests.get(url, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    return r.text


def lookup_security_id(
    underlying_symbol: str, expiry: str, strike: float, option_type: str
):
    """
    Returns first matching Security ID or None from detailed CSV.

    Columns handled (detailed):
      UNDERLYING_SYMBOL, SEM_EXPIRY_DATE, SEM_STRIKE_PRICE, SEM_OPTION_TYPE,
      SECURITY_ID | SEM_SECURITY_ID | SM_SECURITY_ID
    """
    csv_text = fetch_instruments_csv(detailed=True)
    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)

    # detect security id column
    header = reader.fieldnames or []
    sec_id_col = None
    for c in ("SECURITY_ID", "SEM_SECURITY_ID", "SM_SECURITY_ID"):
        if c in header:
            sec_id_col = c
            break

    # normalize inputs
    sym = (underlying_symbol or "").upper().strip()
    otype = (option_type or "").upper().strip()
    exp = (expiry or "").strip()

    for row in reader:
        try:
            if (
                (row.get("UNDERLYING_SYMBOL", "").upper().strip() == sym)
                and (row.get("SEM_EXPIRY_DATE", "").strip() == exp)
                and (row.get("SEM_OPTION_TYPE", "").upper().strip() == otype)
                and (
                    float(row.get("SEM_STRIKE_PRICE", "0") or 0.0) == float(strike)
                )
            ):
                return row.get(sec_id_col) if sec_id_col else None
        except Exception:
            continue
    return None  # ✅ keep this on its own line


# ✅ new line here; the previous error was due to this being stuck to the next def
def place_dhan_order(
    security_id: str,
    side: str,  # BUY / SELL
    qty: int,
    order_type: str = "MARKET",  # MARKET / LIMIT
    price: float | None = None,
    product_type: str = "INTRADAY",
    exchange_segment: str = "NSE_FNO",
    validity: str = "DAY",
    tag: str | None = None,
):
    """
    Minimal /orders call to Dhan v2.
    Adjust enums per your account/segment if needed.
    """
    url = f"{DHAN_API_BASE}/orders"
    payload = {
        "transaction_type": str(side).upper(),  # BUY/SELL
        "exchange_segment": exchange_segment,  # e.g. NSE_FNO
        "product_type": product_type,  # e.g. INTRADAY
        "order_type": order_type,  # MARKET/LIMIT
        "validity": validity,  # DAY/IOC
        "security_id": str(security_id),
        "quantity": int(qty),
    }
    if tag:
        payload["correlation_id"] = str(tag)
    if order_type == "LIMIT" and (price is not None):
        payload["price"] = float(price)

    r = requests.post(url, headers=dhan_headers(), json=payload, timeout=REQ_TIMEOUT)
    try:
        data = r.json()
    except Exception:
        data = {"text": r.text}
    return r.status_code, data


def dhan_quote_snapshot(body: dict):
    """
    Calls /marketfeed/quote for snapshot (LTP, OHLC, depth, OI).
    body example: { "NSE_FNO": [49081, 49082] }
    """
    url = f"{DHAN_API_BASE}/marketfeed/quote"
    r = requests.post(url, headers=dhan_headers(), json=body, timeout=20)
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "has_lib": True,
        "has_creds": broker_ready(),
        "client_ready": broker_ready(),
    }


@app.get("/security_lookup")
def security_lookup_usage():
    return {
        "use": "POST /security_lookup with JSON body",
        "example": {
            "symbol": "NIFTY",
            "expiry": "2025-08-28",
            "strike": 25100,
            "option_type": "CE",
        },
    }


@app.post("/security_lookup")
async def security_lookup(payload: dict):
    """
    Payload:
    {
      "symbol": "NIFTY",
      "expiry": "2025-08-28",
      "strike": 25100,
      "option_type": "CE"
    }
    """
    sec_id = lookup_security_id(
        payload.get("symbol", ""),
        payload.get("expiry", ""),
        payload.get("strike", 0),
        payload.get("option_type", ""),
    )
    return {"security_id": sec_id}


@app.post("/dhan/quote")
async def dhan_quote(body: dict):
    """
    Body example:
    { "NSE_FNO": [49081] }
    """
    try:
        resp = dhan_quote_snapshot(body)
        return resp
    except requests.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@app.post("/webhook")
async def webhook(request: Request):
    """
    TradingView / manual alerts:

    {
      "secret": "my$ecret123",
      "symbol": "NIFTY",
      "action": "BUY",
      "expiry": "2025-08-28",
      "strike": 25100,
      "option_type": "CE",
      "qty": 50,
      "price": "MARKET",             # or numeric for LIMIT
      "security_id": "optional_if_known"
    }
    """
    data = await request.json()

    # 1) Secret check
    if str(data.get("secret", "")) != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 2) Parse fields
    symbol = data.get("symbol")
    action = data.get("action")  # BUY/SELL
    expiry = data.get("expiry")  # YYYY-MM-DD
    strike = data.get("strike")
    option_type = data.get("option_type")  # CE/PE
    qty = int(data.get("qty", 0))
    price = data.get("price", "MARKET")
    security_id = data.get("security_id")

    if not symbol or not action or qty <= 0:
        raise HTTPException(422, detail="symbol/action/qty required")

    # DRY mode → simulate only
    if MODE != "LIVE":
        return {
            "ok": True,
            "mode": MODE,
            "received": data,
            "order": {
                "side": action,
                "symbol": symbol,
                "expiry": expiry,
                "strike": strike,
                "type": option_type,
                "qty": qty,
                "price": price,
                "security_id": security_id,
                "note": "DRY mode: no live order. Set MODE=LIVE to execute.",
            },
        }

    # LIVE mode → ensure security_id
    if not security_id:
        security_id = lookup_security_id(symbol, expiry, strike, option_type)
        if not security_id:
            raise HTTPException(400, detail="security_id not found")

    # MARKET or LIMIT selection
    order_type = "MARKET"
    limit_price = None
    try:
        if isinstance(price, (int, float)) or (
            isinstance(price, str) and price.replace(".", "", 1).isdigit()
        ):
            order_type = "LIMIT"
            limit_price = float(price)
        elif str(price).upper() == "MARKET":
            order_type = "MARKET"
        else:
            order_type = "MARKET"
    except Exception:
        order_type = "MARKET"

    # Place order
    tag = f"tv-{datetime.utcnow().isoformat()}"
    status, broker_resp = place_dhan_order(
        security_id=str(security_id),
        side=str(action).upper(),
        qty=qty,
        order_type=order_type,
        price=limit_price,
        product_type="INTRADAY",
        exchange_segment="NSE_FNO",
        validity="DAY",
        tag=tag,
    )

    return {
        "ok": status in (200, 201),
        "mode": "LIVE",
        "received": data,
        "dhan_response": broker_resp,
    }
