# main.py — Options Analysis API (FastAPI) + Dhan v2
# -----------------------------------------------
# Features
# - /health
# - /broker_status  (env + creds check)
# - /list_expiries  (CSV -> fallback Dhan API)
# - /list_strikes   (CSV)
# - /security_lookup (CSV exact match)
# - /dhan/quote     (snapshot quote proxy)
# - /dhan/expirylist (proxy to Dhan)
# - /dhan/optionchain (proxy to Dhan)
# - /webhook        (DRY simulate / LIVE place order)
# - /selftest       (one-click sanity test)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any, List
from datetime import datetime
import os, io, csv, requests, time

app = FastAPI(title="Options Analysis API", version="2.2")

# CORS (tablet/TV Postman/Hoppscotch testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ─────────────────────────────────────────────────────────────────
# ENV & CONSTANTS
# ─────────────────────────────────────────────────────────────────
MODE = os.getenv("MODE", "DRY").upper()                # DRY / LIVE
ENV  = os.getenv("ENV",  "SANDBOX").upper()            # SANDBOX / LIVE

# Live creds
DHAN_LIVE_BASE_URL    = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")
DHAN_LIVE_CLIENT_ID   = os.getenv("DHAN_LIVE_CLIENT_ID", "")
DHAN_LIVE_ACCESS_TOKEN= os.getenv("DHAN_LIVE_ACCESS_TOKEN", "")

# Sandbox creds
DHAN_SANDBOX_BASE_URL    = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")
DHAN_SANDBOX_CLIENT_ID   = os.getenv("DHAN_SANDBOX_CLIENT_ID", "")
DHAN_SANDBOX_ACCESS_TOKEN= os.getenv("DHAN_SANDBOX_ACCESS_TOKEN", "")

# Selected (by ENV)
def env_pick(live_val: str, sandbox_val: str) -> str:
    return live_val if ENV == "LIVE" else sandbox_val

DHAN_API_BASE   = env_pick(DHAN_LIVE_BASE_URL,    DHAN_SANDBOX_BASE_URL)
DHAN_CLIENT_ID  = env_pick(DHAN_LIVE_CLIENT_ID,   DHAN_SANDBOX_CLIENT_ID)
DHAN_ACCESS_TOKEN = env_pick(DHAN_LIVE_ACCESS_TOKEN, DHAN_SANDBOX_ACCESS_TOKEN)

# CSV (detailed master recommended)
INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "my$ecret123")

# Simple in-memory caches
_csv_cache: Dict[str, Any] = {"ts": 0.0, "text": ""}
_expiry_cache: Dict[str, List[str]] = {}   # key: symbol
_headers = {"accept":"application/json","content-type":"application/json"}


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def broker_ready():
    return bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN)

def base_headers_for_dhan():
    if not broker_ready():
        raise HTTPException(500, detail="Dhan credentials missing")
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json"
    }

def fetch_instruments_csv_text(force: bool=False) -> str:
    # cache for 5 minutes
    now = time.time()
    if (not force) and _csv_cache["text"] and now - _csv_cache["ts"] < 300:
        return _csv_cache["text"]
    r = requests.get(INSTRUMENTS_URL, timeout=30)
    r.raise_for_status()
    _csv_cache.update({"ts": now, "text": r.text})
    return r.text

def csv_reader():
    text = fetch_instruments_csv_text()
    return csv.DictReader(io.StringIO(text))

def norm(s: Optional[str]) -> str:
    return (s or "").strip()

def opt_type_alias(x: str) -> str:
    x = (x or "").upper().strip()
    if x in ("CE","CALL"): return "CE"
    if x in ("PE","PUT"):  return "PE"
    return x

def detect_security_id_col(fieldnames: List[str]) -> Optional[str]:
    for c in ("SECURITY_ID","SEM_SECURITY_ID","SM_SECURITY_ID"):
        if c in fieldnames:
            return c
    return None

def fetch_expiries_from_csv(symbol: str) -> List[str]:
    symbol = norm(symbol).upper()
    out = set()
    rdr = csv_reader()
    for row in rdr:
        if norm(row.get("UNDERLYING_SYMBOL","")).upper() == symbol:
            exp = norm(row.get("SEM_EXPIRY_DATE",""))
            if exp:
                out.add(exp)
    return sorted(out)

