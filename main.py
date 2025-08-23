# main.py — Dhan REST integration (FastAPI)
# ----------------------------------------------------------
# ENV you should have on Render:
# DHAN_ENV = SANDBOX | LIVE
# MODE = DRY | LIVE
#
# DHAN_SANDBOX_CLIENT_ID, DHAN_SANDBOX_ACCESS_TOKEN, DHAN_SANDBOX_BASE_URL
# DHAN_LIVE_CLIENT_ID,    DHAN_LIVE_ACCESS_TOKEN,    DHAN_LIVE_BASE_URL
#
# Optional (override instrument CSV):
# INSTRUMENTS_URL = https://images.dhan.co/api-data/api-scrip-master-detailed.csv
#
# WEBHOOK_SECRET = <your secret>

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any, List
from datetime import datetime
import os, csv, io, requests

# ───────────────────────────────────────────────────────────
# App & CORS
# ───────────────────────────────────────────────────────────
app = FastAPI(title="Options Analysis API", version="3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ───────────────────────────────────────────────────────────
# ENV & constants
# ───────────────────────────────────────────────────────────
MODE = os.getenv("MODE", "DRY").upper()                 # DRY / LIVE
DHAN_ENV = os.getenv("DHAN_ENV", "SANDBOX").upper()     # SANDBOX / LIVE
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")

# per-env creds
ENV_MAP = {
    "SANDBOX": {
        "CLIENT_ID":     os.getenv("DHAN_SANDBOX_CLIENT_ID", ""),
        "ACCESS_TOKEN":  os.getenv("DHAN_SANDBOX_ACCESS_TOKEN", ""),
        "BASE_URL":      os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2"),
    },
    "LIVE": {
        "CLIENT_ID":     os.getenv("DHAN_LIVE_CLIENT_ID", ""),
        "ACCESS_TOKEN":  os.getenv("DHAN_LIVE_ACCESS_TOKEN", ""),
        "BASE_URL":      os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2"),
    },
}

INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
)

# ───────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────
def active_env() -> Dict[str, str]:
    env = ENV_MAP.get(DHAN_ENV, ENV_MAP["SANDBOX"])
    return env

def broker_ready() -> bool:
    env = active_env()
    return bool(env["CLIENT_ID"] and env["ACCESS_TOKEN"] and env["BASE_URL"])

def dhan_headers() -> Dict[str, str]:
    if not broker_ready():
        raise HTTPException(status_code=500, detail="Dhan credentials missing")
    env = active_env()
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "client-id": env["CLIENT_ID"],
        "access-token": env["ACCESS_TOKEN"],
    }

def dhan_base_url() -> str:
    return active_env()["BASE_URL"]

def fetch_instruments_csv() -> str:
    r = requests.get(INSTRUMENTS_URL, timeout=30)
    r.raise_for_status()
    return r.text

def _norm_option_type(s: str) -> str:
    if not s:
        return ""
    s = s.strip().upper()
    # accept CE/PE/CALL/PUT
    return {"CE": "CALL", "PE": "PUT", "CALL": "CALL", "PUT": "PUT"}.get(s, s)

def list_expiries_from_csv(symbol: str) -> List[str]:
    txt = fetch_instruments_csv()
    f = io.StringIO(txt)
    reader = csv.DictReader(f)
    sym = (symbol or "").upper().strip()
    exp_set = set()
    for row in reader:
        if row.get("UNDERLYING_SYMBOL", "").upper().strip() == sym:
            exp = (row.get("SEM_EXPIRY_DATE") or "").strip()
            if exp:
                exp_set.add(exp)
    return sorted(exp_set)

def list_strikes_from_csv(symbol: str, expiry: str, option_type: str) -> List[float]:
    txt = fetch_instruments_csv()
    f = io.StringIO(txt)
    reader = csv.DictReader(f)
    sym = (symbol or "").upper().strip()
    otype = _norm_option_type(option_type)
    exp = (expiry or "").strip()
    strikes = []
    for row in reader:
        if (
            row.get("UNDERLYING_SYMBOL", "").upper().strip() == sym
            and (row.get("SEM_EXPIRY_DATE") or "").strip() == exp
            and _norm_option_type(row.get("SEM_OPTION_TYPE", "")) == otype
        ):
            try:
                sp = float(row.get("SEM_STRIKE_PRICE") or 0.0)
                strikes.append(sp)
            except Exception:
                pass
    return sorted(set(strikes))

def lookup_security_id(symbol: str, expiry: str, strike: float, option_type: str) -> Optional[str]:
    """
    Returns first matching Security ID or None.
    Tries common id columns: SECURITY_ID / SEM_SECURITY_ID / SM_SECURITY_ID
    """
    txt = fetch_instruments_csv()
    f = io.StringIO(txt)
    reader = csv.DictReader(f)

    header = reader.fieldnames or []
    sec_id_col = None
    for c in ("SECURITY_ID", "SEM_SECURITY_ID", "SM_SECURITY_ID"):
        if c in header:
            sec_id_col = c
            break

    sym = (symbol or "").upper().strip()
    otype = _norm_option_type(option_type)
    exp = (expiry or "").strip()

    for row in reader:
        try:
            if (
                row.get("UNDERLYING_SYMBOL", "").upper().strip() == sym
                and (row.get("SEM_EXPIRY_DATE") or "").strip() == exp
                and _norm_option_type(row.get("SEM_OPTION_TYPE", "")) == otype
            ):
                sp = float(row.get("SEM_STRIKE_PRICE") or 0.0)
                if abs(sp - float(strike)) < 1e-6:
                    return str(row.get(sec_id_col)) if sec_id_col else None
        except Exception:
            continue
    return None

