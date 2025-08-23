# main.py — Options Analysis + DhanHQ v2 integration (FastAPI)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any
from datetime import datetime
import os, csv, io, requests, json

app = FastAPI(title="Options Analysis API", version="2.1")

# ─────────────────────────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ─────────────────────────────────────────────────────────────────
# ENV & CONFIG
# ─────────────────────────────────────────────────────────────────
MODE = os.getenv("MODE", "DRY").upper()                   # DRY or LIVE
ENV_ = os.getenv("ENV", "SANDBOX").upper()                # LIVE or SANDBOX

# Live
DHAN_LIVE_BASE_URL   = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")
DHAN_LIVE_CLIENT_ID  = os.getenv("DHAN_LIVE_CLIENT_ID", "")
DHAN_LIVE_ACCESS_TOKEN = os.getenv("DHAN_LIVE_ACCESS_TOKEN", "")

# Sandbox
DHAN_SANDBOX_BASE_URL  = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")
DHAN_SANDBOX_CLIENT_ID = os.getenv("DHAN_SANDBOX_CLIENT_ID", "")
DHAN_SANDBOX_ACCESS_TOKEN = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN", "")

# CSV (detailed master has all needed columns)
INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")

# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def current_dhan_base() -> str:
    return DHAN_LIVE_BASE_URL if ENV_ == "LIVE" else DHAN_SANDBOX_BASE_URL

def current_client_id() -> str:
    return DHAN_LIVE_CLIENT_ID if ENV_ == "LIVE" else DHAN_SANDBOX_CLIENT_ID

def current_access_token() -> str:
    return DHAN_LIVE_ACCESS_TOKEN if ENV_ == "LIVE" else DHAN_SANDBOX_ACCESS_TOKEN

def broker_ready() -> bool:
    return bool(current_client_id() and current_access_token())

def dhan_headers() -> Dict[str, str]:
    if not broker_ready():
        raise HTTPException(500, detail="Dhan credentials missing for selected ENV")
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "client-id": current_client_id(),
        "access-token": current_access_token(),
    }

def fetch_instruments_csv() -> str:
    r = requests.get(INSTRUMENTS_URL, timeout=45)
    r.raise_for_status()
    return r.text

def _norm_expiry(s: str) -> str:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d/%b/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return s

def _norm_otype(s: str) -> str:
    s = (s or "").strip().upper()
    if s in ("CALL", "C"): return "CE"
    if s in ("PUT", "P"):  return "PE"
    if s in ("CE", "PE"):  return s
    return s

def _float_eq(a: float, b: float, tol: float = 1e-6) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False

def lookup_security_id(underlying_symbol: str, expiry: str, strike: float, option_type: str) -> Optional[str]:
    """
    Robust Security ID lookup from detailed CSV.
    Matches on: UNDERLYING_SYMBOL, SEM_EXPIRY_DATE, SEM_OPTION_TYPE, SEM_STRIKE_PRICE
    """
    csv_text = fetch_instruments_csv()
    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)

    # find security id column
    sec_id_col = None
    for c in ("SECURITY_ID", "SEM_SECURITY_ID", "SM_SECURITY_ID"):
        if c in (reader.fieldnames or []):
            sec_id_col = c
            break

    sym   = (underlying_symbol or "").upper().strip()
    exp   = _norm_expiry(expiry)
    otype = _norm_otype(option_type)

    k_sym, k_exp, k_ot, k_strk = "UNDERLYING_SYMBOL", "SEM_EXPIRY_DATE", "SEM_OPTION_TYPE", "SEM_STRIKE_PRICE"

    best = None
    for row in reader:
        try:
            if row.get(k_sym, "").upper().strip() != sym:
                continue
            if row.get(k_ot, "").upper().strip() != otype:
                continue
            if row.get(k_exp, "").strip() != exp:
                continue

            rs = row.get(k_strk, "") or "0"
            rs_val = float(rs)
            if _float_eq(rs_val, float(strike)) or _float_eq(rs_val, float(int(strike))) or _float_eq(rs_val, round(float(strike), 2)):
                best = row.get(sec_id_col) if sec_id_col else None
                if best:
                    return best
        except Exception:
            continue
    return best

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
    url = f"{current_dhan_base()}/orders"
    payload: Dict[str, Any] = {
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
    if order_type == "LIMIT" and price is not None:
        payload["price"] = float(price)

    r = requests.post(url, headers=dhan_headers(), json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"text": r.text}
    return r.status_code, data

def dhan_quote_snapshot(body: dict):
    """
    POST /marketfeed/quote
    body example: { "NSE_FNO": [49081, 49082] }
    """
    url = f"{current_dhan_base()}/marketfeed/quote"
    r = requests.post(url, headers=dhan_headers(), json=body, timeout=20)
    r.raise_for_status()
    return r.json()

# ─────────────────────────────────────────────────────────────────
# Routes — health & status
# ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "env": ENV_,
        "base_url": current_dhan_base(),
        "has_creds": broker_ready(),
        "client_id_present": bool(current_client_id()),
        "token_present": bool(current_access_token()),
    }

