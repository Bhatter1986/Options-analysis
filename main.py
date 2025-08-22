from fastapi import FastAPI, Request, HTTPException
import os

app = FastAPI()

# ✅ Secret ab environment se aayega (Render ke env vars me set karna hoga)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    # ✅ Secret check
    secret = data.get("secret")
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # ✅ Order fields extract
    symbol = data.get("symbol")
    action = data.get("action")
    expiry = data.get("expiry")
    strike = data.get("strike")
    option_type = data.get("option_type")
    qty = data.get("qty")
    price = data.get("price")

    if not all([symbol, action, expiry, strike, option_type, qty, price]):
        raise HTTPException(status_code=422, detail="Missing required fields")

    # ✅ Response back (later yahan Dhan API call add karenge)
    return {
        "ok": True,
        "received": data,
        "order": {
            "side": action,
            "symbol": symbol,
            "expiry": expiry,
            "strike": strike,
            "type": option_type,
            "qty": qty,
            "price": price
        }
    }
