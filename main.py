# main.py — Options Analysis API (FastAPI) + Dhan v2 CSV lookup
# Works best with:
# fastapi==0.103.2, starlette==0.27.0, pydantic==1.10.13, uvicorn==0.29.0, requests==2.32.3

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os, csv, io, time, requests
from typing import Optional, Dict, Any, List
from datetime import datetime

app = FastAPI(title="Options Analysis API", version="2.2")

# ── CORS ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ENV & CONSTANTS ────────────────────────────────────────────────
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
MODE = os.getenv("MODE", "DRY").upper()                 # DRY / LIVE

DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
DHAN_API_BASE = os.getenv("DHAN_API_BASE", "https://api.dhan.co/v2")  # sandbox: https://sandbox.dhan.co/v2

# Dhan instruments CSV (detailed preferred)
INSTR_CSV_COMPACT  = "https://images.dhan.co/api-data/api-scrip-master.csv"
INSTR_CSV_DETAILED = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
INSTR_CSV_URL = INSTR_CSV_DETAILED

# ── CSV helpers (schema-flex) ──────────────────────────────────────
UNDERLYING_CANDS = ("UNDERLYING_SYMBOL", "SEM_UNDERLYING_SYMBOL", "SM_UNDERLYING_SYMBOL", "UNDERLYING")
EXPIRY_CANDS     = ("SEM_EXPIRY_DATE", "EXPIRY_DATE", "EXPIRY", "SM_EXPIRY_DATE")
STRIKE_CANDS     = ("SEM_STRIKE_PRICE", "STRIKE", "STRIKE_PRICE", "SM_STRIKE_PRICE")
OTYPE_CANDS      = ("SEM_OPTION_TYPE", "OPTION_TYPE", "SM_OPTION_TYPE")
SECID_CANDS      = ("SECURITY_ID", "SEM_SECURITY_ID", "SM_SECURITY_ID")

CSV_TTL_SEC = 15 * 60
_CSV_CACHE = {"ts": 0.0, "rows": [], "header": []}

DATE_PATTS = ("%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y")

def _dhan_headers() -> Dict[str, str]:
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="Dhan credentials missing")
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "client-id": DHAN_CLIENT_ID,
        "access-token": DHAN_ACCESS_TOKEN,
    }

def broker_ready() -> bool:
    return bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN)

def _download_csv_text() -> str:
    r = requests.get(INSTR_CSV_URL, timeout=30)
    r.raise_for_status()
    return r.text

def _detect(cols: List[str], candidates: tuple) -> Optional[str]:
    for c in candidates:
        if c in cols:
            return c
    return None

def _norm_symbol(s: Optional[str]) -> str:
    return (s or "").upper().strip()

def _norm_otype(x: Optional[str]) -> str:
    x = _norm_symbol(x)
    if x in ("CE", "CALL"): return "CALL"
    if x in ("PE", "PUT"):  return "PUT"
    return x

def _norm_date(s: Optional[str]) -> str:
    s = (s or "").strip()
    for fmt in DATE_PATTS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return s

def _float_eq(a: Any, b: Any, eps: float = 1e-4) -> bool:
    try:
        return abs(float(a) - float(b)) < eps
    except Exception:
        return False

def _load_rows(force: bool = False):
    now = time.time()
    if (not force) and _CSV_CACHE["rows"] and now - _CSV_CACHE["ts"] < CSV_TTL_SEC:
        return _CSV_CACHE["rows"], _CSV_CACHE["header"]
    text = _download_csv_text()
    f = io.StringIO(text)
    rdr = csv.DictReader(f)
    rows = list(rdr)
    _CSV_CACHE.update(ts=now, rows=rows, header=rdr.fieldnames or [])
    return rows, _CSV_CACHE["header"]

def list_expiries_for_symbol(symbol: str) -> List[str]:
    rows, header = _load_rows()
    ucol = _detect(header, UNDERLYING_CANDS)
    ecol = _detect(header, EXPIRY_CANDS)
    if not (ucol and ecol):
        return []
    sym = _norm_symbol(symbol)
    exps = set()
    for r in rows:
        if _norm_symbol(r.get(ucol)) == sym:
            exps.add(_norm_date(r.get(ecol)))
    return sorted([e for e in exps if e])

def list_strikes_for(symbol: str, expiry: str, option_type: Optional[str] = None) -> List[float]:
    rows, header = _load_rows()
    ucol = _detect(header, UNDERLYING_CANDS)
    ecol = _detect(header, EXPIRY_CANDS)
    scol = _detect(header, STRIKE_CANDS)
    ocol = _detect(header, OTYPE_CANDS)
    if not (ucol and ecol and scol):
        return []
    sym = _norm_symbol(symbol)
    exp = _norm_date(expiry)
    ot = _norm_otype(option_type) if option_type else None
    strikes = set()
    for r in rows:
        if _norm_symbol(r.get(ucol)) != sym: continue
        if _norm_date(r.get(ecol)) != exp:   continue
        if ot and _norm_otype(r.get(ocol)) != ot: continue
        try:
            v = float(r.get(scol) or 0)
            if v > 0:
                strikes.add(v)
        except Exception:
            pass
    return sorted(strikes)

