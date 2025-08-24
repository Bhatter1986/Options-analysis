from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from dhanhq import dhanhq
import os

app = FastAPI(title="DhanHQ Demo API")

# ----- Env & client -----
CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID", "")
ACCESS_TOKEN = os.getenv("DHAN_LIVE_ACCESS_TOKEN", "")
MODE = os.getenv("MODE", "LIVE")  # LIVE/DRY

dhan = None
if CLIENT_ID and ACCESS_TOKEN:
    try:
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
    except Exception as e:
        # SDK init errors (rare)
        print("Dhan init error:", e)

# ----- Helpers -----
def ok(data):
    return {"status": "success", "remarks": "", "data": data}

def fail(msg):
    return {"status": "failure", "remarks": {"error_message": str(msg)}, "data": {}}

# ----- Health / status -----
@app.get("/")
def root():
    return {"hello": "world"}

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "token_present": bool(ACCESS_TOKEN),
        "client_id_present": bool(CLIENT_ID),
    }

def ensure_client():
    if not (CLIENT_ID and ACCESS_TOKEN):
        raise HTTPException(
            status_code=400,
            detail="Missing DHAN_LIVE_CLIENT_ID or DHAN_LIVE_ACCESS_TOKEN env vars.",
        )
    if dhan is None:
        raise HTTPException(status_code=500, detail="Dhan client not initialized.")

# ----- Orders -----
@app.get("/orders")
def orders():
    ensure_client()
    try:
        resp = dhan.get_order_list()
        return ok(resp)
    except Exception as e:
        return JSONResponse(fail(e), status_code=500)

# ----- Positions -----
@app.get("/positions")
def positions():
    ensure_client()
    try:
        resp = dhan.get_positions()
        return ok(resp)
    except Exception as e:
        return JSONResponse(fail(e), status_code=500)

# ----- Expiry list (e.g. NIFTY 13 / IDX_I) -----
@app.post("/expiry_list")
async def expiry_list(req: Request):
    ensure_client()
    body = await req.json()
    under_security_id = body.get("under_security_id")
    under_exchange_segment = body.get("under_exchange_segment")

    if under_security_id is None or not under_exchange_segment:
        raise HTTPException(
            status_code=400,
            detail="Provide 'under_security_id' and 'under_exchange_segment'.",
        )
    try:
        resp = dhan.expiry_list(
            under_security_id=under_security_id,
            under_exchange_segment=under_exchange_segment,
        )
        return ok(resp)
    except Exception as e:
        return JSONResponse(fail(e), status_code=500)

# ----- Option chain -----
@app.post("/option_chain")
async def option_chain(req: Request):
    """
    Body:
    {
      "under_security_id": 13,
      "under_exchange_segment": "IDX_I",
      "expiry": "YYYY-MM-DD"   # optional; if missing => latest
    }
    """
    ensure_client()
    body = await req.json()
    u_sid = body.get("under_security_id")
    u_seg = body.get("under_exchange_segment")
    expiry = body.get("expiry")  # optional

    if u_sid is None or not u_seg:
        raise HTTPException(
            status_code=400,
            detail="Provide 'under_security_id' and 'under_exchange_segment'.",
        )

    try:
        # If expiry not supplied, pick latest from /expiry_list
        if not expiry:
            elist = dhan.expiry_list(under_security_id=u_sid, under_exchange_segment=u_seg)
            # SDK usually returns list of ISO dates; pick the first or max
            if isinstance(elist, list) and elist:
                # Many APIs return ascending; choose the nearest (first)
                expiry = str(elist[0])
            else:
                raise ValueError("No expiries returned for given underlying.")

        resp = dhan.option_chain(
            under_security_id=u_sid,
            under_exchange_segment=u_seg,
            expiry=expiry,
        )
        return ok({"requested_expiry": expiry, "option_chain": resp})
    except Exception as e:
        # Common server message for invalid date
        return JSONResponse(fail(e), status_code=400)
