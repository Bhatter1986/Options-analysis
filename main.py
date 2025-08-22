import os, time
from typing import Optional, Literal
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

app = FastAPI(title="Options Analysis Bot")

# --- ENV CONFIG ---
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
MODE = os.getenv("MODE", "DRY").upper()              # DRY or LIVE
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

# try to import dhanhq sdk if present
try:
    from dhanhq import dhanhq as dhanhq_sdk  # <- some installs expose this name
    _has_dhan_lib = True
except Exception:
    _has_dhan_lib = False
    dhanhq_sdk = None

# lazy init client (only if lib is present)
_dhan_client = None
def get_dhan_client():
    global _dhan_client
    if _dhan_client is None and _has_dhan_lib and DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
        try:
            # Some versions use dhanhq_sdk.dhanhq; others expose class directly.
            # Both patterns are tried below for compatibility.
            try:
                _dhan_client = dhanhq_sdk.dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
            except Exception:
                _dhan_client = dhanhq_sdk.DhanHQ(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
        except Exception:
            pass
    return _dhan_client

# --- MODELS ---
class OrderPayload(BaseModel):
    secret: str
    # Either security_id do, ya niche wale fields informational:
    security_id: Optional[int] = None
    symbol: Optional[str] = None         # e.g., "NIFTY"
    action: Literal["BUY", "SELL"]
    expiry: Optional[str] = None         # "YYYY-MM-DD"
    strike: Optional[int] = None
    option_type: Optional[Literal["CE", "PE"]] = None
    qty: int
    price: Optional[Literal["MARKET", "LIMIT"]] = "MARKET"
    limit_price: Optional[float] = None  # only if price == "LIMIT"
    product: Optional[Literal["INTRADAY", "CARRYFORWARD"]] = "INTRADAY"

# --- HEALTH ---
@app.get("/")
def root():
    return {"message": "Hello India Market 🚀"}

@app.get("/health")
def health():
    return {"ok": True}

# Quick status to confirm credentials/mode
@app.get("/broker_status")
def broker_status():
    ready = bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN)
    client = get_dhan_client()
    return {
        "mode": MODE,
        "has_lib": _has_dhan_lib,
        "has_creds": ready,
        "client_ready": bool(client) or (not _has_dhan_lib and ready)  # REST fallback case
    }

# --- ORDER HELPERS ---
def place_order_via_sdk(p: OrderPayload):
    """
    Live order via dhanhq sdk (if installed).
    You MUST provide a valid security_id in LIVE mode.
    """
    client = get_dhan_client()
    if not client:
        return {"status": "failure", "remarks": {"reason": "dhanhq sdk not available"}}

    if not p.security_id:
        return {"status": "failure", "remarks": {"reason": "security_id required in LIVE mode"}}

    # Many installs expect keys like these; keep defaults conservative.
    exchange_segment = "NSE_FNO"
    order_type = p.price or "MARKET"       # MARKET/LIMIT
    transaction_type = p.action            # BUY/SELL
    product_type = p.product or "INTRADAY" # INTRADAY/CARRYFORWARD
    validity = "DAY"
    price = float(p.limit_price or 0)

    try:
        # Most sdk versions expose place_order; arguments vary slightly across releases.
        # Use kwargs to be resilient.
        res = client.place_order(
            security_id=int(p.security_id),
            exchange_segment=exchange_segment,
            transaction_type=transaction_type,
            order_type=order_type,
            product_type=product_type,
            quantity=int(p.qty),
            price=price,
            validity=validity,
            after_market_order=False,
        )
        return res if isinstance(res, dict) else {"status": "success", "response": str(res)}
    except Exception as e:
        return {"status": "failure", "remarks": {"exception": str(e)}}

@app.post("/webhook")
async def webhook(payload: OrderPayload):
    # 1) Secret check
    if payload.secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 2) DRY path: no live hit, just echo what will be sent
    if MODE == "DRY":
        order = {
            "side": payload.action,
            "symbol": payload.symbol or "N/A",
            "expiry": payload.expiry,
            "strike": payload.strike,
            "type": payload.option_type,
            "qty": payload.qty,
            "price": payload.price,
            "security_id": payload.security_id,
        }
        return {
            "ok": True,
            "mode": MODE,
            "received": payload.model_dump(),
            "order": order,
            "note": "DRY mode active. Set MODE=LIVE and send security_id to place order."
        }

    # 3) LIVE path: sanity checks
    if not (DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN):
        raise HTTPException(status_code=400, detail="Dhan credentials not set")

    if not payload.security_id:
        raise HTTPException(status_code=422, detail="security_id is required in LIVE mode")

    # 4) Place order via SDK if available; else short-circuit with a clear message
    if _has_dhan_lib:
        broker_res = place_order_via_sdk(payload)
    else:
        broker_res = {
            "status": "failure",
            "remarks": {"reason": "dhanhq library not installed; use SDK or add REST call here"}
        }

    ok = str(broker_res.get("status", "")).lower() in ("success", "ok", "true")
    return {
        "ok": ok,
        "mode": MODE,
        "received": payload.model_dump(),
        "order": {
            "side": payload.action,
            "symbol": payload.symbol,
            "expiry": payload.expiry,
            "strike": payload.strike,
            "type": payload.option_type,
            "qty": payload.qty,
            "price": payload.price,
            "security_id": payload.security_id,
        },
        "broker_response": broker_res
    }
