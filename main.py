import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import FastAPI, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Dhan SDK
from dhanhq import dhanhq as DhanHQ

# === OpenAI (for AI recommendations) ===
from openai import OpenAI

app = FastAPI(title="Options-analysis (Dhan v2)")


# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ---------- ENV / MODE ----------
def _pick(*keys: str) -> Optional[str]:
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return None

MODE = os.getenv("MODE", "TEST").upper()          # LIVE or TEST(SANDBOX)
ENV_NOTE = "LIVE" if MODE == "LIVE" else "SANDBOX"

if MODE == "LIVE":
    CLIENT_ID = _pick("DHAN_LIVE_CLIENT_ID", "DHAN_CLIENT_ID")
    ACCESS_TOKEN = _pick("DHAN_LIVE_ACCESS_TOKEN", "DHAN_ACCESS_TOKEN")
else:
    CLIENT_ID = _pick("DHAN_SANDBOX_CLIENT_ID", "DHAN_CLIENT_ID")
    ACCESS_TOKEN = _pick("DHAN_SANDBOX_ACCESS_TOKEN", "DHAN_ACCESS_TOKEN")

# One Dhan client for entire app
dhan = DhanHQ(CLIENT_ID or "", ACCESS_TOKEN or "")

# OpenAI client (optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_ai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ---------- Helpers ----------
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


# ---------- Root ----------
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
            "/option_analysis", "/ai/recommend",
            "/__selftest"
        ],
    }


# ---------- Health / Status ----------
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
        "openai_present": bool(OPENAI_API_KEY),
    }


# ---------- Portfolio ----------
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


# ---------- Market Quote (snapshot REST) ----------
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


# ---------- Option Chain ----------
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


# ---------- Charts ----------
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


# ---------- Aggregate: Option Analysis (data only) ----------
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

        expiry_pick = None
        try:
            expiry_pick = (expiries or {}).get("data", {}).get("data", [None])[0]
        except Exception:
            expiry_pick = None

        # 2) Option chain (first expiry if available)
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


# ---------- Utilities for AI ----------
def _to_float(x):
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).replace(",", "")
        return float(s)
    except Exception:
        return None

def _pick_field(d: dict, candidates=("oi","open_interest","openInterest")):
    if not isinstance(d, dict): return None
    for k in candidates:
        if k in d: return d[k]
    return None

def _extract_rows_from_chain(chain_json: dict, limit: int = 20):
    """
    Normalize Dhan option_chain JSON -> rows:
      {strike, CE:{oi,ltp,iv}, PE:{oi,ltp,iv}}
    Works with CE/PE or ce/pe keys. Keeps a slice (~ATM) to keep prompt small.
    """
    rows = []
    data = None
    try:
        data = chain_json.get("data", {}).get("data")
        if not isinstance(data, list):
            data = chain_json.get("data")
    except Exception:
        pass

    if not isinstance(data, list):
        return rows

    for row in data:
        strike = _to_float(row.get("strikePrice") or row.get("strike") or row.get("sp"))
        ce = row.get("CE") or row.get("ce") or {}
        pe = row.get("PE") or row.get("pe") or {}
        if strike is None:
            continue

        ce_oi = _to_float(_pick_field(ce))
        pe_oi = _to_float(_pick_field(pe))
        ce_ltp = _to_float(ce.get("ltp") or ce.get("last_price") or ce.get("lastPrice"))
        pe_ltp = _to_float(pe.get("ltp") or pe.get("last_price") or pe.get("lastPrice"))
        ce_iv  = _to_float(ce.get("iv") or ce.get("implied_volatility") or ce.get("impliedVolatility"))
        pe_iv  = _to_float(pe.get("iv") or pe.get("implied_volatility") or pe.get("impliedVolatility"))

        rows.append({
            "strike": strike,
            "CE": {"oi": ce_oi, "ltp": ce_ltp, "iv": ce_iv},
            "PE": {"oi": pe_oi, "ltp": pe_ltp, "iv": pe_iv},
        })

    rows.sort(key=lambda r: r["strike"])
    if len(rows) > limit:
        mid = len(rows)//2
        half = limit//2
        rows = rows[max(0, mid-half): mid+half]
    return rows

