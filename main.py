import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# --- Dhan SDK ---
from dhanhq import dhanhq as DhanHQ

# --- Optional AI (OpenAI) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_APIKEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

try:
    if OPENAI_API_KEY:
        from openai import OpenAI
        _openai_client: Optional["OpenAI"] = OpenAI(api_key=OPENAI_API_KEY)
    else:
        _openai_client = None
except Exception:
    _openai_client = None  # fail open to non-AI mode

# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(title="Options-analysis (Dhan v2) + AI")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# ENV / MODE & Dhan client
# -----------------------------------------------------------------------------
def _pick(*keys: str) -> Optional[str]:
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return None

MODE = os.getenv("MODE", "TEST").upper()  # LIVE or TEST (SANDBOX)
ENV_NOTE = "LIVE" if MODE == "LIVE" else "SANDBOX"

if MODE == "LIVE":
    CLIENT_ID = _pick("DHAN_LIVE_CLIENT_ID", "DHAN_CLIENT_ID")
    ACCESS_TOKEN = _pick("DHAN_LIVE_ACCESS_TOKEN", "DHAN_ACCESS_TOKEN")
else:
    CLIENT_ID = _pick("DHAN_SANDBOX_CLIENT_ID", "DHAN_CLIENT_ID")
    ACCESS_TOKEN = _pick("DHAN_SANDBOX_ACCESS_TOKEN", "DHAN_ACCESS_TOKEN")

# One Dhan client
dhan = DhanHQ(CLIENT_ID or "", ACCESS_TOKEN or "")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def ok(data: Any, remarks: str = "") -> Dict[str, Any]:
    return {"status": "success", "remarks": remarks, "data": data}

def fail(msg: str, code: Optional[str] = None, etype: Optional[str] = None, data: Any = None) -> Dict[str, Any]:
    return {"status": "failure", "remarks": {"error_code": code, "error_type": etype, "error_message": msg}, "data": data}

def _quote_key(seg: str) -> str:
    s = seg.upper().strip()
    if s in ("NSE", "NSE_EQ"): return "NSE_EQ"
    if s in ("BSE", "BSE_EQ"): return "BSE_EQ"
    if s in ("NSE_FNO",):      return "NSE_FNO"
    if s in ("MCX", "MCX_COMM"): return "MCX_COMM"
    return s

# -----------------------------------------------------------------------------
# Root / Index
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "app": app.title,
        "mode": MODE,
        "env": ENV_NOTE,
        "now": datetime.now(timezone.utc).isoformat(),
        "endpoints": [
            "/health", "/broker_status",
            "/marketfeed/ltp", "/marketfeed/ohlc", "/marketfeed/quote",
            "/optionchain", "/optionchain/expirylist",
            "/orders", "/positions", "/holdings", "/funds",
            "/charts/intraday", "/charts/historical",
            "/option_analysis",
            # AI
            "/ai/marketview", "/ai/strategy", "/ai/payoff",
            "/__selftest"
        ],
    }

# -----------------------------------------------------------------------------
# Health / Status
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return ok({"ok": True, "time": datetime.now(timezone.utc).isoformat()})

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "env": ENV_NOTE,
        "token_present": bool(ACCESS_TOKEN),
        "client_id_present": bool(CLIENT_ID),
        "ai_enabled": bool(_openai_client),
        "ai_model": OPENAI_MODEL if _openai_client else None,
    }

# -----------------------------------------------------------------------------
# Portfolio
# -----------------------------------------------------------------------------
@app.get("/orders")
def orders():
    try:
        return ok(dhan.get_order_list())
    except Exception as e:
        return fail("orders fetch failed", data=str(e))

@app.get("/positions")
def positions():
    try:
        return ok(dhan.get_positions())
    except Exception as e:
        return fail("positions fetch failed", data=str(e))

@app.get("/holdings")
def holdings():
    try:
        return ok(dhan.get_holdings())
    except Exception as e:
        return fail("holdings fetch failed", data=str(e))

