# main.py — Options Analysis API (Dhan integration)
# FastAPI app with CSV helpers, Dhan REST, and Option-Chain proxies

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os, csv, io, requests
from datetime import datetime

app = FastAPI(title="Options Analysis API", version="3.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────
# ENV & CONSTANTS
# ─────────────────────────────────────────────────────────────────
MODE = os.getenv("MODE", "DRY").upper()               # DRY / LIVE
ENV_NAME = os.getenv("ENV", "").upper()               # SANDBOX / LIVE (optional)
if not ENV_NAME:
    ENV_NAME = "LIVE" if MODE == "LIVE" else "SANDBOX"

# Live creds
DHAN_LIVE_CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID", "")
DHAN_LIVE_ACCESS_TOKEN = os.getenv("DHAN_LIVE_ACCESS_TOKEN", "")
DHAN_LIVE_BASE_URL = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")

# Sandbox creds
DHAN_SANDBOX_CLIENT_ID = os.getenv("DHAN_SANDBOX_CLIENT_ID", "")
DHAN_SANDBOX_ACCESS_TOKEN = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN", "")
DHAN_SANDBOX_BASE_URL = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")

# CSV instrument (detailed recommended)
INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv",
)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")

# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def _active_base_url() -> str:
    return DHAN_LIVE_BASE_URL if ENV_NAME == "LIVE" else DHAN_SANDBOX_BASE_URL

def _active_client_id_token() -> tuple[str, str]:
    if ENV_NAME == "LIVE":
        return DHAN_LIVE_CLIENT_ID, DHAN_LIVE_ACCESS_TOKEN
    else:
        return DHAN_SANDBOX_CLIENT_ID, DHAN_SANDBOX_ACCESS_TOKEN

def _dhan_headers() -> dict:
    cid, tok = _active_client_id_token()
    if not cid or not tok:
        raise HTTPException(500, detail="Dhan credentials missing for current ENV")
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "client-id": cid,
        "access-token": tok,
    }

def _have_creds() -> bool:
    cid, tok = _active_client_id_token()
    return bool(cid and tok)

def fetch_instruments_csv() -> str:
    r = requests.get(INSTRUMENTS_URL, timeout=30)
    r.raise_for_status()
    return r.text

def _norm_opt_type(s: str) -> str:
    """
    Accept CE/PE or CALL/PUT and normalize to CSV 'CALL'/'PUT'
    """
    x = (s or "").strip().upper()
    if x in ("CE", "CALL"):
        return "CALL"
    if x in ("PE", "PUT"):
        return "PUT"
    return x

# ─────────────────────────────────────────────────────────────────
# CSV helpers
# ─────────────────────────────────────────────────────────────────
@app.get("/list_expiries")
def list_expiries(symbol: str):
    """
    Return all expiries for an underlying symbol using Dhan CSV.
    """
    sym = (symbol or "").upper().strip()
    if not sym:
        return {"symbol": symbol, "expiries": []}

    text = fetch_instruments_csv()
    f = io.StringIO(text)
    reader = csv.DictReader(f)

    expiries = set()
    for row in reader:
        if (row.get("UNDERLYING_SYMBOL", "").upper().strip() == sym) and row.get("SEM_EXPIRY_DATE"):
            expiries.add(row["SEM_EXPIRY_DATE"].strip())

    return {"symbol": sym, "expiries": sorted(expiries)}

@app.get("/list_strikes")
def list_strikes(symbol: str, expiry: str, option_type: str = "CALL"):
    """
    Return all strikes for given underlying/expiry/option_type from CSV.
    option_type accepts CE/PE or CALL/PUT.
    """
    sym = (symbol or "").upper().strip()
    exp = (expiry or "").strip()
    otype = _norm_opt_type(option_type)

    if not sym or not exp or otype not in ("CALL", "PUT"):
        return {"symbol": sym, "expiry": exp, "option_type": otype, "strikes": []}

    text = fetch_instruments_csv()
    f = io.StringIO(text)
    reader = csv.DictReader(f)

    strikes = set()
    for row in reader:
        try:
            if (
                row.get("UNDERLYING_SYMBOL", "").upper().strip() == sym and
                row.get("SEM_EXPIRY_DATE", "").strip() == exp and
                row.get("SEM_OPTION_TYPE", "").upper().strip() == otype
            ):
                sp = row.get("SEM_STRIKE_PRICE", "")
                if sp not in (None, ""):
                    strikes.add(float(sp))
        except Exception:
            continue

    return {
        "symbol": sym,
        "expiry": exp,
        "option_type": otype,
        "strikes": sorted(strikes),
    }

@app.post("/security_lookup")
async def security_lookup(payload: dict):
    """
    POST body:
    {
      "symbol": "NIFTY",
      "expiry": "2025-08-28",
      "strike": 25100,
      "option_type": "CALL"  # CE/PE also allowed
    }
    """
    sym = (payload.get("symbol", "") or "").upper().strip()
    exp = (payload.get("expiry", "") or "").strip()
    otype = _norm_opt_type(payload.get("option_type", ""))
    strike = payload.get("strike", None)

    if not (sym and exp and otype and strike is not None):
        # Show usage for GET in browser
        return {
            "use": "POST /security_lookup",
            "example": {"symbol": "NIFTY", "expiry": "2025-08-28", "strike": 25100, "option_type": "CALL"},
        }

    text = fetch_instruments_csv()
    f = io.StringIO(text)
    reader = csv.DictReader(f)

    # detect security-id column name
    sec_id_col = None
    fields = reader.fieldnames or []
    for c in ("SECURITY_ID", "SEM_SECURITY_ID", "SM_SECURITY_ID"):
        if c in fields:
            sec_id_col = c
            break

    sec_id = None
    for row in reader:
        try:
            if (
                row.get("UNDERLYING_SYMBOL", "").upper().strip() == sym
                and row.get("SEM_EXPIRY_DATE", "").strip() == exp
                and row.get("SEM_OPTION_TYPE", "").upper().strip() == otype
                and float(row.get("SEM_STRIKE_PRICE", "0") or 0.0) == float(strike)
            ):
                sec_id = row.get(sec_id_col) if sec_id_col else None
                if sec_id:
                    break
        except Exception:
            continue

    return {"security_id": sec_id}