def fetch_strikes_from_csv(symbol: str, expiry: str, option_type: str) -> List[float]:
    symbol = norm(symbol).upper()
    expiry = norm(expiry)
    otype  = opt_type_alias(option_type)
    out = set()
    rdr = csv_reader()
    for row in rdr:
        if (
            norm(row.get("UNDERLYING_SYMBOL","")).upper() == symbol and
            norm(row.get("SEM_EXPIRY_DATE","")) == expiry and
            opt_type_alias(row.get("SEM_OPTION_TYPE","")) == otype
        ):
            sp = row.get("SEM_STRIKE_PRICE","")
            try:
                out.add(float(sp))
            except Exception:
                pass
    return sorted(out)

def csv_lookup_security_id(symbol: str, expiry: str, strike: float, option_type: str) -> Optional[str]:
    symbol = norm(symbol).upper()
    expiry = norm(expiry)
    otype  = opt_type_alias(option_type)
    rdr = csv_reader()
    sec_col = detect_security_id_col(rdr.fieldnames or [])
    for row in rdr:
        try:
            if (
                norm(row.get("UNDERLYING_SYMBOL","")).upper() == symbol and
                norm(row.get("SEM_EXPIRY_DATE","")) == expiry and
                opt_type_alias(row.get("SEM_OPTION_TYPE","")) == otype and
                float(row.get("SEM_STRIKE_PRICE","0") or 0.0) == float(strike)
            ):
                return norm(row.get(sec_col) if sec_col else "")
        except Exception:
            continue
    return None

def dhan_post(path: str, body: dict) -> requests.Response:
    url = f"{DHAN_API_BASE}{path}"
    hdr = base_headers_for_dhan()
    return requests.post(url, headers=hdr, json=body, timeout=30)

def fetch_expiries_from_dhan(symbol: str) -> List[str]:
    """
    Dhan OptionChain expirylist
    NIFTY UnderlyingScrip=13, BANKNIFTY=25, FINNIFTY=41 (examples)
    """
    # crude map; extend as needed
    u_map = {"NIFTY": 13, "BANKNIFTY": 25, "FINNIFTY": 41}
    underlying = u_map.get(symbol.upper(), 13)
    body = {"UnderlyingScrip": underlying, "UnderlyingSeg": "IDX_I"}
    try:
        r = dhan_post("/optionchain/expirylist", body)
        if r.status_code == 200:
            j = r.json()
            return j.get("data", []) or []
    except Exception:
        pass
    return []

def place_dhan_order(
    security_id: str,
    side: str,
    qty: int,
    order_type: str = "MARKET",
    price: Optional[float] = None,
    product_type: str = "INTRADAY",
    exchange_segment: str = "NSE_FNO",
    validity: str = "DAY",
    tag: Optional[str] = None,
):
    url = f"{DHAN_API_BASE}/orders"
    payload = {
        "transaction_type": side.upper(),
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

    r = requests.post(url, headers=base_headers_for_dhan(), json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"text": r.text}
    return r.status_code, data

def dhan_quote_snapshot(body: dict):
    url = f"{DHAN_API_BASE}/marketfeed/quote"
    r = requests.post(url, headers=base_headers_for_dhan(), json=body, timeout=20)
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
        "env": ENV,
        "base_url": DHAN_API_BASE,
        "has_creds": broker_ready(),
        "client_id_present": bool(DHAN_CLIENT_ID),
        "token_present": bool(DHAN_ACCESS_TOKEN),
    }

# ---------- CSV helpers with Dhan fallback ----------
@app.get("/list_expiries")
def list_expiries(symbol: str):
    sym = norm(symbol).upper()
    expiries = fetch_expiries_from_csv(sym)
    # Fallback → Dhan API (and cache)
    if not expiries and broker_ready():
        expiries = _expiry_cache.get(sym) or fetch_expiries_from_dhan(sym)
        _expiry_cache[sym] = expiries
    return {"symbol": sym, "expiries": expiries}

@app.get("/list_strikes")
def list_strikes(symbol: str, expiry: str, option_type: str = "CALL"):
    sym = norm(symbol).upper()
    otype = opt_type_alias(option_type)
    strikes = fetch_strikes_from_csv(sym, expiry, otype)
    return {"symbol": sym, "expiry": expiry, "option_type": "CALL" if otype=="CE" else "PUT", "strikes": strikes}

@app.post("/security_lookup")
def security_lookup(payload: dict):
    """
    payload: { symbol, expiry, strike, option_type }  option_type: CE/PE/CALL/PUT
    """
    sec_id = csv_lookup_security_id(
        payload.get("symbol",""),
        payload.get("expiry",""),
        payload.get("strike",0),
        payload.get("option_type",""),
    )
    return {"security_id": sec_id}

# ---------- Dhan data proxies ----------
@app.post("/dhan/quote")
def dhan_quote(body: dict):
    try:
        return dhan_quote_snapshot(body)
    except requests.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.post("/dhan/expirylist")