# ─────────────────────────────────────────────────────────────────
# CSV helper routes
# ─────────────────────────────────────────────────────────────────
@app.get("/list_expiries")
def list_expiries(symbol: str):
    csv_text = fetch_instruments_csv()
    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)
    sym = (symbol or "").upper().strip()
    s = set()
    for row in reader:
        if row.get("UNDERLYING_SYMBOL","").upper().strip() == sym:
            ex = row.get("SEM_EXPIRY_DATE","").strip()
            if ex:
                s.add(ex)
    return {"symbol": sym, "expiries": sorted(s)}

@app.get("/list_strikes")
def list_strikes(symbol: str, expiry: str, option_type: str):
    csv_text = fetch_instruments_csv()
    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)
    sym = (symbol or "").upper().strip()
    exp = _norm_expiry(expiry)
    otype = _norm_otype(option_type)
    strikes = []
    for row in reader:
        if (
            row.get("UNDERLYING_SYMBOL","").upper().strip() == sym and
            row.get("SEM_EXPIRY_DATE","").strip() == exp and
            row.get("SEM_OPTION_TYPE","").upper().strip() == otype
        ):
            try:
                strikes.append(float(row.get("SEM_STRIKE_PRICE","0") or 0))
            except Exception:
                pass
    return {"symbol": sym, "expiry": exp, "option_type": otype, "strikes": sorted(strikes)}

@app.get("/csv_debug")
def csv_debug(symbol: str, expiry: str, option_type: str):
    csv_text = fetch_instruments_csv()
    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)
    sym = (symbol or "").upper().strip()
    exp = _norm_expiry(expiry)
    otype = _norm_otype(option_type)
    sec_id_col = None
    for c in ("SECURITY_ID","SEM_SECURITY_ID","SM_SECURITY_ID"):
        if c in (reader.fieldnames or []): sec_id_col = c; break
    strikes, sample = [], []
    for row in reader:
        if (
            row.get("UNDERLYING_SYMBOL","").upper().strip()==sym and
            row.get("SEM_EXPIRY_DATE","").strip()==exp and
            row.get("SEM_OPTION_TYPE","").upper().strip()==otype
        ):
            try:
                strikes.append(float(row.get("SEM_STRIKE_PRICE","0") or 0))
            except: pass
            if len(sample)<5:
                sample.append({
                    "strike": row.get("SEM_STRIKE_PRICE"),
                    "sec_id": row.get(sec_id_col) if sec_id_col else None
                })
    return {
        "symbol": sym, "expiry": exp, "option_type": otype,
        "strikes_found": len(strikes),
        "min": min(strikes or [None]), "max": max(strikes or [None]),
        "sample": sample
    }

# ─────────────────────────────────────────────────────────────────
# Security ID lookup
# ─────────────────────────────────────────────────────────────────
@app.post("/security_lookup")
async def security_lookup(payload: dict):
    """
    Body:
    { "symbol":"NIFTY", "expiry":"2025-08-28", "strike":25100, "option_type":"CE|PE|CALL|PUT" }
    """
    sec_id = lookup_security_id(
        payload.get("symbol",""),
        payload.get("expiry",""),
        payload.get("strike",0),
        payload.get("option_type",""),
    )
    return {"security_id": sec_id}

# ─────────────────────────────────────────────────────────────────
# Dhan data APIs (proxy)
# ─────────────────────────────────────────────────────────────────
@app.post("/dhan/quote")
async def dhan_quote(body: dict):
    try:
        return dhan_quote_snapshot(body)
    except requests.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.post("/dhan/optionchain")
async def dhan_optionchain(body: dict):
    """
    Proxy to Dhan /optionchain
    Body example:
    { "UnderlyingScrip": 13, "UnderlyingSeg": "IDX_I", "Expiry": "2025-08-28" }
    """
    url = f"{current_dhan_base()}/optionchain"
    r = requests.post(url, headers=dhan_headers(), json=body, timeout=60)
    return _relay_response(r)

@app.post("/dhan/expirylist")
async def dhan_expirylist(body: dict):
    """
    Proxy to Dhan /optionchain/expirylist
    Body example:
    { "UnderlyingScrip": 13, "UnderlyingSeg": "IDX_I" }
    """
    url = f"{current_dhan_base()}/optionchain/expirylist"
    r = requests.post(url, headers=dhan_headers(), json=body, timeout=30)
    return _relay_response(r)

