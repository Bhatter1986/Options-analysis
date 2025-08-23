import os, io, csv, json, math
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Body, HTTPException, Header
from pydantic import BaseModel, Field
import httpx

app = FastAPI(title="Options Analysis Helper")

# -----------------------------------------------------------------------------
# ENV & CONFIG
# -----------------------------------------------------------------------------
MODE = (os.getenv("MODE") or "DRY").upper().strip()

# SANDBOX
DHAN_SANDBOX_BASE_URL = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")
DHAN_SANDBOX_ACCESS_TOKEN = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN", "")
DHAN_SANDBOX_CLIENT_ID = os.getenv("DHAN_SANDBOX_CLIENT_ID", "")

# LIVE
DHAN_LIVE_BASE_URL = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")
DHAN_LIVE_ACCESS_TOKEN = os.getenv("DHAN_LIVE_ACCESS_TOKEN", "")
DHAN_LIVE_CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID", "")

# Choose env (LIVE only when user explicitly sets MODE=LIVE)
DHAN_BASE_URL = DHAN_LIVE_BASE_URL if MODE == "LIVE" else DHAN_SANDBOX_BASE_URL
DHAN_ACCESS_TOKEN = DHAN_LIVE_ACCESS_TOKEN if MODE == "LIVE" else DHAN_SANDBOX_ACCESS_TOKEN
DHAN_CLIENT_ID = DHAN_LIVE_CLIENT_ID if MODE == "LIVE" else DHAN_SANDBOX_CLIENT_ID

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "my$ecret123")

# CSV (detailed preferred)
INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv",
)

CSV_TIMEOUT = 20.0

# -----------------------------------------------------------------------------
# MODELS
# -----------------------------------------------------------------------------
class SecLookupReq(BaseModel):
    symbol: str = Field(..., example="NIFTY")
    expiry: str = Field(..., example="2025-08-28")
    strike: float = Field(..., example=25100)
    option_type: str = Field(..., example="CALL")  # CALL/PUT or CE/PE

class WebhookReq(BaseModel):
    secret: str
    symbol: str
    action: str                       # BUY/SELL
    expiry: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None # CALL/PUT/CE/PE
    qty: Optional[int] = 50
    price: Optional[str] = "MARKET"
    security_id: Optional[str] = None # if provided, CSV lookup skip

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def _norm(x: Any) -> str:
    return (str(x).strip()) if x is not None else ""

def _otype(val: str) -> str:
    v = _norm(val).upper()
    if v in ("CE", "CALL", "C"): return "CALL"
    if v in ("PE", "PUT", "P"): return "PUT"
    return v

def _float_eq(a: Any, b: Any) -> bool:
    try:
        return math.isclose(float(a), float(b), rel_tol=0, abs_tol=0.001)
    except Exception:
        return False

CSV_COLS = {
    "underlying": ("UNDERLYING_SYMBOL", "SEM_UNDERLYING_SYMBOL", "SYMBOL"),
    "expiry":     ("EXPIRY_DATE", "SEM_EXPIRY_DATE"),
    "otype":      ("OPTION_TYPE", "SEM_OPTION_TYPE"),
    "strike":     ("STRIKE_PRICE", "SEM_STRIKE_PRICE"),
    "secid":      ("SECURITY_ID", "SEM_SECURITY_ID", "SECURITYID"),
}

def _pick(row: dict, keys: tuple) -> str:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return _norm(row[k])
    return ""

def _reader():
    """
    Stream CSV from INSTRUMENTS_URL; if detailed fails, fall back to simple CSV.
    """
    candidate_urls = [
        INSTRUMENTS_URL,
        "https://images.dhan.co/api-data/api-scrip-master-detailed.csv",
        "https://images.dhan.co/api-data/api-scrip-master.csv",
    ]
    tried = set()
    last_err = None
    for url in candidate_urls:
        if url in tried: continue
        tried.add(url)
        try:
            with httpx.Client(timeout=CSV_TIMEOUT) as cli:
                r = cli.get(url)
                r.raise_for_status()
                content = r.text
                # Handle potential BOM/newlines
                f = io.StringIO(content)
                rdr = csv.DictReader(f)
                # Force evaluation of header by accessing fieldnames
                _ = rdr.fieldnames
                return rdr
        except Exception as e:
            last_err = e
            continue
    raise HTTPException(status_code=502, detail=f"Failed to load instruments CSV: {last_err}")

def _secid_col(fieldnames: List[str]) -> str:
    fset = {c.upper(): c for c in (fieldnames or [])}
    for k in CSV_COLS["secid"]:
        if k.upper() in fset:
            return fset[k.upper()]
    # default guess
    return (fieldnames or ["SECURITY_ID"])[0]

def _dhan_headers() -> Dict[str, str]:
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

# -----------------------------------------------------------------------------
# HEALTH / STATUS
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "env": "LIVE" if MODE == "LIVE" else "SANDBOX",
        "base_url": DHAN_BASE_URL,
        "has_creds": bool(DHAN_ACCESS_TOKEN),
        "client_id_present": bool(DHAN_CLIENT_ID),
        "token_present": bool(DHAN_ACCESS_TOKEN),
        "instruments_url": INSTRUMENTS_URL,
    }

# -----------------------------------------------------------------------------
# CSV HELPERS
# -----------------------------------------------------------------------------
@app.get("/list_expiries")
def list_expiries(symbol: str):
    sym = _norm(symbol).upper()
    expiries = set()
    rdr = _reader()
    for row in rdr:
        if _norm(_pick(row, CSV_COLS["underlying"])).upper() == sym:
            exp = _pick(row, CSV_COLS["expiry"])
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
            _norm(_pick(row, CSV_COLS["underlying"])).upper() == sym and
            _norm(_pick(row, CSV_COLS["expiry"])) == exp and
            _otype(_pick(row, CSV_COLS["otype"])) == ot
        ):
            sp = _pick(row, CSV_COLS["strike"])
            try:
                strikes.add(float(sp))
            except Exception:
                pass
    return {"symbol": sym, "expiry": exp, "option_type": ot, "strikes": sorted(strikes)}

