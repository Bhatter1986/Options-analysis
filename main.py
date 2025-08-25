# main.py
import os
import time
import json
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from functools import lru_cache

# --- ENV ---------------------------------------------------------------------
from dotenv import load_dotenv
load_dotenv()

# DhanHQ SDK (v2.0.2)
try:
    from dhanhq import dhanhq, marketfeed
    DHAN_SDK_OK = True
except Exception as e:
    DHAN_SDK_OK = False

# OpenAI (v1)
try:
    import openai
    OPENAI_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
    if OPENAI_KEY:
        openai.api_key = OPENAI_KEY
    OPENAI_OK = bool(OPENAI_KEY)
except Exception:
    OPENAI_OK = False

APP_MODE = os.getenv("MODE", "LIVE").upper()
CLIENT_ID = os.getenv("DHAN_CLIENT_ID", os.getenv("CLIENT_ID"))
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", os.getenv("ACCESS_TOKEN"))

# --- APP ---------------------------------------------------------------------
app = FastAPI(
    title="Options-analysis (Dhan v2 + AI)",
    version="2.0",
    swagger_ui_parameters={"docExpansion": "list"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# --- Helpers -----------------------------------------------------------------
def ok(data: Any) -> Dict[str, Any]:
    return {"status": "success", "data": data}

def fail(msg: str, data: Any = None) -> Dict[str, Any]:
    return {"status": "failure", "data": {"status": "failed", "remarks": {"814": msg}, "data": data}}

def _bool(x): return True if x in (True, "1", 1, "true", "TRUE", "yes") else False

# --- Dhan Client -------------------------------------------------------------
dhan = None
if DHAN_SDK_OK and CLIENT_ID and ACCESS_TOKEN:
    try:
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
    except Exception as e:
        dhan = None

# --- Instrument Resolver (auto symbol -> underlying) -------------------------
_INSTR_CACHE = {"rows": None, "at": 0.0, "ttl": 300.0}  # 5 minutes

INDEX_FALLBACK = {
    # Fast path (आप चाहें तो BANKNIFTY/FINNIFTY सही IDs बाद में fill कर दें)
    "NIFTY": ("13", "IDX_I"),
    # "BANKNIFTY": ("25", "IDX_I"),
    # "FINNIFTY": ("???", "IDX_I"),
}

def _clean_sym(s: str) -> str:
    s = (s or "").strip().upper()
    aliases = {
        "NIFTY 50": "NIFTY",
        "BANK NIFTY": "BANKNIFTY",
        "NIFTY BANK": "BANKNIFTY",
        "FIN NIFTY": "FINNIFTY",
        "MIDCAP NIFTY": "MIDCPNIFTY",
    }
    return aliases.get(s, s)

def _load_instruments(force: bool = False) -> List[Dict[str, Any]]:
    now = time.time()
    if (not force) and _INSTR_CACHE["rows"] and (now - _INSTR_CACHE["at"] < _INSTR_CACHE["ttl"]):
        return _INSTR_CACHE["rows"]

    if not dhan:
        # SDK नहीं है/initialise नहीं हुआ — सिर्फ fallback से काम चलेगा
        _INSTR_CACHE["rows"] = []
        _INSTR_CACHE["at"] = now
        return _INSTR_CACHE["rows"]

    # SDK से compact list
    try:
        data = dhan.fetch_security_list("compact")
    except Exception:
        data = None

    rows: List[Dict[str, Any]] = []
    if hasattr(data, "to_dict"):  # pandas DF
        rows = data.to_dict(orient="records")  # type: ignore
    elif isinstance(data, list):
        rows = [dict(r) for r in data]
    elif data is None:
        rows = []
    else:
        try:
            rows = list(data)  # best effort
        except Exception:
            rows = []

    # normalize: lower keys
    norm = []
    for r in rows:
        try:
            norm.append({str(k).lower(): v for k, v in dict(r).items()})
        except Exception:
            continue

    _INSTR_CACHE["rows"] = norm
    _INSTR_CACHE["at"] = now
    return norm

def _pick(d: Dict[str, Any], keys: List[str]):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None

def resolve_underlying(symbol: str):
    """
    Returns (under_security_id, under_exchange_segment) using SDK instrument list.
    Falls back to INDEX_FALLBACK for fast known indices.
    """
    sym = _clean_sym(symbol)
    if sym in INDEX_FALLBACK:
        return INDEX_FALLBACK[sym]

    instruments = _load_instruments()
    C_SYM = ["symbol", "tradingsymbol", "name", "security_symbol"]
    C_SEG = ["exchange_segment", "segment"]
    C_ID  = ["security_id", "id", "instrument_token"]

    preferred_segments = ["IDX_I"] if sym in {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"} else []

    matches = []
    for row in instruments:
        rsym = str(_pick(row, C_SYM) or "").strip().upper()
        rseg = str(_pick(row, C_SEG) or "").strip().upper()
        rid  = _pick(row, C_ID)
        if rsym == sym:
            matches.append((str(rid) if rid is not None else None, rseg, row))

    if not matches:
        for row in instruments:
            rsym = str(_pick(row, C_SYM) or "").strip().upper()
            if sym and sym in rsym:
                rseg = str(_pick(row, C_SEG) or "").strip().upper()
                rid  = _pick(row, C_ID)
                matches.append((str(rid) if rid is not None else None, rseg, row))

    if not matches:
        raise ValueError(f"Symbol '{symbol}' not found in instrument list. Pass under_security_id & under_exchange_segment.")

    if preferred_segments:
        pr = [m for m in matches if m[1] in preferred_segments and m[0]]
        if pr:
            return pr[0][0], pr[0][1]

    rid, rseg, _ = next((m for m in matches if m[0] and m[1]), matches[0])
    if not rid or not rseg:
        raise ValueError(f"Instrument mapping incomplete for '{symbol}'.")
    return rid, rseg

# --- Models (AI) -------------------------------------------------------------
class AiMarketIn(BaseModel):
    symbol: Optional[str] = "NIFTY"
    horizon: Optional[str] = "intraday"
    bias: Optional[str] = "neutral"

class AiStrategyIn(BaseModel):
    under_security_id: Optional[str] = None
    under_exchange_segment: Optional[str] = None
    bias: Optional[str] = "neutral"
    risk: Optional[str] = "moderate"
    capital: Optional[float] = 50000
    constraints: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    symbol: Optional[str] = None
    expiry: Optional[str] = None

class AiPayoffIn(BaseModel):
    legs: List[Dict[str, Any]]
    spot: float

# --- Root/Health -------------------------------------------------------------
@app.get("/", summary="Root")
def root():
    return ok({"message": "Options-analysis (Dhan v2 + AI) up", "docs": "/docs"})

@app.get("/health", summary="Health")
def health():
    return ok({"live": True})

@app.get("/broker_status", summary="Broker Status")
def broker_status():
    return ok({
        "mode": APP_MODE,
        "env": True,
        "token_present": bool(ACCESS_TOKEN),
        "client_id_present": bool(CLIENT_ID),
        "openai_present": OPENAI_OK,
    })

@app.get("/__selftest", summary="Selftest")
def selftest():
    data = {
        "status": {
            "env": True,
            "mode": APP_MODE,
            "token_present": bool(ACCESS_TOKEN),
            "client_id_present": bool(CLIENT_ID),
            "openai_present": OPENAI_OK,
        }
    }
    # Quick funds check if possible
    try:
        if dhan:
            f = dhan.get_fund_limits()
            data["sample"] = {"funds_ok": True}
        else:
            data["sample"] = {"funds_ok": False}
    except Exception:
        data["sample"] = {"funds_ok": False}
    return ok(data)

# --- Option APIs -------------------------------------------------------------
@app.get("/option/expirylist", summary="Option Expirylist")
def option_expirylist(
    symbol: Optional[str] = Query(None, description="NIFTY/BANKNIFTY/FINNIFTY or stock"),
    under_security_id: Optional[str] = Query(None),
    under_exchange_segment: Optional[str] = Query(None),
):
    try:
        if symbol and not (under_security_id and under_exchange_segment):
            under_security_id, under_exchange_segment = resolve_underlying(symbol)

        if not (under_security_id and under_exchange_segment):
            return fail("Provide either symbol OR under_security_id + under_exchange_segment")

        if not dhan:
            return fail("Dhan SDK/client not initialised")

        res = dhan.expiry_list(
            under_security_id=under_security_id,
            under_exchange_segment=under_exchange_segment
        )
        return ok(res)
    except Exception as e:
        return fail(str(e))

@app.get("/option/chain", summary="Option Chain")
def option_chain(
    symbol: Optional[str] = Query(None),
    under_security_id: Optional[str] = Query(None),
    under_exchange_segment: Optional[str] = Query(None),
    expiry: Optional[str] = Query(None, description="yyyy-mm-dd"),
):
    try:
        if symbol and not (under_security_id and under_exchange_segment):
            under_security_id, under_exchange_segment = resolve_underlying(symbol)

        if not (under_security_id and under_exchange_segment):
            return fail("Provide either symbol OR under_security_id + under_exchange_segment")

        if not dhan:
            return fail("Dhan SDK/client not initialised")

        args = {
            "under_security_id": under_security_id,
            "under_exchange_segment": under_exchange_segment
        }
        if expiry:
            args["expiry"] = expiry

        res = dhan.option_chain(**args)
        return ok(res)
    except Exception as e:
        return fail(str(e))

# --- Quotes/Charts ------------------------------------------------------------
@app.get("/market/quote", summary="Market Quote")
def market_quote(
    security_id: str = Query(...),
    exchange_segment: str = Query(...),
    mode: str = Query("quote")  # ticker/quote/full
):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.get_quote(
            security_id=security_id,
            exchange_segment=exchange_segment,
            type=mode
        )
        return ok(res)
    except Exception as e:
        return fail(str(e))

@app.get("/charts/intraday", summary="Charts Intraday")
def charts_intraday(
    security_id: str = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: str = Query(...),   # Equity/Futures/Options/Index etc. as per SDK
):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.intraday_minute_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type
        )
        return ok(res)
    except Exception as e:
        return fail(str(e))

@app.get("/charts/historical", summary="Charts Historical")
def charts_historical(
    security_id: str = Query(...),
    exchange_segment: str = Query(...),
    instrument_type: str = Query(...),
    expiry_code: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.historical_daily_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            expiry_code=expiry_code,
            from_date=from_date,
            to_date=to_date,
        )
        return ok(res)
    except Exception as e:
        return fail(str(e))

# --- Orders -------------------------------------------------------------------
@app.post("/orders/place", summary="Orders Place")
def orders_place(body: Dict[str, Any] = Body(...)):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.place_order(**body)
        return ok(res)
    except Exception as e:
        return fail(str(e), data=body)

@app.post("/orders/modify", summary="Orders Modify")
def orders_modify(body: Dict[str, Any] = Body(...)):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.modify_order(**body)
        return ok(res)
    except Exception as e:
        return fail(str(e), data=body)

@app.post("/orders/cancel", summary="Orders Cancel")
def orders_cancel(body: Dict[str, Any] = Body(...)):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.cancel_order(**body)
        return ok(res)
    except Exception as e:
        return fail(str(e), data=body)

@app.get("/orders/{order_id}", summary="Orders Get")
def orders_get(order_id: str):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.get_order_by_id(order_id)
        return ok(res)
    except Exception as e:
        return fail(str(e))

@app.get("/tradebook/{order_id}", summary="Trade Book")
def tradebook(order_id: str):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.get_trade_book(order_id)
        return ok(res)
    except Exception as e:
        return fail(str(e))

@app.get("/tradehistory", summary="Trade History")
def tradehistory(from_date: Optional[str] = None, to_date: Optional[str] = None, page_number: int = 0):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.get_trade_history(from_date, to_date, page_number)
        return ok(res)
    except Exception as e:
        return fail(str(e))

# --- Portfolio/Funds ----------------------------------------------------------
@app.get("/positions", summary="Positions")
def positions():
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.get_positions()
        return ok(res)
    except Exception as e:
        return fail(str(e))

@app.get("/holdings", summary="Holdings")
def holdings():
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.get_holdings()
        return ok(res)
    except Exception as e:
        return fail(str(e))

@app.get("/funds", summary="Funds")
def funds():
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.get_fund_limits()
        return ok(res)
    except Exception as e:
        return fail(str(e))

# --- Forever Orders -----------------------------------------------------------
@app.post("/forever/place", summary="Forever Place")
def forever_place(body: Dict[str, Any] = Body(...)):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.place_forever(**body)
        return ok(res)
    except Exception as e:
        return fail(str(e), data=body)

@app.post("/forever/modify", summary="Forever Modify")
def forever_modify(body: Dict[str, Any] = Body(...)):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        # Some SDKs have modify_forever; if not, return explicit message
        if hasattr(dhan, "modify_forever"):
            res = dhan.modify_forever(**body)  # type: ignore
        else:
            raise RuntimeError("modify_forever not available in current SDK")
        return ok(res)
    except Exception as e:
        return fail(str(e), data=body)

@app.post("/forever/cancel", summary="Forever Cancel")
def forever_cancel(body: Dict[str, Any] = Body(...)):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.cancel_forever(**body)
        return ok(res)
    except Exception as e:
        return fail(str(e), data=body)

# --- eDIS ---------------------------------------------------------------------
@app.post("/edis/generate_tpin", summary="Edis Generate Tpin")
def edis_generate_tpin():
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.generate_tpin()
        return ok(res)
    except Exception as e:
        return fail(str(e))

@app.post("/edis/open_browser_for_tpin", summary="Edis Open Browser For Tpin")
def edis_open_browser_for_tpin(isin: str = Body(...), qty: int = Body(...), exchange: str = Body("NSE")):
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.open_browser_for_tpin(isin=isin, qty=qty, exchange=exchange)
        return ok(res)
    except Exception as e:
        return fail(str(e))

@app.get("/edis/inquiry", summary="Edis Inquiry")
def edis_inquiry():
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        res = dhan.edis_inquiry()
        return ok(res)
    except Exception as e:
        return fail(str(e))

# --- Marketfeed (ping/last placeholders) -------------------------------------
_LAST_MF = {"at": None, "payload": None}

@app.post("/marketfeed/ping", summary="Marketfeed Ping")
def marketfeed_ping(payload: Dict[str, Any] = Body(...)):
    # यहां आप websocket subscribe client जोड़ सकते हैं; अभी के लिए payload store
    _LAST_MF["at"] = time.time()
    _LAST_MF["payload"] = payload
    return ok({"stored": True})

@app.get("/marketfeed/last", summary="Marketfeed Last")
def marketfeed_last():
    return ok(_LAST_MF)

# --- Raw/Exec (advanced) ------------------------------------------------------
@app.post("/dhan/raw", summary="Dhanhq Raw")
def dhanhq_raw(body: Dict[str, Any] = Body(...)):
    """
    body = {"method":"expiry_list","kwargs":{"under_security_id":"13","under_exchange_segment":"IDX_I"}}
    """
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        m = getattr(dhan, body.get("method"))
        res = m(**(body.get("kwargs") or {}))
        return ok(res)
    except Exception as e:
        return fail(str(e), data=body)

@app.post("/dhan/exec", summary="Dhanhq Exec")
def dhanhq_exec(code: str = Body(..., embed=True)):
    """
    Execute small snippets that return 'res' variable.
    """
    try:
        if not dhan:
            return fail("Dhan SDK/client not initialised")
        # Very restricted exec environment
        loc = {"dhan": dhan, "res": None}
        exec(code, {}, loc)
        return ok(loc.get("res"))
    except Exception as e:
        return fail(str(e))

# --- AI Endpoints -------------------------------------------------------------
def _chat(model: str, system: str, user: str) -> str:
    if not OPENAI_OK:
        raise RuntimeError("OpenAI key missing")
    # Using legacy Completion-like messages with Chat Completions
    from openai import OpenAI
    client = OpenAI(api_key=openai.api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""

AI_MODEL_MARKET  = os.getenv("AI_MODEL_MARKET",  "gpt-4o-mini")
AI_MODEL_STRATEGY= os.getenv("AI_MODEL_STRATEGY","gpt-4o-mini")
AI_MODEL_PAYOFF  = os.getenv("AI_MODEL_PAYOFF",  "gpt-4o-mini")

@app.post("/ai/marketview", summary="Ai Marketview")
def ai_marketview(body: AiMarketIn):
    try:
        sys = ("You are an options market analyst for Indian markets. "
               "Give crisp view (3-6 bullets): direction, key levels, IV/volatility, OI hints. "
               "No financial advice disclaimer needed.")
        user = json.dumps(body.dict(exclude_none=True))
        txt = _chat(AI_MODEL_MARKET, sys, f"Market snapshot request: {user}")
        return ok({"ai_text": txt})
    except Exception as e:
        return fail(str(e))

@app.post("/ai/strategy", summary="Ai Strategy")
def ai_strategy(body: AiStrategyIn):
    try:
        # Auto map if symbol given
        if body.symbol and not (body.under_security_id and body.under_exchange_segment):
            uid, seg = resolve_underlying(body.symbol)
            body.under_security_id = uid
            body.under_exchange_segment = seg

        sys = ("You are an options strategist. Propose 1-2 strategies with entry, SL, target, "
               "max loss, Greeks idea, rationale; risk-aware; "
               "present in neat bullet JSON.")
        user = json.dumps(body.dict(exclude_none=True))
        txt = _chat(AI_MODEL_STRATEGY, sys, f"Inputs JSON: {user}")
        return ok({"ai_text": txt})
    except Exception as e:
        return fail(str(e))

@app.post("/ai/payoff", summary="Ai Payoff")
def ai_payoff(body: AiPayoffIn):
    try:
        sys = ("You compute option strategy payoff and summarize P&L profile, BE points, "
               "greeks intuition, and risk notes for retail trader.")
        user = json.dumps(body.dict(exclude_none=True))
        txt = _chat(AI_MODEL_PAYOFF, sys, f"Compute payoff for: {user}")
        return ok({"ai_text": txt})
    except Exception as e:
        return fail(str(e))

@app.post("/ai/test", summary="Ai Test")
def ai_test(prompt: str = Body("Say hello", embed=True)):
    try:
        sys = "Be concise."
        txt = _chat(AI_MODEL_MARKET, sys, prompt)
        return ok({"ai_text": txt})
    except Exception as e:
        return fail(str(e))


# --- Uvicorn entry (local dev) -----------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
