# main.py — Options Analysis API (FastAPI) + Dhan v2 + CSV helpers
from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os, requests, time, io, csv

app = FastAPI(title="Options Analysis API", version="2.3")

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
# ENV / CONFIG
# ─────────────────────────────────────────────────────────────────
MODE = os.getenv("MODE", "DRY").upper()        # DRY | LIVE (order simulate vs live)
ENV  = os.getenv("ENV", "SANDBOX").upper()     # SANDBOX | LIVE (which creds/base)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "my$ecret123")

# SANDBOX
SB_BASE = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")
SB_CID  = os.getenv("DHAN_SANDBOX_CLIENT_ID", "")
SB_TOK  = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN", "")

# LIVE
LV_BASE = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")
LV_CID  = os.getenv("DHAN_LIVE_CLIENT_ID", "")
LV_TOK  = os.getenv("DHAN_LIVE_ACCESS_TOKEN", "")

def use_live_env() -> bool:
    return ENV == "LIVE"

def dhan_base() -> str:
    return LV_BASE if use_live_env() else SB_BASE

def dhan_headers() -> Dict[str, str]:
    token = LV_TOK if use_live_env() else SB_TOK
    cid   = LV_CID if use_live_env() else SB_CID
    if not token or not cid:
        raise HTTPException(500, detail="Dhan credentials missing for selected ENV")
    return {
        "Content-Type": "application/json",
        "access-token": token,
        "client-id": cid,
    }

# Instruments CSV (Detailed)
INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
)

# ─────────────────────────────────────────────────────────────────
# HEALTH / STATUS
# ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/broker_status")
def broker_status():
    try:
        h = dhan_headers()
        has_creds = True
    except HTTPException:
        h = {}
        has_creds = False
    return {
        "mode": MODE,
        "env": ENV,
        "base_url": dhan_base(),
        "has_creds": has_creds,
        "client_id_present": bool(h.get("client-id")),
        "token_present": bool(h.get("access-token")),
        "instruments_url": INSTRUMENTS_URL,
    }

# ─────────────────────────────────────────────────────────────────
# DHAN v2 PROXIES (Option-Chain & Market Quote)
# ─────────────────────────────────────────────────────────────────
class ExpiryListReq(BaseModel):
    UnderlyingScrip: int = Field(13, description="NIFTY index security_id")
    UnderlyingSeg: str = Field("IDX_I", description="Exchange segment enum")

@app.post("/dhan/expirylist")
def dhan_expirylist(body: ExpiryListReq = Body(...)):
    url = f"{dhan_base()}/optionchain/expirylist"
    r = requests.post(url, headers=dhan_headers(), json=body.dict(), timeout=30)
    try:
        return r.json()
    except Exception:
        raise HTTPException(status_code=r.status_code, detail=r.text)

class OptionChainReq(BaseModel):
    UnderlyingScrip: int
    UnderlyingSeg: str = "IDX_I"
    Expiry: str

@app.post("/dhan/optionchain")
def dhan_optionchain(body: OptionChainReq = Body(...)):
    url = f"{dhan_base()}/optionchain"
    r = requests.post(url, headers=dhan_headers(), json=body.dict(), timeout=30)
    try:
        return r.json()
    except Exception:
        raise HTTPException(status_code=r.status_code, detail=r.text)

class QuoteReq(BaseModel):
    NSE_FNO: Optional[List[int]] = None
    NSE_EQ: Optional[List[int]] = None
    BSE_EQ: Optional[List[int]] = None

def _proxy_quote(path: str, body: QuoteReq):
    url = f"{dhan_base()}{path}"
    payload = {k: v for k, v in body.dict().items() if v}
    r = requests.post(url, headers=dhan_headers(), json=payload, timeout=30)
    try:
        return r.json()
    except Exception:
        raise HTTPException(status_code=r.status_code, detail=r.text)

@app.post("/dhan/ltp")
def dhan_ltp(body: QuoteReq = Body(...)):
    return _proxy_quote("/marketfeed/ltp", body)

@app.post("/dhan/ohlc")
def dhan_ohlc(body: QuoteReq = Body(...)):
    return _proxy_quote("/marketfeed/ohlc", body)

@app.post("/dhan/quote")
def dhan_quote(body: QuoteReq = Body(...)):
    return _proxy_quote("/marketfeed/quote", body)

# ─────────────────────────────────────────────────────────────────
# INSTRUMENTS CSV HELPERS (expiry/strike/security_id)
# ─────────────────────────────────────────────────────────────────
_csv_cache: Dict[str, Any] = {"ts": 0.0, "text": ""}

def _csv_text(force: bool=False) -> str:
    now = time.time()
    if not force and _csv_cache["text"] and now - _csv_cache["ts"] < 600:
        return _csv_cache["text"]
    r = requests.get(INSTRUMENTS_URL, timeout=45)
    r.raise_for_status()
    _csv_cache["ts"] = now
    _csv_cache["text"] = r.text
    return _csv_cache["text"]

def _reader(force: bool=False) -> csv.DictReader:
    return csv.DictReader(io.StringIO(_csv_text(force)))

def _norm(x: Optional[str]) -> str:
    return (x or "").strip()

def _otype(x: str) -> str:
    x = (x or "").strip().upper()
    if x in ("CALL","CE"): return "CE"
    if x in ("PUT","PE"):  return "PE"
    return x

def _secid_col(fields: Optional[List[str]]) -> Optional[str]:
    fields = fields or []
    for k in ("SECURITY_ID","SEM_SECURITY_ID","SM_SECURITY_ID"):
        if k in fields:
            return k
    return None

@app.post("/instruments/refresh")
def refresh_instruments():
    _ = _csv_text(force=True)
    return {"ok": True, "source": INSTRUMENTS_URL, "cached": True}