def _relay_response(r: requests.Response):
    try:
        data = r.json()
    except Exception:
        data = {"text": r.text}
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=data)
    return data

# ─────────────────────────────────────────────────────────────────
# Webhook — DRY sim / LIVE place
# ─────────────────────────────────────────────────────────────────
@app.post("/webhook")
async def webhook(request: Request):
    """
    TradingView / Manual alert body:
    {
      "secret": "my$ecret123",
      "symbol": "NIFTY",
      "action": "BUY",
      "expiry": "2025-08-28",
      "strike": 25100,
      "option_type": "CE",
      "qty": 50,
      "price": "MARKET",      # or numeric for LIMIT
      "security_id": "optional_if_known"
    }
    """
    data = await request.json()

    if str(data.get("secret","")) != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    symbol = data.get("symbol")
    action = data.get("action")
    expiry = data.get("expiry")
    strike = data.get("strike")
    option_type = data.get("option_type")
    qty = int(data.get("qty", 0))
    price = data.get("price", "MARKET")
    security_id = data.get("security_id")

    if not symbol or not action or qty <= 0:
        raise HTTPException(422, detail="symbol/action/qty required")

    # DRY mode → simulate only
    if MODE != "LIVE":
        return {
            "ok": True, "mode": "DRY",
            "received": data,
            "note": "DRY mode: no live order. Set MODE=LIVE to execute."
        }

    # LIVE mode: ensure sec id
    if not security_id:
        security_id = lookup_security_id(symbol, expiry, strike, option_type)
        if not security_id:
            raise HTTPException(400, detail="security_id not found for given symbol/expiry/strike/option_type")

    # MARKET or LIMIT
    order_type = "MARKET"
    limit_price = None
    try:
        if isinstance(price, (int, float)) or (isinstance(price, str) and price.replace(".","",1).isdigit()):
            order_type = "LIMIT"
            limit_price = float(price)
        elif str(price).upper() == "MARKET":
            order_type = "MARKET"
    except Exception:
        order_type = "MARKET"

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
    return {"ok": status in (200, 201), "mode": "LIVE", "received": data, "dhan_response": broker_resp}

@app.get("/selftest")
def selftest():
    """
    Run a sequence of checks automatically.
    Returns JSON with pass/fail and details.
    """
    report = {}

    # 1. Broker status
    try:
        bs = broker_status()
        report["broker_status"] = {"ok": True, "data": bs}
    except Exception as e:
        report["broker_status"] = {"ok": False, "error": str(e)}

    # 2. Expiries check
    try:
        exps = list_expiries("NIFTY")
        report["expiries"] = {"ok": bool(exps.get("expiries")), "data": exps}
    except Exception as e:
        report["expiries"] = {"ok": False, "error": str(e)}

    # 3. Strikes check
    try:
        if report.get("expiries",{}).get("ok"):
            expiry = report["expiries"]["data"]["expiries"][0]
            stks = list_strikes("NIFTY", expiry, "CE")
            report["strikes"] = {"ok": bool(stks.get("strikes")), "data": stks}
        else:
            report["strikes"] = {"ok": False, "error": "no expiry"}
    except Exception as e:
        report["strikes"] = {"ok": False, "error": str(e)}

    # 4. Security lookup
    try:
        if report.get("strikes",{}).get("ok"):
            expiry = report["expiries"]["data"]["expiries"][0]
            strike = report["strikes"]["data"]["strikes"][0]
            sec = lookup_security_id("NIFTY", expiry, strike, "CE")
            report["security_lookup"] = {"ok": bool(sec), "data": sec}
        else:
            report["security_lookup"] = {"ok": False, "error": "no strike"}
    except Exception as e:
        report["security_lookup"] = {"ok": False, "error": str(e)}

    # 5. Webhook DRY simulation
    try:
        payload = {
            "secret": WEBHOOK_SECRET,
            "symbol": "NIFTY",
            "action": "BUY",
            "expiry": report.get("expiries",{}).get("data",{}).get("expiries",[None])[0],
            "strike": report.get("strikes",{}).get("data",{}).get("strikes",[None])[0],
            "option_type": "CE",
            "qty": 50,
            "price": "MARKET"
        }
        dry = {
            "ok": True, "mode": "DRY", "received": payload
        } if MODE != "LIVE" else {"note": "LIVE mode skip"}
        report["webhook_dry"] = {"ok": True, "data": dry}
    except Exception as e:
        report["webhook_dry"] = {"ok": False, "error": str(e)}

    return report
