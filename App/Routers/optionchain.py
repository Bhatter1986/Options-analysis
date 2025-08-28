from fastapi import APIRouter, HTTPException
import os, requests, time

router = APIRouter()

# 🔑 Env Vars from Render
DHAN_TOKEN = os.getenv("DHAN_TOKEN")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
BASE_URL = "https://api.dhan.co/v2"

# Cache memory
_cache = {
    "expirylist": {},
    "optionchain": {}
}
_cache_ttl = 10    # seconds (expirylist cache)
_chain_ttl = 3     # seconds (optionchain cache, matches API rate-limit)


def call_dhan_api(endpoint: str, payload: dict):
    """Generic caller for Dhan API with headers"""
    headers = {
        "access-token": DHAN_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json"
    }
    url = f"{BASE_URL}{endpoint}"
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/optionchain/expirylist/{symbol}")
def get_expiry_list(symbol: str):
    """
    Fetch Expiry List for given underlying (e.g., NIFTY, BANKNIFTY).
    Uses caching for 10s to reduce hits.
    """
    now = time.time()
    if symbol in _cache["expirylist"] and now - _cache["expirylist"][symbol]["time"] < _cache_ttl:
        return _cache["expirylist"][symbol]["data"]

    # Map symbol to UnderlyingScrip + Segment (from instruments.csv ideally)
    mapping = {
        "NIFTY": {"UnderlyingScrip": 13, "UnderlyingSeg": "IDX_I"},
        "BANKNIFTY": {"UnderlyingScrip": 25, "UnderlyingSeg": "IDX_I"},
        "FINNIFTY": {"UnderlyingScrip": 52, "UnderlyingSeg": "IDX_I"},
    }
    if symbol not in mapping:
        raise HTTPException(status_code=400, detail=f"Unsupported symbol: {symbol}")

    payload = mapping[symbol]
    data = call_dhan_api("/optionchain/expirylist", payload)

    _cache["expirylist"][symbol] = {"data": data, "time": now}
    return data


@router.post("/optionchain/{symbol}/{expiry}")
def get_option_chain(symbol: str, expiry: str):
    """
    Fetch Option Chain for given symbol + expiry.
    Uses caching for 3s because Dhan rate-limit is 1 req/3s.
    """
    cache_key = f"{symbol}_{expiry}"
    now = time.time()
    if cache_key in _cache["optionchain"] and now - _cache["optionchain"][cache_key]["time"] < _chain_ttl:
        return _cache["optionchain"][cache_key]["data"]

    mapping = {
        "NIFTY": {"UnderlyingScrip": 13, "UnderlyingSeg": "IDX_I"},
        "BANKNIFTY": {"UnderlyingScrip": 25, "UnderlyingSeg": "IDX_I"},
        "FINNIFTY": {"UnderlyingScrip": 52, "UnderlyingSeg": "IDX_I"},
    }
    if symbol not in mapping:
        raise HTTPException(status_code=400, detail=f"Unsupported symbol: {symbol}")

    payload = {**mapping[symbol], "Expiry": expiry}
    data = call_dhan_api("/optionchain", payload)

    _cache["optionchain"][cache_key] = {"data": data, "time": now}
    return data
