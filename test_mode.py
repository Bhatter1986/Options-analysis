"""
Run locally to smoke-test the service.

$ uvicorn main:app --reload
$ python testmode.py
"""
import json, requests

BASE = "http://127.0.0.1:8000"

def ping(path: str):
    url = f"{BASE}{path}"
    try:
        r = requests.get(url, timeout=20)
        ok = r.status_code
        return {"url": url, "status": ok, "len": len(r.text)}
    except Exception as e:
        return {"url": url, "error": str(e)}

checks = [
    "/", "/health", "/broker_status",
    "/orders", "/positions", "/holdings", "/funds",
    "/optionchain/expirylist?under_security_id=13&under_exchange_segment=IDX_I",
    "/charts/intraday?security_id=1333&exchange_segment=NSE&instrument_type=EQUITY",
    "/charts/historical?security_id=1333&exchange_segment=NSE&instrument_type=EQUITY&expiry_code=0&from_date=2024-01-01&to_date=2024-02-01",
    "/option_analysis", "/__selftest"
]

if __name__ == "__main__":
    print(json.dumps({p: ping(p) for p in checks}, indent=2))