def lookup_security_id(underlying_symbol: str, expiry: str, strike: Any, option_type: str) -> Optional[str]:
    # fresh download for final lookup
    text = _download_csv_text()
    f = io.StringIO(text)
    rdr = csv.DictReader(f)
    header = rdr.fieldnames or []
    ucol = _detect(header, UNDERLYING_CANDS)
    ecol = _detect(header, EXPIRY_CANDS)
    scol = _detect(header, STRIKE_CANDS)
    ocol = _detect(header, OTYPE_CANDS)
    sec  = _detect(header, SECID_CANDS)
    if not (ucol and ecol and scol and ocol and sec):
        return None

    sym = _norm_symbol(underlying_symbol)
    exp = _norm_date(expiry)
    ot  = _norm_otype(option_type)
    for r in rdr:
        if _norm_symbol(r.get(ucol)) != sym: continue
        if _norm_date(r.get(ecol)) != exp:   continue
        if _norm_otype(r.get(ocol)) != ot:   continue
        if _float_eq(r.get(scol), strike):
            return r.get(sec)
    return None

# ── Dhan REST calls ───────────────────────────────────────────────
def place_dhan_order(
    security_id: str,
    side: str,                      # BUY / SELL
    qty: int,
    order_type: str = "MARKET",     # MARKET / LIMIT
    price: Optional[float] = None,
    product_type: str = "INTRADAY",
    exchange_segment: str = "NSE_FNO",
    validity: str = "DAY",
    tag: Optional[str] = None,
):
    url = f"{DHAN_API_BASE}/orders"
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

    r = requests.post(url, headers=_dhan_headers(), json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"text": r.text}
    return r.status_code, data

def dhan_quote_snapshot(body: dict):
    url = f"{DHAN_API_BASE}/marketfeed/quote"
    r = requests.post(url, headers=_dhan_headers(), json=body, timeout=20)
    r.raise_for_status()
    return r.json()

# ── Routes ────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/broker_status")
def broker_status():
    return {"mode": MODE, "client_ready": broker_ready()}

@app.get("/csv_debug")
def csv_debug():
    rows, header = _load_rows(force=True)
    return {"columns": header, "sample": rows[:2] if rows else [], "count": len(rows)}

@app.get("/list_expiries")
def list_expiries(symbol: str):
    return {"symbol": _norm_symbol(symbol), "expiries": list_expiries_for_symbol(symbol)}

@app.get("/list_strikes")
def list_strikes(symbol: str, expiry: str, option_type: Optional[str] = None):
    return {
        "symbol": _norm_symbol(symbol),
        "expiry": _norm_date(expiry),
        "option_type": _norm_otype(option_type) if option_type else None,
        "strikes": list_strikes_for(symbol, expiry, option_type),
    }

@app.get("/security_lookup")
def usage_hint():
    return {"use": "POST /security_lookup", "example": {"symbol":"NIFTY","expiry":"2025-08-28","strike":25100,"option_type":"CALL"}}

@app.post("/security_lookup")
def security_lookup(payload: Dict[str, Any]):
    sec_id = lookup_security_id(
        payload.get("symbol", ""),
        payload.get("expiry", ""),
        payload.get("strike", 0),
        payload.get("option_type", ""),
    )
    return {"security_id": sec_id}

@app.post("/dhan/quote")
def dhan_quote(body: Dict[str, Any]):
    # Body example: { "NSE_FNO": ["49081"] }
    try:
        return dhan_quote_snapshot(body)
    except requests.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.post("/webhook")
async def webhook(request: Request):
    """
    Body:
    {
      "secret": "my$ecret123",
      "symbol": "NIFTY",
      "action": "BUY",
      "expiry": "2025-08-28",
      "strike": 25100,
      "option_type": "CALL",    # or PUT
      "qty": 50,
      "price": "MARKET",        # or numeric for LIMIT
      "security_id": "optional"
    }
    """
    data = await request.json()

    if str(data.get("secret", "")) != WEBHOOK_SECRET:
        raise HTTPException(401, detail="Unauthorized")

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

    if not security_id:
        security_id = lookup_security_id(symbol, expiry, strike, option_type)
        if not security_id:
            raise HTTPException(400, detail="security_id not found")

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

    tag = "tv-" + datetime.utcnow().isoformat()
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