@app.get("/funds")
def funds():
    try:
        return ok(dhan.get_fund_limits())
    except Exception as e:
        return fail("funds fetch failed", data=str(e))

# -----------------------------------------------------------------------------
# Market Quote (snapshot REST)
# -----------------------------------------------------------------------------
@app.get("/marketfeed/ltp")
def market_ltp(exchange_segment: str = Query(...), security_id: int = Query(...)):
    try:
        payload = { _quote_key(exchange_segment): [int(security_id)] }
        return ok(dhan.ticker_data(securities=payload))
    except Exception as e:
        return fail("ltp fetch failed", data=str(e))

@app.get("/marketfeed/ohlc")
def market_ohlc(exchange_segment: str = Query(...), security_id: int = Query(...)):
    try:
        payload = { _quote_key(exchange_segment): [int(security_id)] }
        return ok(dhan.ohlc_data(securities=payload))
    except Exception as e:
        return fail("ohlc fetch failed", data=str(e))

@app.get("/marketfeed/quote")
def market_quote(exchange_segment: str = Query(...), security_id: int = Query(...)):
    try:
        payload = { _quote_key(exchange_segment): [int(security_id)] }
        return ok(dhan.quote_data(securities=payload))
    except Exception as e:
        return fail("quote fetch failed", data=str(e))

# -----------------------------------------------------------------------------
# Option Chain
# -----------------------------------------------------------------------------
class OptionChainBody(BaseModel):
    under_security_id: int
    under_exchange_segment: str
    expiry: str

@app.get("/optionchain/expirylist")
def optionchain_expirylist(
    under_security_id: int = Query(...),
    under_exchange_segment: str = Query(...)
):
    try:
        return ok(dhan.expiry_list(under_security_id=under_security_id,
                                   under_exchange_segment=under_exchange_segment))
    except Exception as e:
        return fail("expiry list failed", data=str(e))

@app.post("/optionchain")
def optionchain(body: OptionChainBody = Body(...)):
    try:
        return ok(dhan.option_chain(
            under_security_id=body.under_security_id,
            under_exchange_segment=body.under_exchange_segment,
            expiry=body.expiry
        ))
    except Exception as e:
        return fail("option chain failed", data=str(e))

# -----------------------------------------------------------------------------
# Charts
# -----------------------------------------------------------------------------
@app.get("/charts/intraday")
def charts_intraday(
    security_id: int = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: str = Query(...),
):
    try:
        return ok(dhan.intraday_minute_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type
        ))
    except Exception as e:
        return fail("intraday data failed", data=str(e))

@app.get("/charts/historical")
def charts_historical(
    security_id: int = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: str = Query(...),
    expiry_code: int = Query(0),
    from_date: str = Query(..., description="YYYY-MM-DD"),
    to_date: str = Query(..., description="YYYY-MM-DD"),
):
    try:
        return ok(dhan.historical_daily_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            expiry_code=expiry_code,
            from_date=from_date,
            to_date=to_date
        ))
    except Exception as e:
        return fail("historical data failed", data=str(e))

