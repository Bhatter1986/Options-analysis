# --- DhanHQ v2: minimal REST integration (no SDK) ---

import os, csv, io, requests
from datetime import datetime

DHAN_API_BASE = "https://api.dhan.co/v2"
INSTR_CSV_COMPACT = "https://images.dhan.co/api-data/api-scrip-master.csv"
INSTR_CSV_DETAILED = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

def dhan_headers():
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "client-id": os.getenv("DHAN_CLIENT_ID", ""),
        "access-token": os.getenv("DHAN_ACCESS_TOKEN", ""),
    }

def broker_ready():
    # simple credential ping (no dedicated ping in v2, so just validate headers shape)
    cid = os.getenv("DHAN_CLIENT_ID")
    tok = os.getenv("DHAN_ACCESS_TOKEN")
    return bool(cid and tok)

def fetch_instruments_csv(detailed=False):
    url = INSTR_CSV_DETAILED if detailed else INSTR_CSV_COMPACT
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text

def lookup_security_id(underlying_symbol: str, expiry: str, strike: float, option_type: str):
    """
    underlying_symbol: e.g. 'NIFTY'
    expiry: 'YYYY-MM-DD'
    strike: 25100
    option_type: 'CE' or 'PE'
    Returns first matching Security ID (string) or None
    """
    csv_text = fetch_instruments_csv(detailed=True)
    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)

    # Dhan detailed columns (commonly used):
    # EXCH_ID, SEGMENT, UNDERLYING_SYMBOL, SEM_EXPIRY_DATE, SEM_STRIKE_PRICE, SEM_OPTION_TYPE, SECURITY_ID/SEM_SECURITY_ID
    # Note: different dumps may name Security ID column as 'SECURITY_ID' or 'SEM_SECURITY_ID'
    sec_id_col = None

    # detect security-id column
    header = reader.fieldnames or []
    for c in ("SECURITY_ID", "SEM_SECURITY_ID", "SM_SECURITY_ID"):
        if c in header:
            sec_id_col = c
            break

    for row in reader:
        try:
            if (
                row.get("UNDERLYING_SYMBOL", "").upper() == underlying_symbol.upper()
                and row.get("SEM_EXPIRY_DATE", "") == expiry
                and row.get("SEM_OPTION_TYPE", "").upper() == option_type.upper()
                and float(row.get("SEM_STRIKE_PRICE", "0") or 0) == float(strike)
            ):
                return row.get(sec_id_col) if sec_id_col else None
        except Exception:
            continue
    return None

def place_dhan_order(
    security_id: str,
    side: str,                # 'BUY' / 'SELL'
    qty: int,
    order_type: str = "MARKET",   # 'MARKET' / 'LIMIT'
    price: float | None = None,
    product_type: str = "INTRADAY",   # 'INTRADAY' / 'CNC' / 'MARGIN' etc.
    exchange_segment: str = "NSE_FNO",  # 'NSE_EQ' / 'NSE_FNO' / 'BSE_EQ' / 'MCX' ...
    validity: str = "DAY",            # 'DAY' / 'IOC'
    tag: str | None = None,
):
    """
    Minimal v2 payload for Options/F&O market order.
    Confirm available values per Dhan docs for your segment/product.
    """
    url = f"{DHAN_API_BASE}/orders"
    payload = {
        "transaction_type": side,              # BUY or SELL
        "exchange_segment": exchange_segment,  # e.g., NSE_FNO for index options
        "product_type": product_type,          # e.g., INTRADAY
        "order_type": order_type,              # MARKET / LIMIT
        "validity": validity,                  # DAY / IOC
        "security_id": str(security_id),
        "quantity": int(qty),
    }
    if tag:
        payload["correlation_id"] = str(tag)
    if order_type == "LIMIT" and price is not None:
        payload["price"] = float(price)

    r = requests.post(url, headers=dhan_headers(), json=payload, timeout=30)
    # Successful place → 200/201 with JSON (order_id, status, remarks...)
    return r.status_code, r.json() if r.content else {}
