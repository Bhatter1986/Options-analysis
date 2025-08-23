# main.py
import os
import io
import csv
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from dateutil import parser as dtparser

import httpx
from fastapi import FastAPI, Query, Body
from pydantic import BaseModel, Field

app = FastAPI(title="Options Analysis API", version="2.0")

# =========================
# Environment / Config
# =========================
MODE = os.getenv("MODE", "DRY").upper()                 # DRY / LIVE
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev$secret")

# --- SANDBOX (default) ---
DHAN_SANDBOX_BASE_URL   = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")
DHAN_SANDBOX_CLIENT_ID  = os.getenv("DHAN_SANDBOX_CLIENT_ID", "").strip()
DHAN_SANDBOX_ACCESS_TOK = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN", "").strip()

# --- LIVE ---
DHAN_LIVE_BASE_URL   = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")
DHAN_LIVE_CLIENT_ID  = os.getenv("DHAN_LIVE_CLIENT_ID", "").strip()
DHAN_LIVE_ACCESS_TOK = os.getenv("DHAN_LIVE_ACCESS_TOKEN", "").strip()

# --- CSV (instruments) ---
INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
).strip()

# Which env to use?
if MODE == "LIVE":
    DHAN_BASE_URL = DHAN_LIVE_BASE_URL
    DHAN_CLIENT_ID = DHAN_LIVE_CLIENT_ID
    DHAN_ACCESS_TOKEN = DHAN_LIVE_ACCESS_TOK
else:
    DHAN_BASE_URL = DHAN_SANDBOX_BASE_URL
    DHAN_CLIENT_ID = DHAN_SANDBOX_CLIENT_ID
    DHAN_ACCESS_TOKEN = DHAN_SANDBOX_ACCESS_TOK

# Minimal mapping (extend as you need)
# NIFTY == 13 (IDX_I), BANKNIFTY == 25 (IDX_I)  — Adjust if needed.
UNDERLYING_MAP = {
    "NIFTY":      {"UnderlyingScrip": 13, "UnderlyingSeg": "IDX_I"},
    "BANKNIFTY":  {"UnderlyingScrip": 25, "UnderlyingSeg": "IDX_I"},
}

# =========================
# Models
# =========================
class SecurityLookupReq(BaseModel):
    symbol: str = Field(..., description="Underlying, e.g., NIFTY")
    expiry: str = Field(..., description="YYYY-MM-DD")
    strike: float = Field(..., description="Strike price (e.g., 25100)")
    option_type: str = Field(..., description="CALL/PUT or CE/PE")

class WebhookOrder(BaseModel):
    secret: str
    symbol: str
    action: str                   # BUY / SELL
    expiry: str
    strike: float
    option_type: str              # CALL/PUT/CE/PE
    qty: int
    price: str = "MARKET"         # MARKET/LIMIT
    security_id: Optional[int] = None

# =========================
# Helpers
# =========================
def norm_symbol(s: str) -> str:
    return s.strip().upper()

def norm_opt_type(s: str) -> str:
    s = s.strip().upper()
    if s in ("CALL", "CE"): return "CE"
    if s in ("PUT", "PE"):  return "PE"
    return s

def norm_expiry(e: str) -> str:
    # accept many formats; return YYYY-MM-DD
    try:
        d = dtparser.parse(e, dayfirst=False)
        return d.strftime("%Y-%m-%d")
    except Exception:
        return e  # best-effort

def dhan_headers() -> Dict[str, str]:
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

async def dhan_post(path: str, payload: Dict[str, Any]) -> httpx.Response:
    url = f"{DHAN_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, headers=dhan_headers(), json=payload)
    return resp

async def fetch_optionchain_expiries(symbol: str) -> List[str]:
    sym = norm_symbol(symbol)
    if sym not in UNDERLYING_MAP:
        return []
    payload = {
        "UnderlyingScrip": UNDERLYING_MAP[sym]["UnderlyingScrip"],
        "UnderlyingSeg":   UNDERLYING_MAP[sym]["UnderlyingSeg"],
    }
    resp = await dhan_post("/optionchain/expirylist", payload)
    if resp.status_code != 200:
        return []
    data = resp.json()
    # Expect: {"data": ["YYYY-MM-DD", ...], "status":"success"}
    return [norm_expiry(x) for x in data.get("data", [])]