def place_dhan_order(
    security_id: str,
    side: str,                       # BUY / SELL
    qty: int,
    order_type: str = "MARKET",      # MARKET / LIMIT
    price: Optional[float] = None,
    product_type: str = "INTRADAY",
    exchange_segment: str = "NSE_FNO",
    validity: str = "DAY",
    tag: Optional[str] = None,
) -> (int, Dict[str, Any]):
    url = f"{dhan_base_url()}/orders"
    payload: Dict[str, Any] = {
        "transaction_type": side.upper(),          # BUY/SELL
        "exchange_segment": exchange_segment,      # NSE_FNO
        "product_type": product_type,              # INTRADAY
        "order_type": order_type.upper(),          # MARKET/LIMIT
        "validity": validity,                      # DAY
        "security_id": str(security_id),
        "quantity": int(qty),
    }
    if tag:
        payload["correlation_id"] = str(tag)
    if payload["order_type"] == "LIMIT" and price is not None:
        payload["price"] = float(price)

    r = requests.post(url, headers=dhan_headers(), json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"text": r.text}
    return r.status_code, data

def dhan_quote_snapshot(body: dict) -> dict:
    url = f"{dhan_base_url()}/marketfeed/quote"
    r = requests.post(url, headers=dhan_headers(), json=body, timeout=20)
    r.raise_for_status()
    return r.json()

# ───────────────────────────────────────────────────────────
# Routes
# ───────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/broker_status")
def broker_status():
    env = active_env()
    return {
        "mode": MODE,
        "env": DHAN_ENV,
        "base_url": env["BASE_URL"],
        "has_creds": broker_ready(),
        "client_id_present": bool(env["CLIENT_ID"]),
        "token_present": bool(env["ACCESS_TOKEN"]),
    }

# CSV helpers for cross-check
@app.get("/list_expiries")
def list_expiries(symbol: str):
    exps = list_expiries_from_csv(symbol)
    return {"symbol": symbol.upper(), "expiries": exps}

@app.get("/list_strikes")
def list_strikes(symbol: str, expiry: str, option_type: str):
    strikes = list_strikes_from_csv(symbol, expiry, option_type)
    return {
        "symbol": symbol.upper(),
        "expiry": expiry,
        "option_type": _norm_option_type(option_type),
        "strikes": strikes,
    }

# security id lookup
@app.get("/security_lookup")
def usage_security_lookup():
    return {
        "use": "POST /security_lookup with JSON body",
        "example": {
            "symbol": "NIFTY",
            "expiry": "2025-08-28",
            "strike": 25100,
            "option_type": "CALL",
        },
    }

@app.post("/security_lookup")
async def security_lookup(payload: dict):
    sec_id = lookup_security_id(
        payload.get("symbol", ""),
        payload.get("expiry", ""),
        payload.get("strike", 0),
        payload.get("option_type", ""),
    )
    return {"security_id": sec_id}

# quotes
@app.post("/dhan/quote")
async def dhan_quote(body: dict):
    try:
        return dhan_quote_snapshot(body)
    except requests.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

# webhook (TV / manual)
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    # 1) Secret check
    if str(data.get("secret", "")) != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 2) Parse
    symbol = data.get("symbol")
    action = str(data.get("action", "")).upper()       # BUY/SELL
    expiry = data.get("expiry")
    strike = data.get("strike")
    option_type = _norm_option_type(data.get("option_type", ""))
    qty = int(data.get("qty", 0))
    price = data.get("price", "MARKET")
    security_id = data.get("security_id")

    if not symbol or not action or qty <= 0:
        raise HTTPException(422, detail="symbol/action/qty required")

    # DRY: simulate
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

    # LIVE: ensure creds
    if not broker_ready():
        raise HTTPException(500, detail="Broker credentials not configured")

    # LIVE: ensure security id
    if not security_id:
        security_id = lookup_security_id(symbol, expiry, strike, option_type)
        if not security_id:
            raise HTTPException(400, detail="security_id not found")

    # order type
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
    except Exception:
        order_type = "MARKET"

    # place order
    tag = f"tv-{datetime.utcnow().isoformat()}"
    status, broker_resp = place_dhan_order(
        security_id=str(security_id),
        side=action,
        qty=qty,
        order_type=order_type,
        price=limit_price,
        product_type="INTRADAY",
        exchange_segment="NSE_FNO",
        validity="DAY",
        tag=tag,
    )

    return {"ok": status in (200, 201), "mode": "LIVE", "received": data, "dhan_response": broker_resp}
