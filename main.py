import os
import json
import math
import random
import logging
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from dotenv import load_dotenv

# ---------- env ----------
load_dotenv()
MODE = os.getenv("MODE", "SANDBOX").upper()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ---------- app ----------
app = FastAPI(title="Options-analysis (Dhan v2 + AI)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# serve static
if os.path.isdir("public"):
    app.mount("/static", StaticFiles(directory="public"), name="static")

@app.get("/", include_in_schema=False)
def serve_root():
    # if public/index.html exists, serve it; else simple hello
    f = "public/index.html"
    if os.path.exists(f):
        return FileResponse(f)
    return JSONResponse({"ok": True, "hint": "put your index.html in /public"})

@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    f = "public/dashboard.html"
    if os.path.exists(f):
        return FileResponse(f)
    # fallback to index if only one file is used
    return serve_root()

# ---------- utils ----------
logger = logging.getLogger("options-analysis")
logging.basicConfig(level=logging.INFO)

def verify_secret(req: Request):
    # only used by /ai/* endpoints; others open
    token = req.headers.get("X-Webhook-Secret")
    if WEBHOOK_SECRET and token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid Webhook Secret")
    return True

IST = timezone(timedelta(hours=5, minutes=30))

def next_n_thursdays(n=6):
    """Return next n Thursday dates (YYYY-MM-DD) in IST."""
    now = datetime.now(IST).date()
    # weekday(): Mon=0 ... Sun=6 ; Thursday=3
    days_ahead = (3 - now.weekday()) % 7
    first = now + timedelta(days=days_ahead or 7)  # always future
    return [(first + timedelta(weeks=i)).isoformat() for i in range(n)]

# ---------- basic endpoints ----------
@app.get("/health")
def health():
    return {"status": "ok", "mode": MODE}

@app.get("/broker_status")
def broker_status():
    # we just check env presence; UI only needs booleans
    live = MODE == "LIVE"
    token_present = bool(os.getenv("DHAN_LIVE_ACCESS_TOKEN" if live else "DHAN_SANDBOX_ACCESS_TOKEN"))
    client_present = bool(os.getenv("DHAN_LIVE_CLIENT_ID" if live else "DHAN_SANDBOX_CLIENT_ID"))
    return {"mode": MODE, "token_present": token_present, "client_id_present": client_present}

@app.get("/__selftest")
def selftest():
    routes = [r.path for r in app.routes]
    return {
        "app": "Options-analysis (Dhan v2 + AI)",
        "mode": MODE,
        "env": MODE,
        "now": datetime.now(IST).isoformat(),
        "endpoints": sorted(routes),
    }

# ---------- demo marketfeed ----------
@app.get("/marketfeed/ltp")
def marketfeed_ltp(exchange_segment: str = "NSE", security_id: int = 1333):
    # lightweight demo LTP for HDFCBANK etc.
    base = 1600.0 if security_id == 1333 else 100.0
    jitter = (random.random() - 0.5) * 2.0
    return {
        "data": {
            "data": {
                "NSE_EQ": [{"security_id": security_id, "ltp": round(base + jitter, 2)}]
            }
        }
    }

# ---------- OPTION CHAIN (mock that unblocks UI) ----------
@app.get("/optionchain/expirylist")
def optionchain_expirylist(
    under_security_id: int = Query(..., description="13=NIFTY, 25=BANKNIFTY etc."),
    under_exchange_segment: str = Query(..., description="IDX_I etc."),
):
    """
    Return a simple list of next weekly expiries.
    Frontend expects: { data: { data: [ 'YYYY-MM-DD', ... ] } }
    """
    # we ignore params in this mock, just generate Thursdays
    expiries = next_n_thursdays(8)
    return {"data": {"data": expiries}}

def _make_chain(under_security_id: int, expiry: str):
    """
    Build a synthetic option chain around a spot & strikes so charts/table render.
    Structure per row:
      raw[strike] = { CE:{...}, PE:{...} }
    """
    # choose a spot anchor
    if under_security_id == 25:   # BANKNIFTY
        spot = 48500
        step = 100
    elif under_security_id == 13: # NIFTY
        spot = 24000
        step = 50
    else:
        spot = 20000
        step = 50

    # strikes +/- 30 steps
    strikes = [spot + i*step for i in range(-30, 31)]
    chain = {}
    for sp in strikes:
        dist = abs(sp - spot) / step
        # higher dist -> lower OI/volume, lower price for OTM, etc.
        base_oi = max(0, int(150000 - dist*4000 + random.randint(-1500, 1500)))
        base_vol = max(0, int(5000 - dist*120 + random.randint(-100, 100)))
        iv = round(16 + dist*0.15 + random.random()*2, 2)
        ce_price = max(1.0, round(max(0, spot - sp) * 0.6 + random.random()*30, 2))
        pe_price = max(1.0, round(max(0, sp - spot) * 0.6 + random.random()*30, 2))
        ce_chg = round((random.random() - 0.5) * 10, 2)
        pe_chg = round((random.random() - 0.5) * 10, 2)
        prev_oi_jitter = random.randint( -800, 800)

        chain[sp] = {
            "CE": {
                "oi": base_oi + random.randint(-2000, 2000),
                "previous_oi": base_oi - prev_oi_jitter,
                "volume": base_vol + random.randint(-50, 50),
                "implied_volatility": iv,
                "last_price": ce_price,
                "change": ce_chg,
            },
            "PE": {
                "oi": base_oi + random.randint(-2000, 2000),
                "previous_oi": base_oi + prev_oi_jitter,
                "volume": base_vol + random.randint(-50, 50),
                "implied_volatility": iv + 0.4,
                "last_price": pe_price,
                "change": pe_chg,
            }
        }
    return chain

@app.post("/optionchain")
def optionchain(payload: dict):
    """
    Frontend sends:
      { under_security_id:int, under_exchange_segment:str, expiry:str }
    We return:
      { data: { data: { "<strike>": { CE:{...}, PE:{...} } } } }
    """
    try:
        under_security_id = int(payload.get("under_security_id"))
        expiry = str(payload.get("expiry") or "")
    except Exception:
        raise HTTPException(400, "Invalid payload")

    data = _make_chain(under_security_id, expiry)
    return {"data": {"data": data}}

# ---------- AI placeholders (headers must include X-Webhook-Secret) ----------
@app.post("/ai/marketview")
def ai_marketview(req: dict, _auth: bool = Depends(verify_secret)):
    # lightweight mock reply so button works
    return {"ai_reply": f"Market view (mock): bias={req.get('bias','neutral')}, under={req.get('under_security_id')}"}

@app.post("/ai/strategy")
def ai_strategy(req: dict, _auth: bool = Depends(verify_secret)):
    return {"ai_strategy": "Sample: Short Straddle near ATM, hedge with wings, risk-managed (mock)."}

@app.post("/ai/payoff")
def ai_payoff(req: dict, _auth: bool = Depends(verify_secret)):
    return {"ai_payoff": "Payoff summary (mock): Max profit limited to credit, max loss capped by wings."}

@app.post("/ai/test")
def ai_test(_req: dict):
    return {"ai_test_reply": "pong"}
