import os
import csv
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

# ---------- Load env ----------
load_dotenv()

MODE = os.getenv("MODE", "SANDBOX").upper()  # SANDBOX | LIVE
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Dhan v2 REST base
DHAN_BASE = "https://api.dhan.co/v2"

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("options-analysis")

# ---------- FastAPI app ----------
app = FastAPI(title="Options-analysis (Dhan v2 + AI)")

# serve /public (optional)
if Path("public").exists():
    app.mount("/static", StaticFiles(directory="public"), name="static")


@app.get("/", include_in_schema=False)
def serve_index():
    # serve /public/index.html if present, else 404 guidance
    idx = Path("public/index.html")
    if idx.exists():
        return FileResponse(idx)
    return JSONResponse(
        {"ok": True, "msg": "Place your UI at public/index.html or call the JSON APIs."}
    )


# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # loosen for dev; tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Security helper ----------
def verify_secret(req: Request):
    if not WEBHOOK_SECRET:
        return True
    token = req.headers.get("X-Webhook-Secret")
    if token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid Webhook Secret")
    return True


# ---------- Annexure (from your pasted table) ----------
ANNEXURE = {
    "exchange_segment": {
        "IDX_I": {"exchange": "Index", "segment": "Index Value", "code": 0},
        "NSE_EQ": {"exchange": "NSE", "segment": "Equity Cash", "code": 1},
        "NSE_FNO": {"exchange": "NSE", "segment": "Futures & Options", "code": 2},
        "NSE_CURRENCY": {"exchange": "NSE", "segment": "Currency", "code": 3},
        "BSE_EQ": {"exchange": "BSE", "segment": "Equity Cash", "code": 4},
        "MCX_COMM": {"exchange": "MCX", "segment": "Commodity", "code": 5},
        "BSE_CURRENCY": {"exchange": "BSE", "segment": "Currency", "code": 7},
        "BSE_FNO": {"exchange": "BSE", "segment": "Futures & Options", "code": 8},
    },
    "product_type": ["CNC", "INTRADAY", "MARGIN", "CO", "BO"],
    "expiry_code": {"0": "Current/Near", "1": "Next", "2": "Far"},
    "instrument": [
        "INDEX", "FUTIDX", "OPTIDX", "EQUITY", "FUTSTK", "OPTSTK",
        "FUTCOM", "OPTFUT", "FUTCUR", "OPTCUR"
    ],
    "feed_request": {
        11: "Connect Feed", 12: "Disconnect Feed", 15: "Sub Ticker", 16: "Unsub Ticker",
        17: "Sub Quote", 18: "Unsub Quote", 21: "Sub Full", 22: "Unsub Full",
        23: "Sub 20 Depth", 24: "Unsub 20 Depth"
    },
    "feed_response": {
        1: "Index Packet", 2: "Ticker Packet", 4: "Quote Packet", 5: "OI Packet",
        6: "Prev Close", 7: "Market Status", 8: "Full Packet", 50: "Feed Disconnect"
    }
}


@app.get("/annexure")
def get_annexure():
    return {"ok": True, "data": ANNEXURE}


# ---------- Dhan REST helpers ----------
def _dhan_headers() -> Dict[str, str]:
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail="Broker creds missing (Client ID / Access Token).")
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Client-Id": DHAN_CLIENT_ID,
        "Access-Token": DHAN_ACCESS_TOKEN,
    }


def dhan_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{DHAN_BASE}{path}"
    try:
        r = requests.get(url, headers=_dhan_headers(), params=params, timeout=15)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=_mk_err(r))
        return r.json()
    except requests.RequestException as e:
        log.exception("GET failed")
        raise HTTPException(status_code=502, detail=str(e))


def dhan_post(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{DHAN_BASE}{path}"
    try:
        r = requests.post(url, headers=_dhan_headers(), json=body, timeout=20)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=_mk_err(r))
        return r.json()
    except requests.RequestException as e:
        log.exception("POST failed")
        raise HTTPException(status_code=502, detail=str(e))


def _mk_err(resp: requests.Response) -> str:
    try:
        j = resp.json()
        # Dhan data error codes 800.. etc
        return f"{resp.status_code} {j}"
    except Exception:
        return f"{resp.status_code} {resp.text}"


# ---------- Self test ----------
@app.get("/__selftest")
def selftest():
    info = {
        "env": "Render/Cloud",
        "mode": MODE,
        "status": {
            "client_id_present": bool(DHAN_CLIENT_ID),
            "token_present": bool(DHAN_ACCESS_TOKEN),
        },
    }
    return {"ok": True, "status": info}