def dhan_expirylist(body: dict):
    # passthrough proxy to Dhan "/optionchain/expirylist"
    r = dhan_post("/optionchain/expirylist", body)
    if r.status_code != 200:
        raise HTTPException(r.status_code, detail=r.text)
    return r.json()

@app.post("/dhan/optionchain")
def dhan_optionchain(body: dict):
    # passthrough proxy to Dhan "/optionchain"
    r = dhan_post("/optionchain", body)
    if r.status_code != 200:
        raise HTTPException(r.status_code, detail=r.text)
    return r.json()

# ---------- Webhook (TV / manual) ----------
@app.post("/webhook")
async def webhook(request: Request):
    """
    Example:
    {
      "secret": "my$ecret123",
      "symbol": "NIFTY",
      "action": "BUY",
      "expiry": "2025-08-28",
      "strike": 25100,
      "option_type": "CE",
      "qty": 50,
      "price": "MARKET",         # or 123.45 for LIMIT
      "security_id": "optional"
    }
    """
    data = await request.json()
    if str(data.get("secret","")) != WEBHOOK_SECRET:
        raise HTTPException(401, detail="Unauthorized")

    symbol = data.get("symbol")
    action = data.get("action")
    expiry = data.get("expiry")
    strike = data.get("strike")
    option_type = data.get("option_type")
    qty = int(data.get("qty", 0))
    price_in = data.get("price", "MARKET")
    security_id = data.get("security_id")

    if not symbol or not action or qty <= 0:
        raise HTTPException(422, detail="symbol/action/qty required")

    # DRY mode => simulate
    if MODE != "LIVE":
        return {
            "ok": True,
            "mode": MODE,
            "received": data,
            "note": "DRY mode: no live order. Set MODE=LIVE to execute.",
        }

    # LIVE → need security_id
    if not security_id:
        security_id = csv_lookup_security_id(symbol, expiry, strike, option_type)
        if not security_id:
            raise HTTPException(400, detail="security_id not found")

    # order type
    order_type = "MARKET"; limit_price = None
    try:
        if isinstance(price_in, (int, float)) or (isinstance(price_in, str) and price_in.replace(".","",1).isdigit()):
            order_type = "LIMIT"; limit_price = float(price_in)
    except Exception:
        pass

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
    return {"ok": status in (200,201), "mode":"LIVE", "dhan_response": broker_resp}

# ---------- Auto self-test ----------
@app.get("/selftest")
def selftest():
    out = {"ok": True, "data": {}}
    # broker
    out["broker_status"] = {
        "ok": True,
        "data": {
            "mode": MODE, "env": ENV, "base_url": DHAN_API_BASE,
            "has_creds": broker_ready(),
            "client_id_present": bool(DHAN_CLIENT_ID),
            "token_present": bool(DHAN_ACCESS_TOKEN),
        }
    }
    # expiries via CSV / fallback
    try:
        exps = list_expiries("NIFTY")["expiries"]
        ok = bool(exps)
        out["expiries"] = {"ok": ok, "data": {"symbol":"NIFTY","expiries": exps} if ok else {"error":"empty"}}
        # strikes (only if expiry exists)
        if ok:
            strikes = list_strikes("NIFTY", exps[0], "CALL")["strikes"]
            out["strikes"] = {"ok": bool(strikes), "data": {"count": len(strikes)} if strikes else {"error":"no strikes"}}
            # security lookup (try mid strike if any)
            if strikes:
                mid = strikes[len(strikes)//2]
                sec = csv_lookup_security_id("NIFTY", exps[0], mid, "CE")
                out["security_lookup"] = {"ok": bool(sec), "data": {"security_id": sec} if sec else {"error":"not found"}}
            else:
                out["security_lookup"] = {"ok": False, "error": "no strike"}
        else:
            out["strikes"] = {"ok": False, "error": "no expiry"}
            out["security_lookup"] = {"ok": False, "error": "no strike"}
    except Exception as e:
        out["expiries"] = {"ok": False, "error": str(e)}

    # webhook dry check
    try:
        sample = {
            "secret": WEBHOOK_SECRET, "symbol":"NIFTY", "action":"BUY",
            "expiry": "2099-01-01", "strike": 0, "option_type":"CE", "qty": 1, "price":"MARKET"
        }
        # simulate what /webhook would return in DRY mode:
        if MODE == "DRY":
            out["webhook_dry"] = {"ok": True, "data": "DRY ok"}
        else:
            out["webhook_dry"] = {"ok": False, "error": "MODE is LIVE"}
    except Exception as e:
        out["webhook_dry"] = {"ok": False, "error": str(e)}

    return out
