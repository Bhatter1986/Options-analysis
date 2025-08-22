# main.py — Dhan REST integration + CSV-backed lookups (FastAPI)

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
import os, csv, io, time, requests
from datetime import datetime

app = FastAPI(title="Options Analysis API", version="2.1")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ─────────────────────────────────────────────────────────────────
# ENV & CONSTANTS
# ─────────────────────────────────────────────────────────────────
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
MODE = os.getenv("MODE", "DRY").upper()  # DRY / LIVE

DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
DHAN_API_BASE = "https://api.dhan.co/v2"     # sandbox: https://sandbox.dhan.co/v2

# Dhan scrip-master (detailed) — isme expiry/strike/option_type/security_id sab hote hain
INSTR_CSV_DETAILED = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

# CSV cache (memory)
_CSV_CACHE: Dict[str, Any] = {"ts": 0.0, "rows": []}
CSV_TTL_SEC = 15 * 60  # 15 minutes

# Common CSV column names (detailed master)
COL_UNDERLYING = "UNDERLYING_SYMBOL"
COL_EXPIRY     = "SEM_EXPIRY_DATE"
COL_STRIKE     = "SEM_STRIKE_PRICE"
COL_OPT_TYPE   = "SEM_OPTION_TYPE"
SEC_ID_CANDIDATES = ("SECURITY_ID", "SEM_SECURITY_ID", "SM_SECURITY_ID")


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

def _download_csv_text(url: str) -> str:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text

def _load_csv_rows(force: bool = False) -> List[Dict[str, Any]]:
    """Load & cache detailed scrip master rows."""
    now = time.time()
    if (not force) and _CSV_CACHE["rows"] and (now - _CSV_CACHE["ts"] < CSV_TTL_SEC):
        return _CSV_CACHE["rows"]

    text = _download_csv_text(INSTR_CSV_DETAILED)
    f = io.StringIO(text)
    reader = csv.DictReader(f)
    rows = []
    for row in reader:
        rows.append(row)
    _CSV_CACHE["rows"] = rows
    _CSV_CACHE["ts"] = now
    return rows

def _security_id_column(fieldnames: List[str]) -> Optional[str]:
    for c in SEC_ID_CANDIDATES:
        if c in fieldnames:
            return c
    return None

def list_expiries_for_symbol(symbol: str) -> List[str]:
    rows = _load_csv_rows()
    sym = (symbol or "").upper().strip()
    expiries = set()
    for r in rows:
        if (r.get(COL_UNDERLYING,"").upper().strip() == sym):
            e = (r.get(COL_EXPIRY) or "").strip()
            if e:
                expiries.add(e)
    # sort ascending (YYYY-MM-DD)
    return sorted(expiries)

def list_strikes_for(symbol: str, expiry: str, option_type: Optional[str]=None) -> List[float]:
    rows = _load_csv_rows()
    sym = (symbol or "").upper().strip()
    exp = (expiry or "").strip()
    ot  = (option_type or "").upper().strip() if option_type else None

    strikes = set()
    for r in rows:
        if r.get(COL_UNDERLYING,"").upper().strip() != sym: 
            continue
        if (r.get(COL_EXPIRY) or "").strip() != exp:
            continue
        if ot and (r.get(COL_OPT_TYPE,"").upper().strip() != ot):
            continue
        try:
            val = float(r.get(COL_STRIKE) or "0")
            if val > 0:
                strikes.add(val)
        except Exception:
            continue
    return sorted(strikes)

def lookup_security_id(underlying_symbol: str, expiry: str, strike: float, option_type: str):
    """
    Returns first matching Security ID or None from detailed csv.
    """
    text = _download_csv_text(INSTR_CSV_DETAILED)  # fresh pull for accuracy
    f = io.StringIO(text)
    reader = csv.DictReader(f)
    sec_col = _security_id_column(reader.fieldnames or [])

    sym = (underlying_symbol or "").upper().strip()
    otype = (option_type or "").upper().strip()
    exp = (expiry or "").strip()
    target_strike = float(strike)

    for row in reader:
        try:
            if (
                (row.get(COL_UNDERLYING,"").upper().strip() == sym) and
                (row.get(COL_EXPIRY,"").strip() == exp) and
                (row.get(COL_OPT_TYPE,"").upper().strip() == otype) and
                (float(row.get(COL_STRIKE,"0") or 0.0) == target_strike)
            ):
                return (row.get(sec_col) if sec_col else None)
        except Exception:
            continue
    return None

