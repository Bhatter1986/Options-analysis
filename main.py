import os, math, statistics
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

from fastapi import FastAPI, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Dhan SDK
from dhanhq import dhanhq as DhanHQ

app = FastAPI(title="Options-analysis (Dhan v2 + AI)")

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

# ---------- Generic Helpers ----------
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
    if s in ("NSE_INDEX", "IDX_I"): return "IDX_I"
    return s

def dget(obj, dotted: str, default=None):
    """Safely get nested keys using dotted path (e.g. 'data.data')"""
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur

def first_num(*vals, default=None):
    for v in vals:
        try:
            if v is None: 
                continue
            if isinstance(v, (int, float)): 
                return float(v)
            # str -> float
            return float(str(v).replace(",", "").strip())
        except Exception:
            continue
    return default

def median_gap(values: List[float], default: float = 50.0) -> float:
    if not values or len(values) < 2: 
        return default
    gaps = sorted(abs(values[i+1]-values[i]) for i in range(len(values)-1))
    if not gaps:
        return default
    return statistics.median(gaps)

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
            "/option_analysis",
            # AI
            "/ai/marketview", "/ai/strategy", "/ai/payoff", "/ai/test",
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

# =============== AI GURU: Chain Normalization + Metrics =====================

def _normalize_chain(chain_resp) -> List[Dict[str, float]]:
    """
    Returns list of rows:
      {strike, ce_oi, pe_oi, ce_ltp, pe_ltp, ce_iv, pe_iv}
    Extremely defensive to handle schema variance.
    """
    rows = dget(chain_resp, "data.data", [])
    if isinstance(rows, dict) and "data" in rows:
        rows = rows.get("data")  # some variants

    if not isinstance(rows, list):
        # fallback: try 'records' or 'optionChain'
        rows = dget(chain_resp, "data.records", []) or dget(chain_resp, "data.optionChain", []) or []

    out = []

    def pick(obj, keys: List[str], default=None):
        for k in keys:
            if k in obj:
                return obj[k]
        # try case-insensitive
        lower = {str(k).lower(): v for k, v in obj.items()} if isinstance(obj, dict) else {}
        for k in keys:
            if lower.get(k.lower()) is not None:
                return lower.get(k.lower())
        return default

    for r in rows or []:
        if not isinstance(r, dict):
            continue

        # strike detect
        strike = first_num(
            r.get("strike"), r.get("strike_price"), r.get("strikePrice"),
            r.get("strikePriceValue"), r.get("strikeprice"), pick(r, ["Strike","STRIKE"]),
        )

        # possible nested dicts for CE/PE
        ce = pick(r, ["CE", "CALL", "Call", "call", "ce"], default={}) or {}
        pe = pick(r, ["PE", "PUT", "Put", "put", "pe"], default={}) or {}

        ce_oi = first_num(
            pick(ce, ["oi","open_interest","openInterest","openinterest"]),
            r.get("ce_oi"), r.get("call_oi")
        )
        pe_oi = first_num(
            pick(pe, ["oi","open_interest","openInterest","openinterest"]),
            r.get("pe_oi"), r.get("put_oi")
        )

        ce_ltp = first_num(
            pick(ce, ["ltp","last_price","lastPrice","closePrice","Close"]),
            r.get("ce_ltp"), r.get("call_ltp")
        )
        pe_ltp = first_num(
            pick(pe, ["ltp","last_price","lastPrice","closePrice","Close"]),
            r.get("pe_ltp"), r.get("put_ltp")
        )

        ce_iv = first_num(
            pick(ce, ["iv","impliedVolatility","implied_volatility"]),
            r.get("ce_iv"), r.get("call_iv")
        )
        pe_iv = first_num(
            pick(pe, ["iv","impliedVolatility","implied_volatility"]),
            r.get("pe_iv"), r.get("put_iv")
        )

        if strike is None:
            # last fallback: try any numeric value named 'strike*'
            for k,v in (r.items()):
                if "strike" in str(k).lower():
                    strike = first_num(v)
                    break

        if strike is None:
            # cannot use this row
            continue

        out.append({
            "strike": strike,
            "ce_oi": ce_oi or 0.0,
            "pe_oi": pe_oi or 0.0,
            "ce_ltp": ce_ltp or 0.0,
            "pe_ltp": pe_ltp or 0.0,
            "ce_iv": ce_iv or 0.0,
            "pe_iv": pe_iv or 0.0,
        })

    # sort by strike
    out.sort(key=lambda x: x["strike"])
    return out

def _compute_pcr(rows: List[Dict[str, float]]) -> float:
    total_put = sum((r["pe_oi"] or 0.0) for r in rows)
    total_call = sum((r["ce_oi"] or 0.0) for r in rows)
    if not total_call:
        return 0.0
    return round(total_put / total_call, 3)

