# main.py — Dhan REST integration + routes (FastAPI)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os, csv, io, requests
from datetime import datetime
from typing import Optional

app = FastAPI(title="Options Analysis API", version="2.0")

# CORS: easy testing from Hoppscotch/Postman/browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────
# ENV & CONSTANTS
# ─────────────────────────────────────────────────────────────────
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
MODE = os.getenv("MODE", "DRY").upper()  # DRY / LIVE

DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
DHAN_API_BASE = "https://api.dhan.co/v2"  # sandbox: https://sandbox.dhan.co/v2

INSTR_CSV_COMPACT = "https://images.dhan.co/api-data/api-scrip-master.csv"
INSTR_CSV_DETAILED = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def dhan_headers():
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="Dhan credentials missing")
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "client-id": DHAN_CLIENT_ID,
        "access-token": DHAN_ACCESS_TOKEN,
    }


def broker_ready() -> bool:
    return bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN)


def fetch_instruments_csv(detailed: bool = False) -> str:
    url = INSTR_CSV_DETAILED if detailed else INSTR_CSV_COMPACT
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text


# --- date helpers -------------------------------------------------
_MONTHS = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}

def _to_yyyy_mm_dd(s: str) -> Optional[str]:
    """
    Accepts:
      - YYYY-MM-DD
      - YYYY/MM/DD
      - DD-Mon-YYYY  (e.g. 28-Aug-2025 / 28-AUG-2025)
    Returns YYYY-MM-DD or None.
    """
    if not s:
        return None
    s = s.strip()
    try:
        if "-" in s and len(s.split("-")[0]) == 4:
            # YYYY-MM-DD
            dt = datetime.strptime(s, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        if "/" in s and len(s.split("/")[0]) == 4:
            dt = datetime.strptime(s, "%Y/%m/%d")
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    # DD-Mon-YYYY
    try:
        parts = s.replace("_", "-").split("-")
        if len(parts) == 3 and len(parts[2]) == 4:
            dd = parts[0].zfill(2)
            mm = _MONTHS.get(parts[1].upper()[:3])
            yyyy = parts[2]
            if mm:
                return f"{yyyy}-{mm}-{dd}"
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────
# Replace this whole function in main.py
# ─────────────────────────────────────────────────────────────────
def _fmt_expiry(date_str: str) -> tuple[str, str]:
    """
    Return (YYYY-MM-DD, DD-MMM-YYYY) both, so we can match either.
    """
    s = (date_str or "").strip()
    if not s:
        return "", ""
    # try parse YYYY-MM-DD
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        # try parse DD-MMM-YYYY (as it comes in CSV sometimes)
        try:
            dt = datetime.strptime(s.upper(), "%d-%b-%Y")
        except ValueError:
            return s, s  # give up; compare as-is
    iso = dt.strftime("%Y-%m-%d")
    dmy = dt.strftime("%d-%b-%Y").upper()  # e.g. 28-AUG-2025
    return iso, dmy

def _normalize_opt_type(t: str) -> set[str]:
    """
    Accept CE/PE or CALL/PUT.
    """
    x = (t or "").upper().strip()
    if x in {"CE", "CALL"}:
        return {"CE", "CALL"}
    if x in {"PE", "PUT"}:
        return {"PE", "PUT"}
    return {x}

def lookup_security_id(underlying_symbol: str, expiry: str, strike: float, option_type: str):
    """
    Returns first matching Security ID or None.
    Robust against:
      - Expiry in YYYY-MM-DD vs DD-MMM-YYYY (CSV often uses DD-MMM-YYYY)
      - Option type CE/PE vs CALL/PUT
      - Float formatting of strike
    """
    csv_text = fetch_instruments_csv(detailed=True)
    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)

    # detect any Security ID column
    header = reader.fieldnames or []
    sec_id_col = None
    for c in ("SECURITY_ID", "SEM_SECURITY_ID", "SM_SECURITY_ID"):
        if c in header:
            sec_id_col = c
            break

    sym = (underlying_symbol or "").upper().strip()
    exp_iso, exp_dmy = _fmt_expiry(expiry)
    opt_set = _normalize_opt_type(option_type)

    # small float tolerance
    try:
        strike_f = float(strike)
    except Exception:
        strike_f = None

    for row in reader:
        try:
            if row.get("UNDERLYING_SYMBOL", "").upper().strip() != sym:
                continue

            csv_exp = (row.get("SEM_EXPIRY_DATE") or row.get("SM_EXPIRY_DATE") or "").upper().strip()
            if csv_exp not in {exp_iso.upper(), exp_dmy}:
                continue

            csv_type = (row.get("SEM_OPTION_TYPE") or row.get("OPTION_TYPE") or "").upper().strip()
            if csv_type not in opt_set:
                continue

            csv_strike_raw = row.get("SEM_STRIKE_PRICE") or row.get("STRIKE_PRICE") or "0"
            try:
                csv_strike = float(csv_strike_raw)
            except Exception:
                continue

            if (strike_f is None) or (abs(csv_strike - strike_f) > 1e-6):
                continue

            return row.get(sec_id_col) if sec_id_col else None
        except Exception:
            continue

    return Nonedef place_dhan_order(
    security_id: str,
    side: str,                  # BUY / SELL
    qty: int,
    order_type: str = "MARKET", # MARKET / LIMIT
    price: float | None = None,
    product_type: str = "INTRADAY",
    exchange_segment: str = "NSE_FNO",
    validity: str = "DAY",
    tag: str | None = None,
):
    """Minimal place order to Dhan v2."""
    url = f"{DHAN_API_BASE}/orders"
    payload = {
        "transaction_type": side,              # BUY/SELL
        "exchange_segment": exchange_segment,  # e.g. NSE_FNO
        "product_type": product_type,          # e.g. INTRADAY
        "order_type": order_type,              # MARKET/LIMIT
        "validity": validity,                  # DAY/IOC
        "security_id": str(security_id),
        "quantity": int(qty),
    }
    if tag:
        payload["correlation_id"] = str(tag)
    if order_type == "LIMIT" and (price is not None):
        payload["price"] = float(price)

    r = requests.post(url, headers=dhan_headers(), json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"text": r.text}
    return r.status_code, data