def place_dhan_order(
    security_id: str,
    side: str,                 # BUY / SELL
    qty: int,
    order_type: str = "MARKET",# MARKET / LIMIT
    price: Optional[float] = None,
    product_type: str = "INTRADAY",
    exchange_segment: str = "NSE_FNO",
    validity: str = "DAY",
    tag: Optional[str] = None,
):
    """Minimal place order to Dhan v2."""
    url = f"{DHAN_API_BASE}/orders"
    payload = {
        "transaction_type": side,              # BUY/SELL
        "exchange_segment": exchange_segment,  # e.g. NSE_FNO
        "product_type": product_type,          # e.g. INTRADAY
        "order_type": order_type,              # MARKET/LIMIT
        "validity": validity,                  # DAY/IOC
        "security_id": str(security_id),
        "quantity": int(qty),
    }
    if tag:
        payload["correlation_id"] = str(tag)
    if order_type == "LIMIT" and (price is not None):
        payload["price"] = float(price)

    r = requests.post(url, headers=dhan_headers(), json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"text": r.text}
    return r.status_code, data

def dhan_quote_snapshot(body: dict):
    """Calls /marketfeed/quote for snapshot (LTP, OHLC, depth, OI)."""
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

# NEW: list expiries for an underlying (from CSV)
@app.get("/list_expiries")
def list_expiries(symbol: str = Query(..., description="e.g. NIFTY / BANKNIFTY")):
    try:
        expiries = list_expiries_for_symbol(symbol)
        return {"symbol": symbol.upper(), "expiries": expiries}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

# NEW: list strikes for symbol+expiry (+optional option_type)
@app.get("/list_strikes")
def list_strikes(
    symbol: str = Query(...),
    expiry: str = Query(..., description="YYYY-MM-DD"),
    option_type: Optional[str] = Query(None, description="CE/PE (optional)"),
):
    try:
        strikes = list_strikes_for(symbol, expiry, option_type)
        return {
            "symbol": symbol.upper(),
            "expiry": expiry,
            "option_type": (option_type.upper() if option_type else None),
            "strikes": strikes,
        }
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/security_lookup")
async def security_lookup(payload: dict):
    """
    Payload:
    {
      "symbol": "NIFTY",
      "expiry": "YYYY-MM-DD",
      "strike": 25100,
      "option_type": "CE"
    }
    """
    # quick guard: if invalid combo, return None fast
    exp_list = list_expiries_for_symbol(payload.get("symbol",""))
    if payload.get("expiry") not in exp_list:
        return {"security_id": None}

    sec_id = lookup_security_id(
        payload.get("symbol",""),
        payload.get("expiry",""),
        payload.get("strike",0),
        payload.get("option_type",""),
    )
    return {"security_id": sec_id}

@app.post("/dhan/quote")
async def dhan_quote(body: dict):
    """
    Body example: { "NSE_FNO": [49081] }
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
    if str(data.get("secret","")) != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 2) Parse fields
    symbol = data.get("symbol")
    action = data.get("action")              # BUY/SELL
    expiry = data.get("expiry")              # YYYY-MM-DD
    strike = data.get("strike")
    option_type = data.get("option_type")    # CE/PE
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
                "side": action, "symbol": symbol, "expiry": expiry,
                "strike": strike, "type": option_type, "qty": qty, "price": price,
                "security_id": security_id,
                "note": "DRY mode: no live order. Set MODE=LIVE to execute."
            }
        }

    # LIVE mode → ensure security_id
    if not security_id:
        security_id = lookup_security_id(symbol, expiry, strike, option_type)
        if not security_id:
            raise HTTPException(400, detail="security_id not found")

    # MARKET or LIMIT selection
    order_type = "MARKET"
    limit_price: Optional[float] = None
    try:
        if isinstance(price, (int, float)) or (isinstance(price, str) and price.replace(".","",1).isdigit()):
            order_type = "LIMIT"
            limit_price = float(price)
        elif str(price).upper() == "MARKET":
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
        tag=tag
    )

    return {
        "ok": status in (200, 201),
        "mode": "LIVE",
        "received": data,
        "dhan_response": broker_resp
    }