# -----------------------------------------------------------------------------
# Aggregate: Option Analysis (data only)
# -----------------------------------------------------------------------------
@app.get("/option_analysis")
def option_analysis(
    under_security_id: int = Query(13, description="NIFTY"),
    under_exchange_segment: str = Query("IDX_I"),
    equity_security_id: int = Query(1333, description="HDFC Bank eq for demo"),
    equity_exchange_segment: str = Query("NSE")
):
    try:
        # 1) Expiries
        expiries = dhan.expiry_list(under_security_id=under_security_id,
                                    under_exchange_segment=under_exchange_segment)

        # pick first expiry if list available
        expiry_pick = None
        try:
            expiry_pick = (expiries or {}).get("data", {}).get("data", [None])[0]
        except Exception:
            expiry_pick = None

        # 2) Option chain
        chain = {}
        if expiry_pick:
            chain = dhan.option_chain(
                under_security_id=under_security_id,
                under_exchange_segment=under_exchange_segment,
                expiry=expiry_pick
            )

        # 3) Market snapshots for an example equity
        key = _quote_key(equity_exchange_segment)
        payload = { key: [int(equity_security_id)] }
        market = {
            "ltp": dhan.ticker_data(securities=payload),
            "ohlc": dhan.ohlc_data(securities=payload),
            "quote": dhan.quote_data(securities=payload)
        }

        # 4) Portfolio snapshot
        portfolio = {
            "orders": dhan.get_order_list(),
            "positions": dhan.get_positions(),
            "holdings": dhan.get_holdings(),
            "funds": dhan.get_fund_limits()
        }

        return ok({
            "params": {
                "under_security_id": under_security_id,
                "under_exchange_segment": under_exchange_segment,
                "used_expiry": expiry_pick
            },
            "expiry_list": expiries,
            "option_chain": chain,
            "market": market,
            "portfolio": portfolio
        })
    except Exception as e:
        return fail("option_analysis failed", data=str(e))

# -----------------------------------------------------------------------------
# AI endpoints
# -----------------------------------------------------------------------------
class AIMarketViewBody(BaseModel):
    underlier: str = Field("BANKNIFTY", description="Display name only")
    context: Dict[str, Any] = Field(default_factory=dict, description="optional signals like pcr, iv, oi_buildup")

class AIStrategyBody(BaseModel):
    outlook: str = Field("neutral", description="bullish|slightly_bullish|neutral|slightly_bearish|bearish")
    risk: str = Field("moderate", description="low|moderate|high")
    capital: int = 50000
    expiry: Optional[str] = None
    notes: Optional[str] = None

class AIPayoffLeg(BaseModel):
    side: str            # BUY or SELL
    opt_type: str        # CE or PE
    strike: float
    premium: float
    qty: int = 1

class AIPayoffBody(BaseModel):
    legs: List[AIPayoffLeg]
    price_grid: List[float] = Field(default_factory=lambda: [])

def _ai_call(prompt: str) -> str:
    """
    Calls OpenAI if configured, else returns a simple rule-based response.
    """
    if _openai_client:
        try:
            resp = _openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an options strategist for Indian markets. Keep outputs concise, structured, and actionable."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"(AI error fallback) {str(e)}"

    # fallback (no OpenAI)
    return "AI is not enabled; set OPENAI_API_KEY to get model-based insights. Meanwhile: focus on liquid strikes near ATM, prefer credit strategies when IV is high, define exits via max loss or IV crush."

@app.post("/ai/marketview")
def ai_marketview(body: AIMarketViewBody):
    try:
        ctx = body.context or {}
        quick = {
            "pcr": ctx.get("pcr"),
            "avg_iv": ctx.get("avg_iv"),
            "max_pain": ctx.get("max_pain"),
            "oi_trend": ctx.get("oi_trend")
        }
        prompt = (f"Underlier: {body.underlier}\n"
                  f"Signals: {quick}\n"
                  f"Task: Give a short directional view (bullish/neutral/bearish), "
                  f"key levels, and 1-2 risks to watch for the next session.")
        return ok({"summary": _ai_call(prompt)})
    except Exception as e:
        return fail("ai marketview failed", data=str(e))

@app.post("/ai/strategy")
def ai_strategy(body: AIStrategyBody):
    try:
        prompt = (f"Design an options strategy for Indian F&O with:\n"
                  f"- Outlook: {body.outlook}\n- Risk: {body.risk}\n- Capital: ₹{body.capital}\n"
                  f"- Expiry preference: {body.expiry or 'nearest weekly'}\n"
                  f"- Notes: {body.notes or '-'}\n"
                  f"Return: name, legs (sell/buy CE/PE with strikes/premiums placeholders), "
                  f"max profit/loss, break-evens, PoP%, and key management rules.")
        text = _ai_call(prompt)
        return ok({"recommendation": text})
    except Exception as e:
        return fail("ai strategy failed", data=str(e))