@app.post("/security_lookup")
def security_lookup(req: SecLookupReq):
    sym = _norm(req.symbol).upper()
    exp = _norm(req.expiry)
    ot  = _otype(req.option_type)
    rdr = _reader()
    sec_col = _secid_col(rdr.fieldnames or [])
    for row in rdr:
        try:
            if (
                _norm(_pick(row, CSV_COLS["underlying"])).upper() == sym and
                _norm(_pick(row, CSV_COLS["expiry"])) == exp and
                _otype(_pick(row, CSV_COLS["otype"])) == ot and
                _float_eq(_pick(row, CSV_COLS["strike"]), req.strike)
            ):
                sid = _norm(row.get(sec_col, ""))
                return {"security_id": sid or None}
        except Exception:
            continue
    return {"security_id": None}

# -----------------------------------------------------------------------------
# DHAN PROXY (Data APIs)
# -----------------------------------------------------------------------------
@app.post("/dhan/quote")
def dhan_quote(payload: Dict[str, List[int]] = Body(...)):
    """
    Proxy to Dhan /marketfeed/quote
    Body example: { "NSE_FNO": [71988] }
    """
    url = f"{DHAN_BASE_URL}/marketfeed/quote"
    headers = _dhan_headers()
    try:
        with httpx.Client(timeout=20.0) as cli:
            r = cli.post(url, headers=headers, content=json.dumps(payload))
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"dhan quote error: {e}")

@app.post("/dhan/optionchain")
def dhan_optionchain(body: Dict[str, Any] = Body(...)):
    """
    Proxy to Dhan /optionchain
    Body example:
    { "UnderlyingScrip": 13, "UnderlyingSeg":"IDX_I", "Expiry":"2025-08-28" }
    """
    url = f"{DHAN_BASE_URL}/optionchain"
    headers = _dhan_headers()
    try:
        with httpx.Client(timeout=20.0) as cli:
            r = cli.post(url, headers=headers, content=json.dumps(body))
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"dhan optionchain error: {e}")

@app.post("/dhan/expirylist")
def dhan_expirylist(body: Dict[str, Any] = Body(...)):
    """
    Proxy to Dhan /optionchain/expirylist
    Body example:
    { "UnderlyingScrip": 13, "UnderlyingSeg":"IDX_I" }
    """
    url = f"{DHAN_BASE_URL}/optionchain/expirylist"
    headers = _dhan_headers()
    try:
        with httpx.Client(timeout=20.0) as cli:
            r = cli.post(url, headers=headers, content=json.dumps(body))
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"dhan expirylist error: {e}")

# -----------------------------------------------------------------------------
# WEBHOOK (DRY by default)
# -----------------------------------------------------------------------------
@app.post("/webhook")
def webhook(req: WebhookReq):
    # auth
    if _norm(req.secret) != _norm(WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")

    # DRY mode -> just echo + light validation
    if MODE != "LIVE":
        return {
            "ok": True,
            "mode": "DRY",
            "received": req.dict(),
            "note": "Dry-run only. No live order has been placed.",
        }

    # LIVE mode – here you would place order to broker if needed.
    # Keeping out of scope intentionally for safety.
    return {
        "ok": False,
        "mode": "LIVE",
        "note": "Live order placement is disabled in this sample.",
    }

# -----------------------------------------------------------------------------
# SELFTEST – runs a light diagnostic (no live orders)
# -----------------------------------------------------------------------------
@app.get("/selftest")
def selftest():
    report: Dict[str, Any] = {}

    # A) Broker status
    try:
        bs = broker_status()
        report["broker_status"] = {"ok": True, "data": bs}
    except Exception as e:
        report["broker_status"] = {"ok": False, "error": str(e)}

    # B) CSV Expiries
    try:
        ex = list_expiries("NIFTY")
        ok = bool(ex.get("expiries"))
        report["expiries"] = {
            "ok": ok,
            "data": {"count": len(ex.get("expiries", []))}
        }
    except Exception as e:
        report["expiries"] = {"ok": False, "error": str(e)}

    # C) Strikes (use first expiry if present)
    try:
        exps = list_expiries("NIFTY").get("expiries", [])
        if not exps:
            raise ValueError("no expiry")
        st = list_strikes("NIFTY", exps[0], "CALL")
        ok = bool(st.get("strikes"))
        report["strikes"] = {"ok": ok, "data": {"count": len(st.get("strikes", []))}}
    except Exception as e:
        report["strikes"] = {"ok": False, "error": str(e)}

    # D) security_lookup (use first expiry/strike)
    try:
        exps = list_expiries("NIFTY").get("expiries", [])
        if not exps:
            raise ValueError("no expiry")
        st = list_strikes("NIFTY", exps[0], "CALL")
        strikes = st.get("strikes", [])
        if not strikes:
            raise ValueError("no strike")
        sl = security_lookup(SecLookupReq(symbol="NIFTY", expiry=exps[0], strike=strikes[0], option_type="CALL"))
        ok = bool(sl.get("security_id"))
        report["security_lookup"] = {"ok": ok, "data": sl if ok else None, "error": None if ok else "no id"}
    except Exception as e:
        report["security_lookup"] = {"ok": False, "error": str(e)}

    # E) webhook DRY not executed (just note)
    report["webhook_dry"] = {"ok": False, "error": "not executed in selftest"}

    return report
