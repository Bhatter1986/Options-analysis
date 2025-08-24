# main.py  — FastAPI + DhanHQ v2, single-file
import os
from typing import Optional, Any, Dict, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

try:
    from dhanhq import dhanhq as DhanSDK
except Exception as e:  # safety on first boot
    DhanSDK = None


app = FastAPI(title="Options-analysis", version="v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ---------- Helpers ----------

def _mode_env() -> Dict[str, Any]:
    """Pick LIVE / SANDBOX creds by MODE (LIVE|SANDBOX|DRY)."""
    mode = os.getenv("MODE", "LIVE").upper()
    if mode == "SANDBOX":
        return dict(
            mode=mode, env="SANDBOX",
            client_id=os.getenv("DHAN_SANDBOX_CLIENT_ID", ""),
            token=os.getenv("DHAN_SANDBOX_ACCESS_TOKEN", "")
        )
    else:  # default LIVE (also used for DRY)
        return dict(
            mode=mode if mode in ("LIVE", "DRY") else "LIVE",
            env="LIVE",
            client_id=os.getenv("DHAN_LIVE_CLIENT_ID", ""),
            token=os.getenv("DHAN_LIVE_ACCESS_TOKEN", "")
        )


def _get_dhan():
    """Return (meta, dhan_instance or None)."""
    meta = _mode_env()
    if meta["mode"] == "DRY":
        return meta, None
    if not DhanSDK:
        raise HTTPException(500, "dhanhq package not available.")
    if not meta["client_id"] or not meta["token"]:
        raise HTTPException(400, "Missing DHAN client_id or access_token.")
    return meta, DhanSDK(meta["client_id"], meta["token"])


def _ok(data: Any) -> Dict[str, Any]:
    return {"status": "success", "remarks": "", "data": data}


def _fail(e: Exception | str, data: Any = None) -> Dict[str, Any]:
    msg = str(e)
    return {"status": "failure", "remarks": msg, "data": data or {}}


def _collect_dates(obj: Any) -> List[str]:
    """Extract YYYY-MM-DD strings from any nested response shape."""
    out: List[str] = []
    def walk(x: Any):
        if isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
        elif isinstance(x, str) and len(x) == 10 and x[4] == "-" and x[7] == "-":
            out.append(x)
    walk(obj)
    # unique, keep order
    seen = set()
    uniq = []
    for d in out:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq

# ---------- Models ----------

class ExpiryListReq(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    under_security_id: int = Field(alias="UnderlyingScrip")
    under_exchange_segment: str = Field(alias="UnderlyingSeg")


class OptionChainReq(ExpiryListReq):
    expiry: Optional[str] = Field(default=None, alias="Expiry")


# ---------- Routes ----------

@app.get("/")
def root():
    return {"ok": True, "service": app.title, "version": app.version}

@app.get("/broker_status")
def broker_status():
    meta = _mode_env()
    return {
        "mode": meta["mode"],
        "env": meta["env"],
        "token_present": bool(meta["token"]),
        "client_id_present": bool(meta["client_id"]),
    }

@app.get("/orders")
def orders():
    meta, dhan = _get_dhan()
    if not dhan:
        # DRY response
        return _ok({"data": [], "status": "dry"})
    try:
        res = dhan.get_order_list()
        return _ok(res)
    except Exception as e:
        return _fail(e)

@app.get("/positions")
def positions():
    meta, dhan = _get_dhan()
    if not dhan:
        return _ok({"data": [], "status": "dry"})
    try:
        res = dhan.get_positions()
        return _ok(res)
    except Exception as e:
        return _fail(e)

# --- Expiry list (GET with query OR POST with body) ---

@app.get("/optionchain/expirylist")
def expiry_list_get(
    under_security_id: int = Query(..., alias="under_security_id"),
    under_exchange_segment: str = Query(..., alias="under_exchange_segment"),
):
    meta, dhan = _get_dhan()
    if not dhan:
        # few mock dates in DRY
        return _ok({"data": ["2025-08-28", "2025-09-23"]})
    try:
        res = dhan.expiry_list(
            under_security_id=under_security_id,
            under_exchange_segment=under_exchange_segment
        )
        return _ok(res)
    except Exception as e:
        return _fail(e)

@app.post("/optionchain/expirylist")
def expiry_list_post(req: ExpiryListReq):
    meta, dhan = _get_dhan()
    if not dhan:
        return _ok({"data": ["2025-08-28", "2025-09-23"]})
    try:
        res = dhan.expiry_list(
            under_security_id=req.under_security_id,
            under_exchange_segment=req.under_exchange_segment
        )
        return _ok(res)
    except Exception as e:
        return _fail(e)

# --- Option Chain ---

@app.post("/optionchain")
def option_chain(req: OptionChainReq):
    meta, dhan = _get_dhan()
    if not dhan:
        # DRY sample
        return _ok({"symbol": "NIFTY", "contracts": [], "status": "dry"})

    # Resolve expiry if missing: pick the nearest one from /expirylist
    expiry = req.expiry
    if not expiry:
        try:
            el = dhan.expiry_list(
                under_security_id=req.under_security_id,
                under_exchange_segment=req.under_exchange_segment
            )
            dates = _collect_dates(el)
            if not dates:
                raise HTTPException(400, "No valid expiries returned by broker.")
            expiry = sorted(dates)[0]
        except Exception as e:
            return _fail(f"Failed to resolve expiry automatically: {e}")

    try:
        res = dhan.option_chain(
            under_security_id=req.under_security_id,
            under_exchange_segment=req.under_exchange_segment,
            expiry=expiry
        )
        return _ok(res)
    except Exception as e:
        # Common broker error: invalid expiry
        return _fail(e, data={"hint": "Call /optionchain/expirylist to get valid dates and use one of them."})