def _max_pain_approx(rows: List[Dict[str, float]]) -> Optional[float]:
    # Lightweight approx: strike with highest combined OI
    best = None
    best_sum = -1
    for r in rows:
        s = (r["pe_oi"] or 0.0) + (r["ce_oi"] or 0.0)
        if s > best_sum:
            best_sum = s
            best = r["strike"]
    return best

def _iv_rank(rows: List[Dict[str, float]]) -> Optional[float]:
    # Use mid of CE/PE IV -> take range and rank current avg IV within it
    ivs = []
    for r in rows:
        if r["ce_iv"]: ivs.append(r["ce_iv"])
        if r["pe_iv"]: ivs.append(r["pe_iv"])
    ivs = [v for v in ivs if v and v > 0]
    if len(ivs) < 3:
        return None
    low, high = min(ivs), max(ivs)
    cur = statistics.median(ivs)
    if high <= low:
        return 50.0
    rank = 100.0 * (cur - low) / (high - low)
    return round(rank, 1)

def _support_resistance(rows: List[Dict[str, float]]) -> Tuple[Optional[float], Optional[float]]:
    # Support → highest PUT OI; Resistance → highest CALL OI
    sup, supv = None, -1
    res, resv = None, -1
    for r in rows:
        po, co = (r["pe_oi"] or 0.0), (r["ce_oi"] or 0.0)
        if po > supv:
            supv, sup = po, r["strike"]
        if co > resv:
            resv, res = co, r["strike"]
    return sup, res

def _spot_from_rows(rows: List[Dict[str, float]]) -> Optional[float]:
    # if LTPs exist, pick strike where CE LTP ~ PE LTP (ATM-ish)
    best = None
    bestdiff = None
    for r in rows:
        if r["ce_ltp"] and r["pe_ltp"]:
            diff = abs(r["ce_ltp"] - r["pe_ltp"])
            if bestdiff is None or diff < bestdiff:
                best, bestdiff = r["strike"], diff
    return best

def _bias_from_pcr_pain(pcr: float, spot: Optional[float], sup: Optional[float], res: Optional[float]) -> Tuple[str, int]:
    # Simple rule engine
    if pcr is None:
        return "NEUTRAL", 50
    bias = "NEUTRAL"
    conf = 55
    if pcr < 0.7:
        bias, conf = "BEARISH", 65
    elif pcr > 1.3:
        bias, conf = "BULLISH", 65

    # refine with spot near support/resistance
    try:
        if spot and sup and res:
            # if spot close to resistance and PCR low -> bearish strong
            if abs(spot - res) < abs(spot - sup) and pcr < 0.9:
                bias, conf = "BEARISH", max(conf, 70)
            # if spot near support and PCR high -> bullish strong
            if abs(spot - sup) < abs(spot - res) and pcr > 1.1:
                bias, conf = "BULLISH", max(conf, 70)
    except Exception:
        pass
    return bias, conf

# ---------- AI: Pydantic bodies ----------
class AIBaseBody(BaseModel):
    under_security_id: int = 13
    under_exchange_segment: str = "IDX_I"
    expiry: Optional[str] = None   # if None, we pick the nearest

class AIStrategyBody(AIBaseBody):
    capital: float = 50000
    risk: str = "moderate"  # low / moderate / high

# ---------- AI Core helpers ----------
def _fetch_chain_validated(under_security_id: int, under_exchange_segment: str, expiry: Optional[str]):
    # 1) expiry list
    ex = dhan.expiry_list(under_security_id=under_security_id, under_exchange_segment=under_exchange_segment)
    exlist = dget(ex, "data.data", []) or []
    if not exlist:
        return None, None, fail("No expiries available", data=ex)
    if expiry and expiry not in exlist:
        return None, None, fail("Invalid Expiry Date", code="811", data={"wanted": expiry, "available": exlist})
    use_exp = expiry or exlist[0]
    # 2) chain
    try:
        ch = dhan.option_chain(
            under_security_id=under_security_id,
            under_exchange_segment=under_exchange_segment,
            expiry=use_exp
        )
        return use_exp, ch, None
    except Exception as e:
        return None, None, fail("option chain failed", data=str(e))

def _build_marketview(chain_resp) -> Dict[str, Any]:
    rows = _normalize_chain(chain_resp)
    if not rows:
        return {"rows": [], "note":"chain rows empty"}
    pcr = _compute_pcr(rows)
    max_pain = _max_pain_approx(rows)
    ivrank = _iv_rank(rows)
    sup, res = _support_resistance(rows)
    spot = _spot_from_rows(rows)
    bias, conf = _bias_from_pcr_pain(pcr, spot, sup, res)
    # strike step
    gap = median_gap([r["strike"] for r in rows], default=50.0)

    return {
        "rows_count": len(rows),
        "pcr": pcr,
        "max_pain_approx": max_pain,
        "iv_rank": ivrank,
        "support": sup,
        "resistance": res,
        "spot_estimate": spot,
        "bias": bias,
        "confidence": conf,
        "strike_step": gap,
    }

