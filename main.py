from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello India Market 🚀"}

@app.get("/health")
def health():
    return {"ok": True}

# New Endpoint: Options Analysis (dummy)
@app.get("/options")
def options_analysis():
    data = {
        "symbol": "NIFTY",
        "strike": 25000,
        "trend": "Bullish",
        "iv": 12.5,
        "delta": 0.62
    }
    return {"options_data": data}
from pydantic import BaseModel
from fastapi import HTTPException

class TVAlert(BaseModel):
    secret: str
    symbol: str
    action: str
    expiry: str | None = None
    strike: float | None = None
    option_type: str | None = None
    qty: int = 50
    price: str = "MARKET"

WEBHOOK_SECRET = "My$ecret123"  # baad me Render ENV me daalenge

@app.post("/webhook")
def webhook(alert: TVAlert):
    if alert.secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")
    order = {
        "side": "BUY" if alert.action.upper() == "BUY" else "SELL",
        "symbol": alert.symbol,
        "expiry": alert.expiry,
        "strike": alert.strike,
        "type": alert.option_type,
        "qty": alert.qty,
        "price": alert.price
    }
    return {"ok": True, "received": alert.model_dump(), "order": order}