# ─────────────────────────────────────────────────────────────────
# Dhan REST helpers (quote) + Option-Chain proxies
# ─────────────────────────────────────────────────────────────────
@app.post("/dhan/quote")
async def dhan_quote(body: dict):
    """
    Snapshot quote via Dhan marketfeed/quote proxy.
    Body example:
    { "NSE_FNO": [71988] }
    """
    url = f"{_active_base_url()}/marketfeed/quote"
    try:
        r = requests.post(url, headers=_dhan_headers(), json=body, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.post("/dhan/expirylist")
async def dhan_expirylist(payload: dict):
    """
    Dhan v2 Option-Chain ExpiryList proxy

    Body:
    {
      "UnderlyingScrip": 13,
      "UnderlyingSeg": "IDX_I"
    }
    """
    url = f"{_active_base_url()}/optionchain/expirylist"
    try:
        r = requests.post(url, headers=_dhan_headers(), json=payload, timeout=20)
        return r.json()
    except requests.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/dhan/optionchain")
async def dhan_optionchain(payload: dict):
    """
    Dhan v2 Option-Chain proxy

    Body:
    {
      "UnderlyingScrip": 13,
      "UnderlyingSeg": "IDX_I",
      "Expiry": "2025-08-28"
    }
    """
    url = f"{_active_base_url()}/optionchain"
    try:
        r = requests.post(url, headers=_dhan_headers(), json=payload, timeout=25)
        return r.json()
    except requests.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

# ─────────────────────────────────────────────────────────────────
# Webhook (TradingView/Manual) — simulate in DRY, place in LIVE
# ─────────────────────────────────────────────────────────────────
def place_dhan_order(
    security_id: str,
    side: str,                         # BUY / SELL
    qty: int,
    order_type: str = "MARKET",        # MARKET / LIMIT
    price: float | None = None,
    product_type: str = "INTRADAY",
    exchange_segment: str = "NSE_FNO",
    validity: str = "DAY",
    tag: str | None = None,
):
    url = f"{_active_base_url()}/orders"
    payload = {
        "transaction_type": side,
        "exchange_segment": exchange_segment,
        "product_type": product_type,
        "order_type": order_type,
        "validity": validity,
        "security_id": str(security_id),
        "quantity": int(qty),
    }
    if tag:
        payload["correlation_id"] = str(tag)
    if order_type == "LIMIT" and (price is not None):
        payload["price"] = float(price)

    r = requests.post(url, headers=_dhan_headers(), json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"text": r.text}
    return r.status_code, data

@app.post("/webhook")
async def webhook(request: Request):
    """
    Example JSON:
    {
      "secret": "my$ecret123",
      "symbol": "NIFTY",
      "action": "BUY",
      "expiry": "2025-08-28",
      "strike": 25100,
      "option_type": "CALL",
      "qty": 50,
      "price": "MARKET",     # or 123.45 for LIMIT
      "security_id": "optional_if_known"
    }
    """
    data = await request.json()

    # Secret check
    if str(data.get("secret", "")) != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    symbol = data.get("symbol")
    action = (data.get("action") or "").upper()
    expiry = data.get("expiry")
    strike = data.get("strike")
    option_type = data.get("option_type")
    qty = int(data.get("qty", 0))
    price = data.get("price", "MARKET")
    security_id = data.get("security_id")

    if not symbol or not action or qty <= 0:
        raise HTTPException(422, detail="symbol/action/qty required")

    # DRY → simulate only
    if MODE != "LIVE":
        return {
            "ok": True,
            "mode": MODE,
            "env": ENV_NAME,
            "received": data,
            "note": "DRY mode: no live order. Set MODE=LIVE to execute.",
        }

    # LIVE → ensure security_id
    if not security_id:
        # try resolve from CSV
        res = await security_lookup({
            "symbol": symbol,
            "expiry": expiry,
            "strike": strike,
            "option_type": option_type
        })
        security_id = res.get("security_id")
        if not security_id:
            raise HTTPException(400, detail="security_id not found")

    # Decide order type
    order_type = "MARKET"
    limit_price = None
    try:
        if isinstance(price, (int, float)) or (isinstance(price, str) and price.replace(".", "", 1).isdigit()):
            order_type = "LIMIT"
            limit_price = float(price)
        elif str(price).upper() == "MARKET":
            order_type = "MARKET"
    except Exception:
        order_type = "MARKET"

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

    return {
        "ok": status in (200, 201),
        "mode": MODE,
        "env": ENV_NAME,
        "received": data,
        "dhan_response": broker_resp,
    }

# ─────────────────────────────────────────────────────────────────
# Misc routes
# ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/broker_status")
def broker_status():
    cid, tok = _active_client_id_token()
    return {
        "mode": MODE,
        "env": ENV_NAME,
        "base_url": _active_base_url(),
        "has_creds": bool(cid and tok),
        "client_id_present": bool(cid),
        "token_present": bool(tok),
    }