def dhan_quote_snapshot(body: dict):
    """Calls /marketfeed/quote for snapshot (LTP, OHLC, depth, OI)."""
    url = f"{DHAN_API_BASE}/marketfeed/quote"
    r = requests.post(url, headers=dhan_headers(), json=body, timeout=20)
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "has_lib": True,
        "has_creds": broker_ready(),
        "client_ready": broker_ready(),
    }


# 👉 GET info (browser friendly)
@app.get("/security_lookup")
def security_lookup_info():
    return {
        "use": "POST /security_lookup with JSON body",
        "example": {
            "symbol": "NIFTY",
            "expiry": "2025-08-28",   # YYYY-MM-DD (auto handles 28-Aug-2025 in CSV)
            "strike": 25100,
            "option_type": "CE"
        }
    }


# 👉 Actual POST lookup
@app.post("/security_lookup")
async def security_lookup(payload: dict):
    """
    Payload:
    {
      "symbol": "NIFTY",
      "expiry": "2025-08-28",
      "strike": 25100,
      "option_type": "CE"
    }
    """
    sec_id = lookup_security_id(
        payload.get("symbol", ""),
        payload.get("expiry", ""),
        payload.get("strike", 0),
        payload.get("option_type", ""),
    )
    return {"security_id": sec_id}


@app.post("/dhan/quote")
async def dhan_quote(body: dict):
    """
    Body example:
    { "NSE_FNO": [49081] }
    """
    try:
        resp = dhan_quote_snapshot(body)
        return resp
    except requests.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@app.post("/webhook")