@app.get("/list_expiries")
def list_expiries(symbol: str):
    sym = _norm(symbol).upper()
    expiries = set()
    rdr = _reader()
    for row in rdr:
        if _norm(row.get("UNDERLYING_SYMBOL","")).upper() == sym:
            exp = _norm(row.get("SEM_EXPIRY_DATE",""))
            if exp:
                expiries.add(exp)
    return {"symbol": sym, "expiries": sorted(expiries)}

@app.get("/list_strikes")
def list_strikes(symbol: str, expiry: str, option_type: str = "CALL"):
    sym = _norm(symbol).upper()
    exp = _norm(expiry)
    ot  = _otype(option_type)
    strikes = set()
    rdr = _reader()
    for row in rdr:
        if (
            _norm(row.get("UNDERLYING_SYMBOL","")).upper() == sym and
            _norm(row.get("SEM_EXPIRY_DATE","")) == exp and
            _otype(row.get("SEM_OPTION_TYPE","")) == ot
        ):
            sp = _norm(row.get("SEM_STRIKE_PRICE",""))
            try:
                strikes.add(float(sp))
            except Exception:
                pass
    return {
        "symbol": sym, "expiry": exp,
        "option_type": "CALL" if ot == "CE" else "PUT",
        "strikes": sorted(strikes)
    }

class SecLookupReq(BaseModel):
    symbol: str
    expiry: str
    strike: float
    option_type: str  # CALL/PUT or CE/PE

@app.post("/security_lookup")
def security_lookup(body: SecLookupReq):
    sym = _norm(body.symbol).upper()
    exp = _norm(body.expiry)
    ot  = _otype(body.option_type)
    rdr = _reader()
    sec_col = _secid_col(rdr.fieldnames)
    for row in rdr:
        try:
            if (
                _norm(row.get("UNDERLYING_SYMBOL","")).upper() == sym and
                _norm(row.get("SEM_EXPIRY_DATE","")) == exp and
                _otype(row.get("SEM_OPTION_TYPE","")) == ot and
                float(_norm(row.get("SEM_STRIKE_PRICE","0")) or 0.0) == float(body.strike)
            ):
                sid = _norm(row.get(sec_col) if sec_col else "")
                return {"security_id": sid or None}
        except Exception:
            continue
    return {"security_id": None}

# ─────────────────────────────────────────────────────────────────
# WEBHOOK (TradingView / Manual)
# ─────────────────────────────────────────────────────────────────
class WebhookReq(BaseModel):
    secret: str
    action: str = Field(..., description="BUY or SELL")
    security_id: Optional[int] = None
    symbol: Optional[str] = None
    expiry: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None  # CALL/PUT or CE/PE
    qty: int = 1
    price: Optional[str] = "MARKET"    # or numeric string

@app.post("/webhook")
def webhook(body: WebhookReq):
    if body.secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    action = (body.action or "").upper()
    if action not in ("BUY","SELL"):
        raise HTTPException(422, detail="action must be BUY or SELL")

    # DRY -> simulate
    if MODE != "LIVE":
        return {
            "ok": True,
            "mode": "DRY",
            "message": "Simulation only. No live order placed.",
            "echo": body.dict(),
        }

    # LIVE -> require security_id (we are not placing real orders here)
    if body.security_id is None:
        raise HTTPException(400, detail="security_id required in LIVE mode")

    # Live order API wiring intentionally disabled for safety
    return {
        "ok": False,
        "mode": "LIVE",
        "message": "Order placement disabled in this build. security_id received.",
        "security_id": body.security_id,
    }

# ─────────────────────────────────────────────────────────────────
# SELFTEST (safe)
# ─────────────────────────────────────────────────────────────────
@app.get("/selftest")
def selftest():
    out: Dict[str, Any] = {}

    # broker
    out["broker_status"] = {"ok": True, "data": broker_status()}

    # expiries (CSV)
    try:
        exps = list_expiries("NIFTY")["expiries"]
        out["expiries"] = {"ok": bool(exps), "data": {"count": len(exps)}}
    except Exception as e:
        out["expiries"] = {"ok": False, "error": str(e)}

    # strikes (CSV) — only if expiry exists
    try:
        if out.get("expiries", {}).get("data", {}).get("count", 0) > 0:
            any_exp = list_expiries("NIFTY")["expiries"][0]
            stks = list_strikes("NIFTY", any_exp, "CALL")["strikes"]
            out["strikes"] = {"ok": bool(stks), "data": {"count": len(stks)}}
        else:
            out["strikes"] = {"ok": False, "error": "no expiry"}
    except Exception as e:
        out["strikes"] = {"ok": False, "error": str(e)}

    # security_lookup (CSV) — best effort (uses mid strike if available)
    try:
        if out.get("strikes", {}).get("data", {}).get("count", 0) > 0:
            exps2 = list_expiries("NIFTY")["expiries"]
            exp0 = exps2[0]
            stks2 = list_strikes("NIFTY", exp0, "CALL")["strikes"]
            mid = stks2[len(stks2)//2]
            sec = security_lookup(SecLookupReq(symbol="NIFTY", expiry=exp0, strike=float(mid), option_type="CALL"))
            out["security_lookup"] = {"ok": bool(sec.get("security_id")), "data": sec}
        else:
            out["security_lookup"] = {"ok": False, "error": "no strike"}
    except Exception as e:
        out["security_lookup"] = {"ok": False, "error": str(e)}

    # webhook dry — not run automatically (needs secret)
    out["webhook_dry"] = {"ok": False, "error": "not executed in selftest"}

    return out

# Run with: uvicorn main:app --host 0.0.0.0 --port 8000