# ---------- Instruments (CSV lookup) ----------
# Expect path: data/instruments.csv (large file from Dhan "Instrument List")
INSTR_PATHS = [
    Path("data/instruments.csv"),
    Path("data/InstrumentList.csv"),
]

# minimal safe fallback (if CSV not available)
FALLBACK_INSTR = [
    # exchange_segment, security_id, trading_symbol, instrument
    {"exchange_segment": "IDX_I", "security_id": 13, "trading_symbol": "NIFTY 50", "instrument": "INDEX"},
    {"exchange_segment": "IDX_I", "security_id": 25, "trading_symbol": "BANKNIFTY", "instrument": "INDEX"},
    {"exchange_segment": "NSE_EQ", "security_id": 1333, "trading_symbol": "HDFCBANK", "instrument": "EQUITY"},
]


def _load_instruments() -> List[Dict[str, Any]]:
    for p in INSTR_PATHS:
        if p.exists():
            rows: List[Dict[str, Any]] = []
            with p.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # normalize common columns; keep raw as well
                    row["security_id"] = int(row.get("security_id") or row.get("SecurityId") or 0)
                    row["exchange_segment"] = (
                        row.get("exchange_segment") or row.get("ExchangeSegment") or ""
                    ).strip()
                    row["trading_symbol"] = (row.get("trading_symbol") or row.get("Symbol") or "").strip()
                    row["instrument"] = (row.get("instrument") or row.get("Instrument") or "").strip()
                    rows.append(row)
            return rows
    return FALLBACK_INSTR


INSTR_CACHE = _load_instruments()


@app.get("/instruments/search")
def instruments_search(
    q: str = Query(..., description="Symbol/Name contains"),
    exchange_segment: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
):
    ql = q.lower().strip()
    out = []
    for r in INSTR_CACHE:
        if ql in str(r.get("trading_symbol", "")).lower() or ql in str(r).lower():
            if exchange_segment and r.get("exchange_segment") != exchange_segment:
                continue
            out.append(
                {
                    "exchange_segment": r.get("exchange_segment"),
                    "security_id": r.get("security_id"),
                    "trading_symbol": r.get("trading_symbol"),
                    "instrument": r.get("instrument"),
                }
            )
        if len(out) >= limit:
            break
    return {"ok": True, "count": len(out), "data": out}


# ---------- Data APIs ----------

@app.get("/marketquote")
def market_quote(
    exchange_segment: str = Query(..., description="e.g. NSE_EQ / NSE_FNO / IDX_I"),
    security_id: int = Query(..., description="numeric security id"),
    mode: str = Query("full", description="ticker|quote|full (per docs)"),
):
    """
    Snapshot quote (REST). For real-time streaming, use Live Market Feed (WebSocket) from frontend.
    """
    # docs for v2: /market-quote? (Dhan has POST with list or GET by params; here use a common GET path)
    # Many implementations use /market-quote?securityId=...&exchangeSegment=...&mode=...
    # We stick to the doc style query.
    j = dhan_get(
        "/market-quote",
        params={
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "mode": mode,
        },
    )
    return {"ok": True, "data": j}


@app.get("/marketfeed/ltp")
def market_ltp(exchange_segment: str = "NSE_EQ", security_id: int = 1333):
    """
    Convenience LTP endpoint (pulls ticker/quote and returns last traded price).
    """
    j = dhan_get(
        "/market-quote",
        params={
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "mode": "ticker",
        },
    )
    # Normalize LTP from response (structure differs; map common ones)
    ltp = None
    try:
        # Dhan returns list sometimes; handle both
        if isinstance(j, dict) and "data" in j:
            payload = j["data"]
        else:
            payload = j
        # make a best effort guess:
        ltp = (
            payload.get("ltp")
            or payload.get("LTP")
            or payload.get("last_price")
            or payload.get("lastTradedPrice")
        )
    except Exception:
        pass
    return {"ok": True, "data": {"ltp": ltp, "raw": j}}


@app.get("/optionchain/expirylist")
def optionchain_expirylist(
    under_security_id: int = Query(...),
    under_exchange_segment: str = Query(...),
):
    """
    Returns available expiries (as per Dhan v2 Option Chain API).
    """
    j = dhan_get(
        "/option-chain/expiries",
        params={
            "underSecurityId": under_security_id,
            "underExchangeSegment": under_exchange_segment,
        },
    )
    return {"ok": True, "data": j}