@app.post("/ai/payoff")
def ai_payoff(body: AIPayoffBody):
    try:
        # Simple deterministic payoff calc at expiry (ignore greeks; premium as given)
        grid = body.price_grid or []
        if not grid:
            # auto grid from legs
            strikes = [l.strike for l in body.legs]
            if strikes:
                lo = max(0, min(strikes) - 500)
                hi = max(strikes) + 500
                grid = list(range(int(lo), int(hi)+1, 100))
            else:
                grid = list(range(30000, 50001, 100))

        def leg_payoff(spot: float, leg: AIPayoffLeg) -> float:
            # payoff at expiry per 1 qty
            if leg.opt_type.upper() == "CE":
                intrinsic = max(0.0, spot - leg.strike)
            else:
                intrinsic = max(0.0, leg.strike - spot)
            # buy = pay premium; sell = receive premium
            sign = 1 if leg.side.upper() == "BUY" else -1
            # Profit = sign*(intrinsic - premium)
            per_unit = sign * (intrinsic - leg.premium)
            return per_unit * leg.qty

        series = []
        for s in grid:
            total = sum(leg_payoff(s, lg) for lg in body.legs)
            series.append({"spot": s, "pnl": round(total, 2)})

        # rough metrics
        pnl_vals = [p["pnl"] for p in series]
        max_profit = max(pnl_vals)
        max_loss = min(pnl_vals)
        # breakevens: spot where pnl crosses 0 (linear scan)
        bes = []
        for i in range(1, len(series)):
            p0, p1 = series[i-1]["pnl"], series[i]["pnl"]
            if (p0 == 0) or (p1 == 0) or (p0 < 0 and p1 > 0) or (p0 > 0 and p1 < 0):
                bes.append(series[i]["spot"])
        result = {
            "grid": series,
            "summary": {
                "max_profit": max_profit,
                "max_loss": max_loss,
                "breakevens_estimated": sorted(list(set(bes)))
            }
        }
        return ok(result)
    except Exception as e:
        return fail("ai payoff failed", data=str(e))

# -----------------------------------------------------------------------------
# Self-test
# -----------------------------------------------------------------------------
@app.get("/__selftest")
def __selftest(request: Request):
    base = str(request.base_url).rstrip("/")
    samples = {
        "root": "/",
        "health": "/health",
        "broker_status": "/broker_status",
        "orders": "/orders",
        "positions": "/positions",
        "holdings": "/holdings",
        "funds": "/funds",
        "expiryllist_sample": "/optionchain/expirylist?under_security_id=13&under_exchange_segment=IDX_I",
        "intraday_sample": "/charts/intraday?security_id=1333&exchange_segment=NSE&instrument_type=EQUITY",
        "historical_sample": "/charts/historical?security_id=1333&exchange_segment=NSE&instrument_type=EQUITY&expiry_code=0&from_date=2024-01-01&to_date=2024-02-01",
        "option_analysis": "/option_analysis",
        "ai_marketview": "/ai/marketview",
        "ai_strategy": "/ai/strategy",
        "ai_payoff": "/ai/payoff"
    }
    return {
        "status": {
            "mode": MODE, "env": ENV_NOTE,
            "token_present": bool(ACCESS_TOKEN),
            "client_id_present": bool(CLIENT_ID),
            "ai_enabled": bool(_openai_client),
            "ai_model": OPENAI_MODEL if _openai_client else None,
            "base_url_note": "MODE=LIVE uses LIVE_* keys; otherwise SANDBOX",
        },
        "samples": {k: f"{base}{v}" for k, v in samples.items()},
        "now": datetime.now(timezone.utc).isoformat()
    }
