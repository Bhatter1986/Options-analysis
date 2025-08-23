# main.py
from fastapi import FastAPI, Body, HTTPException
from pydantic import BaseModel, Field, validator
import os, requests

app = FastAPI(title="Options Analysis API", version="2.0")

# =========================
# ENV / CONFIG
# =========================
MODE = os.getenv("MODE", "DRY").upper()  # DRY | LIVE
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "my$ecret123")

# SANDBOX
SB_BASE   = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")
SB_TOKEN  = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN", "")
SB_CID    = os.getenv("DHAN_SANDBOX_CLIENT_ID", "")

# LIVE
LV_BASE   = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")
LV_TOKEN  = os.getenv("DHAN_LIVE_ACCESS_TOKEN", "")
LV_CID    = os.getenv("DHAN_LIVE_CLIENT_ID", "")

# Optional CSV (kept for future)
INSTR_CSV = os.getenv("INSTRUMENTS_URL", "")

def use_live() -> bool:
    return MODE == "LIVE"

def dhan_base() -> str:
    return LV_BASE if use_live() else SB_BASE

def dhan_headers() -> dict:
    token = LV_TOKEN if use_live() else SB_TOKEN
    cid   = LV_CID   if use_live() else SB_CID
    return {
        "Content-Type": "application/json",
        "access-token": token,
        "client-id": cid,
    }

# =========================
# BASIC
# =========================
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/broker_status")
def broker_status():
    base = dhan_base()
    h = dhan_headers()
    return {
        "mode": MODE,
        "env": "LIVE" if use_live() else "SANDBOX",
        "base_url": base,
        "has_creds": bool(h.get("access-token")) and bool(h.get("client-id")),
        "client_id_present": bool(h.get("client-id")),
        "token_present": bool(h.get("access-token")),
    }

# =========================
# DHAN v2: OPTION-CHAIN
# =========================
class ExpiryListReq(BaseModel):
    UnderlyingScrip: int = Field(13, description="NIFTY index security_id")
    UnderlyingSeg: str = Field("IDX_I", description="Exchange segment enum")

@app.post("/dhan/expirylist")
def dhan_expirylist(body: ExpiryListReq = Body(...)):
    url = f"{dhan_base()}/optionchain/expirylist"
    r = requests.post(url, headers=dhan_headers(), json=body.dict())
    try:
        return r.json()
    except Exception:
        raise HTTPException(status_code=r.status_code, detail=r.text)

class OptionChainReq(BaseModel):
    UnderlyingScrip: int = Field(..., description="Underlying security id")
    UnderlyingSeg: str = Field("IDX_I", description="Exchange segment enum")
    Expiry: str = Field(..., description="YYYY-MM-DD")

@app.post("/dhan/optionchain")
def dhan_optionchain(body: OptionChainReq = Body(...)):
    url = f"{dhan_base()}/optionchain"
    r = requests.post(url, headers=dhan_headers(), json=body.dict())
    try:
        return r.json()
    except Exception:
        raise HTTPException(status_code=r.status_code, detail=r.text)

# =========================
# DHAN v2: MARKET QUOTE
# =========================
class QuoteReq(BaseModel):
    NSE_FNO: list[int] | None = None
    NSE_EQ: list[int] | None = None
    BSE_EQ: list[int] | None = None

    @validator("*", pre=True)
    def _empty_to_none(cls, v):
        return v if v not in ([], None, "") else None

def _proxy_quote(path: str, body: QuoteReq):
    url = f"{dhan_base()}{path}"
    r = requests.post(url, headers=dhan_headers(), json=body.dict(exclude_none=True))
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

# =========================
# SECURITY LOOKUP (placeholder)
# =========================
class SecLookupReq(BaseModel):
    symbol: str
    expiry: str
    strike: float | int
    option_type: str   # "CALL"/"PUT" or "CE"/"PE"

@app.post("/security_lookup")
def security_lookup(body: SecLookupReq):
    # CSV resolver intentionally disabled for now.
    return {
        "security_id": None,
        "note": "CSV resolver disabled. Use Dhan instruments list to pick the correct security IDs."
    }

# =========================
# WEBHOOK
# =========================
class WebhookReq(BaseModel):
    secret: str
    symbol: str | None = None
    action: str = Field(..., description="BUY or SELL")
    expiry: str | None = None
    strike: float | int | None = None
    option_type: str | None = None  # CALL/PUT or CE/PE
    qty: int = 1
    price: str | float = "MARKET"
    security_id: int | None = None  # Prefer passing this (NSE_FNO id)

    @validator("action")
    def _action_ok(cls, v):
        v = v.upper()
        if v not in ("BUY", "SELL"):
            raise ValueError("action must be BUY or SELL")
        return v

@app.post("/webhook")
def webhook(body: WebhookReq):
    # auth
    if body.secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # DRY mode: just simulate + sanity output
    if MODE == "DRY":
        return {
            "ok": True,
            "mode": "DRY",
            "message": "Simulation only. No live order was placed.",
            "echo": body.dict(),
        }

    # LIVE: require security_id for now (CSV lookup disabled)
    if body.security_id is None:
        raise HTTPException(
            status_code=400,
            detail="security_id required in LIVE mode (CSV resolver disabled).",
        )

    # Example LIVE order call (pseudo, adjust to your Orders API when you enable)
    # url = f"{dhan_base()}/orders"   # put the correct orders endpoint when you enable live
    # payload = { ... map fields ... }
    # r = requests.post(url, headers=dhan_headers(), json=payload)
    # return r.json()

    return {
        "ok": False,
        "mode": "LIVE",
        "message": "Order placement wiring is disabled in this build. security_id received.",
        "security_id": body.security_id,
    }

# =========================
# SELFTEST (safe)
# =========================
@app.get("/selftest")
def selftest():
    results: dict[str, dict] = {}

    # 1) broker
    results["broker_status"] = {"ok": True, "data": broker_status()}

    # 2) expiries (Dhan v2)
    try:
        exp = dhan_expirylist(ExpiryListReq())
        ok = isinstance(exp, dict) and "data" in exp and isinstance(exp["data"], list)
        results["expiries"] = {
            "ok": ok,
            "data": {"count": len(exp.get("data", [])) if ok else 0},
        }
    except Exception as e:
        results["expiries"] = {"ok": False, "error": str(e)}

    # 3) strikes — CSV helper off
    results["strikes"] = {"ok": False, "error": "strikes helper disabled"}

    # 4) security_lookup — CSV off
    results["security_lookup"] = {"ok": False, "error": "CSV lookup disabled"}

    # 5) webhook DRY — not executed automatically (needs secret)
    results["webhook_dry"] = {"ok": False, "error": "not executed in selftest"}

    return results

# Run: uvicorn main:app --host 0.0.0.0 --port 8000