@app.post("/optionchain")
def optionchain(body: Dict[str, Any]):
    """
    Request body:
    {
      "under_security_id": 25,
      "under_exchange_segment": "IDX_I",
      "expiry": "2025-09-25"
    }
    """
    under_security_id = int(body.get("under_security_id"))
    under_exchange_segment = body.get("under_exchange_segment")
    expiry = body.get("expiry")

    j = dhan_post(
        "/option-chain",
        {
            "underSecurityId": under_security_id,
            "underExchangeSegment": under_exchange_segment,
            "expiry": expiry,
        },
    )
    return {"ok": True, "data": j}


@app.get("/historical")
def historical(
    exchange_segment: str = Query(...),
    security_id: int = Query(...),
    interval: str = Query("1", description="minutes (1/3/5/15/30), or 'D' for daily"),
    from_date: str = Query(..., description="YYYY-MM-DD"),
    to_date: str = Query(..., description="YYYY-MM-DD"),
):
    """
    Historical OHLC
    """
    j = dhan_get(
        "/historical",
        params={
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "interval": interval,
            "fromDate": from_date,
            "toDate": to_date,
        },
    )
    return {"ok": True, "data": j}


@app.get("/marketdepth20")
def market_depth_20(
    exchange_segment: str = Query(...),
    security_id: int = Query(...),
):
    """
    20-Level Market Depth (snapshot pull)
    """
    j = dhan_get(
        "/market-depth",
        params={
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "levels": 20,
        },
    )
    return {"ok": True, "data": j}


# ---------- Orders / Portfolio (stubs you can extend) ----------
@app.post("/orders/place")
def place_order(body: Dict[str, Any], auth: bool = Depends(verify_secret)):
    """
    Minimal pass-through. You MUST validate required fields on your UI.
    """
    j = dhan_post("/orders", body)
    return {"ok": True, "data": j}


@app.get("/orders")
def order_book():
    j = dhan_get("/orders")
    return {"ok": True, "data": j}


@app.get("/trades")
def trade_book():
    j = dhan_get("/trades")
    return {"ok": True, "data": j}


@app.get("/positions")
def positions():
    j = dhan_get("/positions")
    return {"ok": True, "data": j}


@app.get("/holdings")
def holdings():
    j = dhan_get("/holdings")
    return {"ok": True, "data": j}


# ---------- AI endpoints ----------
# Uses official OpenAI client >= 1.0
# If OPENAI_API_KEY missing, we return 400
def _openai():
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY missing")
    # lazy import to avoid startup crash if lib missing
    from openai import OpenAI
    return OpenAI(api_key=OPENAI_API_KEY)


@app.post("/ai/marketview")
def ai_marketview(req: Dict[str, Any], auth: bool = Depends(verify_secret)):
    client = _openai()
    prompt = (
        "You are an options market analyst. Using the following inputs, give a crisp intraday/positional view, "
        "key levels, and risk notes. Keep it structured with bullets.\n\n"
        f"INPUT:\n{json.dumps(req, indent=2)}"
    )
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return {"ok": True, "ai_reply": r.choices[0].message.content}


@app.post("/ai/strategy")
def ai_strategy(req: Dict[str, Any], auth: bool = Depends(verify_secret)):
    client = _openai()
    prompt = (
        "Suggest 1-2 options strategies (with strikes, qty lot, max loss, risk:reward, payoff notes) "
        "that match bias/risk/capital. Assume Indian F&O.\n\n"
        f"INPUT:\n{json.dumps(req, indent=2)}"
    )
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return {"ok": True, "ai_strategy": r.choices[0].message.content}


@app.post("/ai/payoff")
def ai_payoff(req: Dict[str, Any], auth: bool = Depends(verify_secret)):
    client = _openai()
    prompt = (
        "Given this option position set, compute key payoff points (break-evens, max profit/loss) "
        "and a short explanation of Greeks exposure. Keep it concise.\n\n"
        f"INPUT:\n{json.dumps(req, indent=2)}"
    )
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return {"ok": True, "ai_payoff": r.choices[0].message.content}


@app.post("/ai/test")
def ai_test():
    client = _openai()
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Reply 'pong' only."}],
        temperature=0,
    )
    return {"ok": True, "ai_test_reply": r.choices[0].message.content}


# ---------- Error handler ----------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"error": str(exc)})