async def fetch_optionchain(symbol: str, expiry: str) -> Dict[str, Any]:
    sym = norm_symbol(symbol)
    if sym not in UNDERLYING_MAP:
        return {}
    payload = {
        "UnderlyingScrip": UNDERLYING_MAP[sym]["UnderlyingScrip"],
        "UnderlyingSeg":   UNDERLYING_MAP[sym]["UnderlyingSeg"],
        "Expiry":          norm_expiry(expiry),
    }
    resp = await dhan_post("/optionchain", payload)
    if resp.status_code != 200:
        return {}
    return resp.json()

def parse_csv_guess(rows: List[Dict[str, str]], symbol: str, expiry: str, strike: float, opt: str) -> Optional[int]:
    """
    Robust CSV matcher for Dhan 'api-scrip-master(-detailed).csv'
    Tries multiple header names & date formats.
    """
    sym = norm_symbol(symbol)
    exp_norm = norm_expiry(expiry)
    opt = norm_opt_type(opt)
    # Possible header aliases:
    HID = [
        "SEM_SECURITY_ID", "SECURITY_ID", "SecurityID", "security_id"
    ]
    HEXP = [
        "SEM_EXPIRY_DATE", "EXPIRY_DATE", "ExpiryDate", "expiry"
    ]
    HOPT = [
        "SEM_OPTION_TYPE", "OPTION_TYPE", "OptType"
    ]
    HSTR = [
        "SEM_STRIKE_PRICE", "STRIKE_PRICE", "StrikePrice", "strike"
    ]
    HNAME = [
        "SEM_INSTRUMENT_NAME", "INSTRUMENT_NAME", "InstrumentName"
    ]
    HSEG = [
        "SEM_EXM_EXCH_ID", "EXM_EXCH_ID", "ExchangeSegment"
    ]
    HTRSYM = [
        "SEM_TRADING_SYMBOL", "TRADING_SYMBOL", "TradingSymbol"
    ]

    def get(row: Dict[str, str], keys: List[str]) -> Optional[str]:
        for k in keys:
            if k in row and row[k] != "":
                return row[k]
        # case-insensitive fallback
        lower = {k.lower(): v for k, v in row.items()}
        for k in keys:
            if k.lower() in lower and lower[k.lower()] != "":
                return lower[k.lower()]
        return None

    def match_date(cell: Optional[str]) -> bool:
        if not cell:
            return False
        # normalize many styles
        try:
            d = dtparser.parse(cell)
            return d.strftime("%Y-%m-%d") == exp_norm
        except Exception:
            return False

    for row in rows:
        seg  = (get(row, HSEG) or "").upper()
        if seg and seg != "NSE_FNO":
            continue  # we only want derivatives
        name = (get(row, HNAME) or "").upper()
        tsym = (get(row, HTRSYM) or "").upper()

        # underlying rough check
        if sym not in name and sym not in tsym:
            continue

        # option type
        row_opt = (get(row, HOPT) or "").upper()
        if row_opt in ("CE", "CALL") and opt == "CE":
            pass
        elif row_opt in ("PE", "PUT") and opt == "PE":
            pass
        else:
            continue

        # expiry
        if not match_date(get(row, HEXP)):
            continue

        # strike
        rstr = get(row, HSTR)
        try:
            rstrike = float(rstr)
        except Exception:
            continue
        if abs(rstrike - float(strike)) > 1e-6:
            continue

        sid = get(row, HID)
        if sid:
            try:
                return int(sid)
            except Exception:
                return None
    return None

async def download_csv_rows(url: str) -> List[Dict[str, str]]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url)
        r.raise_for_status()
    buf = io.StringIO(r.text)
    reader = csv.DictReader(buf)
    return list(reader)

# =========================
# Endpoints
# =========================
@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/broker_status")
async def broker_status():
    return {
        "mode": MODE,
        "env": "LIVE" if MODE == "LIVE" else "SANDBOX",
        "base_url": DHAN_BASE_URL,
        "has_creds": bool(DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID),
        "client_id_present": bool(DHAN_CLIENT_ID),
        "token_present": bool(DHAN_ACCESS_TOKEN),
        "instruments_url": INSTRUMENTS_URL,
    }

@app.get("/list_expiries")
async def list_expiries(symbol: str = Query(..., description="e.g., NIFTY")):
    exps = await fetch_optionchain_expiries(symbol)
    return {"symbol": norm_symbol(symbol), "expiries": exps}

