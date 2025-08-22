import os, random, time
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# -----------------------
# Settings (env variables)
# -----------------------
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret")
DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "NIFTY").upper()

app = FastAPI(title="Options Analysis Bot (DEMO)", version="1.0")

# -----------------------
# Helpers: expiry utilities
# -----------------------
# Weekly expiry mapping (historical common setup):
# NIFTY: Thu(3), BANKNIFTY: Wed(2), FINNIFTY: Tue(1)
WEEKLY_WD = {"NIFTY": 3, "BANKNIFTY": 2, "FINNIFTY": 1}

def _next_weekday(d: date, target_wd: int) -> date:
    ahead = (target_wd - d.weekday()) % 7
    if ahead == 0:
        ahead = 7
    return d + timedelta(days=ahead)

def next_weekly_expiry(symbol: str, today: Optional[date] = None) -> date:
    today = today or date.today()
    target = WEEKLY_WD.get(symbol.upper(), 3)
    return _next_weekday(today, target)

# -----------------------
# DEMO option-chain + metrics
# -----------------------
def synthetic_chain(symbol: str, n: int = 21, start_strike: int = 25000, step: int = 50) -> List[Dict[str, Any]]:
    """Make a fake option chain so you can test endpoints without real API keys."""
    strikes = [start_strike + i * step for i in range(-n // 2, n // 2 + 1)]
    expiry = next_weekly_expiry(symbol).isoformat()
    rows = []
    base_iv = random.uniform(10, 25)
    for k in strikes:
        ce_iv = max(5, base_iv + random.uniform(-2, 2))
        pe_iv = max(5, base_iv + random.uniform(-2, 2))
        ce_oi = random.randint(5_000, 150_000)
        pe_oi = random.randint(5_000, 150_000)
        ce_ltp = max(1, random.uniform(5, 250))
        pe_ltp = max(1, random.uniform(5, 250))
        rows.append({
            "expiry": expiry,
            "strike": k,
            "ce_oi": ce_oi, "pe_oi": pe_oi,
            "ce_ltp": ce_ltp, "pe_ltp": pe_ltp,
            "ce_iv": ce_iv, "pe_iv": pe_iv,
        })
    rows.sort(key=lambda r: r["strike"])
    return rows

def compute_pcr(rows: List[Dict[str, Any]]) -> float:
    ce = sum(r.get("ce_oi", 0) or 0 for r in rows)
    pe = sum(r.get("pe_oi", 0) or 0 for r in rows)
    return float(pe / ce) if ce > 0 else 0.0

def top_oi(rows: List[Dict[str, Any]], side: str = "CE", n: int = 5) -> List[Dict[str, Any]]:
    key = "ce_oi" if side.upper() == "CE" else "pe_oi"
    return sorted(
        [{"strike": r["strike"], key: r.get(key, 0)} for r in rows],
        key=lambda x: x[key],
        reverse=True
    )[:n]

def simple_signal(pcr: float) -> str:
    if pcr < 0.8:
        return f"BULLISH (PCR={pcr:.2f})"
    if pcr > 1.2:
        return f"BEARISH (PCR={pcr:.2f})"
    return f"NEUTRAL (PCR={pcr:.2f})"

# -----------------------
# Schemas
# -----------------------
class TVAlert(BaseModel):
    secret: str
    symbol: str
    action: str               # BUY / SELL / EXIT
    instrument_type: str = "OPTIONS"
    expiry: Optional[str] = None   # YYYY-MM-DD
    strike: Optional[float] = None
    option_type: Optional[str] = None  # CE / PE
    qty: int = 50
    price: str = "MARKET"     # MARKET / LIMIT
    limit_price: Optional[float] = None
    strategy: Optional[str] = None

# -----------------------
# Endpoints
# -----------------------
@app.get("/health")
def health():
    return {"ok": True, "demo": DEMO_MODE}

@app.get("/chain")
def chain(symbol: str = DEFAULT_SYMBOL):
    """
    DEMO: returns a synthetic option chain with expiry + PCR.
    Later we will switch to real Dhan API when DEMO_MODE=false.
    """
    rows = synthetic_chain(symbol)
    pcr = compute_pcr(rows)
    return {"symbol": symbol, "rows": len(rows), "expiry": rows[0]["expiry"], "pcr": pcr, "data": rows}

@app.get("/signals")
def signals(symbol: str = DEFAULT_SYMBOL):
    rows = synthetic_chain(symbol)
    pcr = compute_pcr(rows)
    sig = simple_signal(pcr)
    return {
        "symbol": symbol,
        "signal": sig,
        "pcr": pcr,
        "ce_top": top_oi(rows, "CE"),
        "pe_top": top_oi(rows, "PE"),
    }

@app.post("/webhook")
def webhook(alert: TVAlert):
    if alert.secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")

    order = {
        "transactionType": "BUY" if alert.action.upper() == "BUY" else "SELL",
        "instrument": "OPTIDX",
        "symbol": f"{alert.symbol} {alert.expiry or 'NA'} {int((alert.strike or 0))} {alert.option_type or 'XX'}",
        "quantity": alert.qty,
        "orderType": alert.price,
        "price": 0 if alert.price.upper() == "MARKET" else (alert.limit_price or 0),
        "productType": "INTRADAY",
        "validity": "DAY",
        "remarks": alert.strategy or "tv-webhook",
    }
    # DEMO: just echo back (no live order).
    return {"ok": True, "received": alert.model_dump(), "order": order}