async def webhook(request: Request):
    """
    TradingView / manual alerts:
    {
      "secret": "my$ecret123",
      "symbol": "NIFTY",
      "action": "BUY",
      "expiry": "2025-08-28",
      "strike": 25100,
      "option_type": "CE",
      "qty": 50,
      "price": "MARKET",            # or numeric for LIMIT
      "security_id": "optional_if_known"
    }
    """
    data = await request.json()

    # 1) Secret check
    if str(data.get("secret", "")) != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 2) Parse fields
    symbol = data.get("symbol")
    action = data.get("action")              # BUY/SELL
    expiry = data.get("expiry")              # YYYY-MM-DD
    strike = data.get("strike")
    option_type = data.get("option_type")    # CE/PE
    qty = int(data.get("qty", 0))
    price = data.get("price", "MARKET")
    security_id = data.get("security_id")

    if not symbol or not action or qty <= 0:
        raise HTTPException(422, detail="symbol/action/qty required")

    # DRY mode → simulate only
    if MODE != "LIVE":
        return {
            "ok": True,
            "mode": MODE,
            "received": data,
            "order": {
                "side": action, "symbol": symbol, "expiry": expiry,
                "strike": strike, "type": option_type, "qty": qty, "price": price,
                "security_id": security_id,
                "note": "DRY mode: no live order. Set MODE=LIVE to execute."
            }
        }

    # LIVE mode → ensure security_id
    if not security_id:
        security_id = lookup_security_id(symbol, expiry, strike, option_type)
        if not security_id:
            raise HTTPException(400, detail="security_id not found")

    # MARKET or LIMIT selection
    order_type = "MARKET"
    limit_price = None
    try:
        if isinstance(price, (int, float)) or (isinstance(price, str) and price.replace(".", "", 1).isdigit()):
            order_type = "LIMIT"
            limit_price = float(price)
        elif str(price).upper() == "MARKET":
            order_type = "MARKET"
    except Exception:
        order_type = "MARKET"

    # Place order
    tag = f"tv-{datetime.utcnow().isoformat()}"
    status, broker_resp = place_dhan_order(
        security_id=str(security_id),
        side=str(action).upper(),
        qty=qty,
        order_type=order_type,
        price=limit_price,
        product_type="INTRADAY",
        exchange_segment="NSE_FNO",
        validity="DAY",
        tag=tag,
    )

    return {
        "ok": status in (200, 201),
        "mode": "LIVE",
        "received": data,
        "dhan_response": broker_resp,
    }
# ─────────────────────────────────────────────────────────────────
# ADD this route (anywhere below helper defs, above webhook)
# ─────────────────────────────────────────────────────────────────
@app.get("/debug_lookup")
def debug_lookup(symbol: str = "NIFTY", limit: int = 10):
    """
    Browser:  /debug_lookup?symbol=NIFTY
    Dekhne ke liye ki CSV me expiry/type/strike ka format kya aa raha hai.
    """
    txt = fetch_instruments_csv(detailed=True)
    f = io.StringIO(txt)
    reader = csv.DictReader(f)
    sec_col = None
    for c in ("SECURITY_ID", "SEM_SECURITY_ID", "SM_SECURITY_ID"):
        if c in (reader.fieldnames or []):
            sec_col = c
            break

    out = []
    for row in reader:
        if row.get("UNDERLYING_SYMBOL", "").upper() == symbol.upper():
            out.append({
                "SECURITY_ID": row.get(sec_col),
                "UNDERLYING_SYMBOL": row.get("UNDERLYING_SYMBOL"),
                "SEM_EXPIRY_DATE": row.get("SEM_EXPIRY_DATE"),
                "SEM_OPTION_TYPE": row.get("SEM_OPTION_TYPE"),
                "SEM_STRIKE_PRICE": row.get("SEM_STRIKE_PRICE"),
                "SEM_TRADING_SYMBOL": row.get("SEM_TRADING_SYMBOL") or row.get("SEM_CUSTOM_SYMBOL"),
            })
            if len(out) >= max(1, min(50, limit)):
                break
    return out
