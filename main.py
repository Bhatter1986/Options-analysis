# main.py
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
import os

from dhanhq import dhanhq as Dhan

app = FastAPI(title="Options Analysis API", version="2.0")

# -------- Helpers --------
def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    if v is not None and isinstance(v, str):
        v = v.strip()
    return v

def get_mode() -> str:
    # DRY = mock safe mode
    return (get_env("MODE", "LIVE") or "LIVE").upper()

def get_env_tag() -> str:
    # LIVE vs SANDBOX detection (optional)
    base = (get_env("DHAN_BASE_URL") or "").lower()
    if "sandbox" in base:
        return "SANDBOX"
    return "LIVE"

def get_dhan_client() -> Dhan:
    client_id = get_env("DHAN_CLIENT_ID")
    access_token = get_env("DHAN_ACCESS_TOKEN")

    if not client_id or not access_token:
        raise HTTPException(
            status_code=400,
            detail="Missing DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN env vars."
        )
    return Dhan(client_id, access_token)

def ok(payload: Any) -> Dict[str, Any]:
    return {"status": "success", "remarks": "", "data": payload}

def fail(message: str, code: Optional[str] = None, etype: Optional[str] = None, extra: Any = None):
    return {
        "status": "failure",
        "remarks": {"error_code": code, "error_type": etype, "error_message": message},
        "data": extra,
    }

# -------- Schemas --------
class OptionChainReq(BaseModel):
    under_security_id: int = Field(..., description="e.g., 13 for NIFTY")
    under_exchange_segment: str = Field(..., description='e.g., "IDX_I" for Index derivatives')
    expiry: Optional[str] = Field(None, description='YYYY-MM-DD (must be valid as per /expiry_list)')

# -------- Endpoints --------
@app.get("/broker_status")
def broker_status():
    mode = get_mode()
    token_present = bool(get_env("DHAN_ACCESS_TOKEN"))
    client_present = bool(get_env("DHAN_CLIENT_ID"))
    return {
        "mode": mode,
        "env": get_env_tag(),
        "token_present": token_present,
        "client_id_present": client_present,
    }

@app.get("/orders")
def orders():
    if get_mode() == "DRY":
        # Dry mode: return empty list to keep it safe
        return ok([])
    try:
        dhan = get_dhan_client()
        data = dhan.get_order_list()  # returns list/dict as per SDK
        return ok(data)
    except Exception as e:
        # return SDK/raw error in a friendly format
        raise HTTPException(status_code=502, detail=fail(str(e)))

@app.get("/positions")
def positions():
    if get_mode() == "DRY":
        return ok([])
    try:
        dhan = get_dhan_client()
        data = dhan.get_positions()
        return ok(data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=fail(str(e)))

@app.get("/expiry_list")
def expiry_list(
    under_security_id: int = Query(..., description="e.g., 13 for NIFTY"),
    under_exchange_segment: str = Query(..., description='e.g., "IDX_I"'),
):
    """
    Valid expiries nikaalne ke liye. Example:
    GET /expiry_list?under_security_id=13&under_exchange_segment=IDX_I
    """
    if get_mode() == "DRY":
        # sample mock
        return ok(["2025-08-28", "2025-09-04", "2025-09-25"])
    try:
        dhan = get_dhan_client()
        exps = dhan.expiry_list(
            under_security_id=under_security_id,
            under_exchange_segment=under_exchange_segment,
        )
        return ok(exps)
    except Exception as e:
        raise HTTPException(status_code=502, detail=fail(str(e)))

@app.post("/option_chain")
def option_chain(body: OptionChainReq):
    """
    Body example:
    {
      "under_security_id": 13,
      "under_exchange_segment": "IDX_I",
      "expiry": "2025-08-28"
    }
    """
    if get_mode() == "DRY":
        # minimal mock shape
        return ok({"records": {"data": []}, "status": "mock"})
    try:
        dhan = get_dhan_client()

        # If expiry missing, attempt without expiry (SDK may allow),
        # but Dhan usually needs a valid expiry; better to fail clearly.
        if not body.expiry:
            raise HTTPException(
                status_code=400,
                detail=fail("Missing expiry. Pehle /expiry_list se valid date lo.")
            )

        oc = dhan.option_chain(
            under_security_id=body.under_security_id,
            under_exchange_segment=body.under_exchange_segment,
            expiry=body.expiry,
        )
        # Dhan invalid expiry par aisa error deta hai:
        # {"data":{"811":"Invalid Expiry Date"},"status":"failed"}
        if isinstance(oc, dict) and oc.get("status") == "failed":
            raise HTTPException(status_code=400, detail=fail("Invalid Expiry Date", extra=oc))

        return ok(oc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=fail(str(e)))