def _suggest_strategy(view: Dict[str, Any], rows: List[Dict[str, float]], capital: float, risk: str) -> Dict[str, Any]:
    bias = view.get("bias") or "NEUTRAL"
    ivr  = view.get("iv_rank")
    step = view.get("strike_step") or 50.0
    spot = view.get("spot_estimate") or view.get("max_pain_approx")

    # default widths
    width = step * (2 if risk == "high" else (1 if risk == "low" else 1.5))
    width = round(width / step) * step

    # helper to find closest strike in rows
    strikes = [r["strike"] for r in rows]
    def closest(x):
        return min(strikes, key=lambda s: abs(s-x)) if strikes else x

    legs = []
    name = "Neutral Hold"
    rationale = "No strong signal."

    # choose by bias & IV rank
    if bias == "NEUTRAL":
        if ivr is None or ivr >= 50:
            # Credit: Iron Condor
            name = "Iron Condor"
            center = spot or (strikes[len(strikes)//2] if strikes else 0)
            short_put  = closest(center - step)
            long_put   = closest(short_put - width)
            short_call = closest(center + step)
            long_call  = closest(short_call + width)
            legs = [
                {"side":"SELL","type":"PUT","strike":short_put,"qty":1},
                {"side":"BUY", "type":"PUT","strike":long_put,"qty":1},
                {"side":"SELL","type":"CALL","strike":short_call,"qty":1},
                {"side":"BUY", "type":"CALL","strike":long_call,"qty":1},
            ]
            rationale = "Neutral view with mid/high IV → credit strategy to benefit from time decay."
        else:
            # Low IV → Iron Butterfly (debit-ish if priced tight)
            name = "Iron Butterfly"
            center = spot or (strikes[len(strikes)//2] if strikes else 0)
            long_put   = closest(center - width)
            short_p    = closest(center)
            short_c    = closest(center)
            long_call  = closest(center + width)
            legs = [
                {"side":"BUY", "type":"PUT", "strike":long_put, "qty":1},
                {"side":"SELL","type":"PUT", "strike":short_p,  "qty":1},
                {"side":"SELL","type":"CALL","strike":short_c,  "qty":1},
                {"side":"BUY", "type":"CALL","strike":long_call,"qty":1},
            ]
            rationale = "Neutral view with low IV → centered butterfly."
    elif bias == "BULLISH":
        if ivr is not None and ivr < 40:
            name = "Bull Call Spread"
            lower = closest((spot or strikes[0]) - 0*step)
            upper = closest(lower + width)
            legs = [
                {"side":"BUY","type":"CALL","strike":lower,"qty":1},
                {"side":"SELL","type":"CALL","strike":upper,"qty":1},
            ]
            rationale = "Bullish & low IV → debit vertical."
        else:
            name = "Cash-Secured Put (synthetic)"
            k = closest((spot or strikes[0]) - step)
            legs = [
                {"side":"SELL","type":"PUT","strike":k,"qty":1}
            ]
            rationale = "Bullish & mid/high IV → short put to collect premium."
    else:  # BEARISH
        if ivr is not None and ivr < 40:
            name = "Bear Put Spread"
            upper = closest((spot or strikes[-1]) + 0*step)
            lower = closest(upper - width)
            legs = [
                {"side":"BUY","type":"PUT","strike":upper,"qty":1},
                {"side":"SELL","type":"PUT","strike":lower,"qty":1},
            ]
            rationale = "Bearish & low IV → debit vertical."
        else:
            name = "Call Credit Spread"
            short = closest((spot or strikes[-1]) + step)
            long  = closest(short + width)
            legs = [
                {"side":"SELL","type":"CALL","strike":short,"qty":1},
                {"side":"BUY","type":"CALL","strike":long,"qty":1},
            ]
            rationale = "Bearish & mid/high IV → credit vertical."

    # very rough capacity check (1 lot placeholder)
    note_cap = "Assumes 1 lot; verify margin with broker."
    return {
        "name": name,
        "legs": legs,
        "risk_profile": risk,
        "capital_hint": capital,
        "rationale": rationale,
        "note": note_cap
    }

def _payoff_points(legs: List[Dict[str, Any]], rows: List[Dict[str, float]], around: Optional[float], step: float) -> List[Dict[str, float]]:
    """Approx payoff using strikes; premiums ~ row LTP if available else 0."""
    strikes = [r["strike"] for r in rows] or []
    if around is None:
        around = strikes[len(strikes)//2] if strikes else 0.0
    span = step * 12  # cover +/- 12 steps
    xs = []
    start = around - span
    for i in range(0, 25):
        xs.append(round(start + i*step, 2))

    # map strike -> ce/pe ltp
    ltp_map_ce = {r["strike"]: r["ce_ltp"] for r in rows}
    ltp_map_pe = {r["strike"]: r["pe_ltp"] for r in rows}

    def price_of(option_type, strike):
        # premium from chain if available
        if option_type == "CALL":
            return ltp_map_ce.get(strike, 0.0)
        return ltp_map_pe.get(strike, 0.0)

    out = []
    for s in xs:
        pnl = 0.0
        for leg in legs:
            typ = (leg["type"] or "CALL").upper()
            side = (leg["side"] or "BUY").upper()
            k = float(leg["strike"])
            qty = int(leg.get("qty", 1))

            # option payoff at expiry (simplified)
            intrinsic = max(0.0, s - k) if typ == "CALL" else max(0.0, k - s)
            premium = price_of(typ, k) or 0.0

            # BUY: -premium + intrinsic ; SELL: +premium - intrinsic
            if side == "BUY":
                leg_pnl = (intrinsic - premium) * qty
            else:
                leg_pnl = (premium - intrinsic) * qty

            pnl += leg_pnl
        out.append({"underlying": s, "pnl": round(pnl, 2)})
    return out

# ---------- AI Endpoints ----------
@app.post("/ai/marketview")
def ai_marketview(body: AIBaseBody = Body(...)):
    exp, chain, err = _fetch_chain_validated(body.under_security_id, body.under_exchange_segment, body.expiry)
    if err:
        return err
    view = _build_marketview(chain)
    return ok({"expiry": exp, "view": view})

@app.post("/ai/strategy")
def ai_strategy(body: AIStrategyBody = Body(...)):
    exp, chain, err = _fetch_chain_validated(body.under_security_id, body.under_exchange_segment, body.expiry)
    if err:
        return err
    rows = _normalize_chain(chain)
    view = _build_marketview(chain)
    strat = _suggest_strategy(view, rows, body.capital, (body.risk or "moderate").lower())
    return ok({"expiry": exp, "view": view, "strategy": strat})

@app.post("/ai/payoff")
def ai_payoff(body: AIStrategyBody = Body(...)):
    exp, chain, err = _fetch_chain_validated(body.under_security_id, body.under_exchange_segment, body.expiry)
    if err:
        return err
    rows = _normalize_chain(chain)
    view = _build_marketview(chain)
    strat = _suggest_strategy(view, rows, body.capital, (body.risk or "moderate").lower())
    points = _payoff_points(strat["legs"], rows, view.get("spot_estimate") or view.get("max_pain_approx"), view.get("strike_step") or 50.0)
    return ok({"expiry": exp, "strategy": strat, "payoff": points})

@app.get("/ai/test")
def ai_test(
    under_security_id: int = Query(13),
    under_exchange_segment: str = Query("IDX_I")
):
    # use first expiry
    exp, chain, err = _fetch_chain_validated(under_security_id, under_exchange_segment, None)
    if err:
        return err
    view = _build_marketview(chain)
    rows = _normalize_chain(chain)
    strat = _suggest_strategy(view, rows, 50000, "moderate")
    points = _payoff_points(strat["legs"], rows, view.get("spot_estimate") or view.get("max_pain_approx"), view.get("strike_step") or 50.0)
    return ok({"expiry": exp, "view": view, "strategy": strat, "payoff_sample": points[:7]})

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
        "option_analysis": "/option_analysis",
        # AI
        "ai_marketview": "POST /ai/marketview {under_security_id:13, under_exchange_segment:'IDX_I'}",
        "ai_strategy":   "POST /ai/strategy {under_security_id:13, under_exchange_segment:'IDX_I', risk:'moderate', capital:50000}",
        "ai_payoff":     "POST /ai/payoff {under_security_id:13, under_exchange_segment:'IDX_I'}",
        "ai_test":       "/ai/test?under_security_id=13&under_exchange_segment=IDX_I"
    }
    return {
        "status": {
            "mode": MODE, "env": ENV_NOTE,
            "token_present": bool(ACCESS_TOKEN),
            "client_id_present": bool(CLIENT_ID),
            "base_url_note": "MODE=LIVE uses LIVE_… keys; otherwise SANDBOX",
        },
        "samples": {k: (f"{base}{v}" if v.startswith("/") else v) for k, v in samples.items()},
        "now": datetime.now(timezone.utc).isoformat()
    }