def _quick_metrics(rows):
    tot_ce = sum([(r["CE"]["oi"] or 0) for r in rows]) or 0.0
    tot_pe = sum([(r["PE"]["oi"] or 0) for r in rows]) or 0.0
    pcr = (tot_pe / tot_ce) if tot_ce else None
    top_call = max(rows, key=lambda r: (r["CE"]["oi"] or 0))["strike"] if rows else None
    top_put  = max(rows, key=lambda r: (r["PE"]["oi"] or 0))["strike"] if rows else None
    return {"pcr": pcr, "top_call_oi_strike": top_call, "top_put_oi_strike": top_put}


# ---------- AI: Recommend ----------
class AIReq(BaseModel):
    under_security_id: int = 13
    under_exchange_segment: str = "IDX_I"  # index segment
    expiry: str
    spot: float | None = None
    symbol: str | None = None

@app.post("/ai/recommend")
def ai_recommend(body: AIReq):
    """
    Uses Dhan option_chain + OpenAI to return a single structured recommendation.
    Fallback (no OPENAI_API_KEY): rule-based JSON using PCR & OI walls.
    """
    try:
        # 1) fetch chain
        chain = dhan.option_chain(
            under_security_id=body.under_security_id,
            under_exchange_segment=body.under_exchange_segment,
            expiry=body.expiry
        )
        rows = _extract_rows_from_chain(chain, limit=20)
        meta = _quick_metrics(rows)

        # If no OpenAI key -> fallback JSON
        if _ai is None:
            suggestion = {
                "strategy": "Neutral Credit Spread",
                "rationale": "Fallback (no OPENAI_API_KEY). Using PCR & OI walls.",
                "metrics": meta,
                "key_levels": {
                    "put_oi_wall": meta["top_put_oi_strike"],
                    "call_oi_wall": meta["top_call_oi_strike"]
                },
                "positions": [
                    f"Sell {int(meta['top_call_oi_strike'] or 0)} CE",
                    f"Sell {int(meta['top_put_oi_strike'] or 0)} PE"
                ],
                "risk": {"max_profit": None, "max_loss": None, "pop": None}
            }
            return ok(suggestion, "fallback")

        # 2) build prompt + call OpenAI (JSON output)
        symbol = body.symbol or ("NIFTY" if body.under_security_id == 13 else "SYMBOL")
        sys = (
            "You are an options strategist. Propose ONE risk-defined, liquid options "
            "strategy (spreads/defined-risk) for the given symbol & expiry based on "
            "PCR and OI walls. Return STRICT JSON with fields: "
            "strategy, rationale, positions[], key_levels{support,resistance}, "
            "risk{max_profit,max_loss,pop}."
        )
        user = {
            "symbol": symbol, "expiry": body.expiry, "spot": body.spot,
            "metrics": meta, "sample_rows": rows
        }

        resp = _ai.responses.create(
            model="gpt-5.1-mini",
            input=[
                {"role":"system","content":sys},
                {"role":"user","content":f"{user}"}
            ],
            response_format={"type": "json_object"}
        )

        # parse JSON
        content = resp.output_text
        import json
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {"raw_text": content}
        data.setdefault("metrics", meta)

        return ok(data)
    except Exception as e:
        return fail("ai_recommend failed", data=str(e))


# ---------- Self-test ----------
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
        "ai_recommend_sample": "/ai/recommend",
        "option_analysis": "/option_analysis"
    }
    return {
        "status": {
            "mode": MODE, "env": ENV_NOTE,
            "token_present": bool(ACCESS_TOKEN),
            "client_id_present": bool(CLIENT_ID),
            "openai_present": bool(OPENAI_API_KEY),
            "base_url_note": "MODE=LIVE uses LIVE_… keys; otherwise SANDBOX",
        },
        "samples": {k: f"{base}{v}" for k, v in samples.items()},
        "now": datetime.now(timezone.utc).isoformat()
    }