@app.get("/list_strikes")
async def list_strikes(
    symbol: str = Query(...),
    expiry: str = Query(..., description="YYYY-MM-DD"),
    option_type: str = Query("CALL", description="CALL/PUT (optional, only used to filter)")
):
    """
    Strikes are derived from Option-Chain 'oc' keys for given expiry.
    """
    data = await fetch_optionchain(symbol, expiry)
    oc = (data.get("data") or {}).get("oc") or {}
    strikes = []
    want = norm_opt_type(option_type)
    for k, v in oc.items():
        try:
            strike = float(k)
        except Exception:
            continue
        if want == "CE":
            if "ce" in v and v["ce"]:
                strikes.append(strike)
        elif want == "PE":
            if "pe" in v and v["pe"]:
                strikes.append(strike)
        else:
            strikes.append(strike)
    strikes = sorted(set(strikes))
    return {"symbol": norm_symbol(symbol), "expiry": norm_expiry(expiry), "option_type": "CALL" if want=="CE" else "PUT", "strikes": strikes}

@app.post("/security_lookup")
async def security_lookup(req: SecurityLookupReq):
    """
    Lookup Security ID from Dhan CSV master.
    """
    rows = await download_csv_rows(INSTRUMENTS_URL)
    sid = parse_csv_guess(rows, req.symbol, req.expiry, req.strike, req.option_type)
    return {"security_id": sid}

@app.post("/dhan/quote")
async def dhan_quote(body: Dict[str, List[int]] = Body(..., example={"NSE_FNO": [71988]})):
    """
    Market Quote snapshot — pass dict with exchange segment keys.
    """
    resp = await dhan_post("/marketfeed/quote", body)
    try:
        data = resp.json()
    except Exception:
        data = {"status_code": resp.status_code, "text": resp.text}
    return data

@app.post("/webhook")
async def webhook(order: WebhookOrder):
    if order.secret != WEBHOOK_SECRET:
        return {"detail": "Unauthorized"}
    # DRY mode: simulate only
    mode = "LIVE" if MODE == "LIVE" else "DRY"
    return {
        "ok": True,
        "mode": mode,
        "received": order.dict(),
        "note": "DRY mode - no live order placed" if mode == "DRY" else "LIVE not implemented here",
    }

@app.get("/selftest")
async def selftest():
    report: Dict[str, Any] = {}

    # 1) Broker status
    bs = await broker_status()
    report["broker_status"] = {"ok": bool(bs["has_creds"]), "data": bs}

    # 2) Expiry check (NIFTY)
    try:
        exps = await fetch_optionchain_expiries("NIFTY")
        report["expiries"] = {"ok": len(exps) > 0, "data": {"count": len(exps)} if exps is not None else {"count": 0}, "error": None if exps else "no expiry"}
    except Exception as e:
        report["expiries"] = {"ok": False, "data": {"count": 0}, "error": str(e)}

    # 3) Strikes check — only if expiry exists (take first)
    try:
        if report["expiries"]["ok"]:
            expiry = report["expiries"]["data"].get("first") or None
            if not expiry:
                expiry = (await list_expiries("NIFTY"))["expiries"][0]
            ls = await list_strikes("NIFTY", expiry, "CALL")
            ok = len(ls["strikes"]) > 0
            report["strikes"] = {"ok": ok, "data": {"count": len(ls["strikes"]), "sample": ls["strikes"][:10]}}
        else:
            report["strikes"] = {"ok": False, "error": "no expiry"}
    except Exception as e:
        report["strikes"] = {"ok": False, "error": str(e)}

    # 4) Security lookup — only if we have strikes
    try:
        if report.get("strikes", {}).get("ok"):
            expiry = (await list_expiries("NIFTY"))["expiries"][0]
            strike = report["strikes"]["data"]["sample"][0]
            sid = await security_lookup(SecurityLookupReq(symbol="NIFTY", expiry=expiry, strike=strike, option_type="CALL"))
            report["security_lookup"] = {"ok": bool(sid.get("security_id")), "error": None if sid.get("security_id") else "no match"}
        else:
            report["security_lookup"] = {"ok": False, "error": "no strike"}
    except Exception as e:
        report["security_lookup"] = {"ok": False, "error": str(e)}

    # 5) Webhook DRY — we don’t execute in selftest to avoid side-effects
    report["webhook_dry"] = {"ok": False, "error": "not executed in selftest"}

    return report


# Render/Procfile entrypoint would typically be:
# uvicorn main:app --host 0.0.0.0 --port $PORT
