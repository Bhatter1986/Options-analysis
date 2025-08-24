# test_mode.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
import os, requests, json
from typing import Any, Dict, Optional, Tuple

router = APIRouter()

# --------- helpers copied (light) ----------
def MODE() -> str:
    m = (os.getenv("MODE") or "LIVE").strip().upper()
    return m if m in {"DRY","LIVE","SANDBOX"} else "LIVE"

def pick(live_key: str, sbx_key: str) -> Optional[str]:
    return os.getenv(live_key) if MODE()=="LIVE" else os.getenv(sbx_key)

def BASE_URL() -> str:
    return (pick("DHAN_LIVE_BASE_URL","DHAN_SANDBOX_BASE_URL") or "").rstrip("/")

def CLIENT_ID() -> str:
    # allow fallback DHAN_CLIENT_ID
    return pick("DHAN_LIVE_CLIENT_ID","DHAN_SANDBOX_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID","")

def ACCESS_TOKEN() -> str:
    # allow fallback DHAN_ACCESS_TOKEN
    return pick("DHAN_LIVE_ACCESS_TOKEN","DHAN_SANDBOX_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN","")

def headers() -> Dict[str,str]:
    return {
        "accept":"application/json",
        "content-type":"application/json",
        **({"client-id": CLIENT_ID()} if CLIENT_ID() else {}),
        **({"access-token": ACCESS_TOKEN()} if ACCESS_TOKEN() else {}),
    }

DH_PATHS = {
    "orders": "/orders",
    "positions": "/positions",
    "expiry_list": "/expiry-list",
    "option_chain": "/option-chain",
    "ohlc_data": "/ohlc-data",
    "holdings": "/holdings",
    "fund_limits": "/fund-limits",
    "trade_book": "/tradebook",
    "trade_history": "/trade-history",
    "intraday_minute": "/intraday-minute-data",
    "historical_daily": "/historical-daily-data",
}

def call_api(method: str, path: str, params: Dict[str,Any]|None=None, json_body: Dict[str,Any]|None=None, timeout: int = 25) -> Tuple[int, Any]:
    url = f"{BASE_URL()}{path}"
    try:
        if method == "GET":
            r = requests.get(url, headers=headers(), params=params, timeout=timeout)
        else:
            r = requests.post(url, headers=headers(), json=json_body, timeout=timeout)
        try:
            body = r.json()
        except Exception:
            body = r.text
        return r.status_code, body
    except requests.RequestException as e:
        return 0, f"REQUEST-ERROR: {e}"

# --------- individual checks ----------
def check_env() -> Dict[str, Any]:
    m = MODE()
    required = ["MODE"]
    if m == "LIVE":
        required += ["DHAN_LIVE_BASE_URL","DHAN_LIVE_CLIENT_ID","DHAN_LIVE_ACCESS_TOKEN"]
    elif m == "SANDBOX":
        required += ["DHAN_SANDBOX_BASE_URL","DHAN_SANDBOX_CLIENT_ID","DHAN_SANDBOX_ACCESS_TOKEN"]
    present = {k: bool(os.getenv(k)) for k in required}
    fallback = {
        "DHAN_CLIENT_ID": bool(os.getenv("DHAN_CLIENT_ID")),
        "DHAN_ACCESS_TOKEN": bool(os.getenv("DHAN_ACCESS_TOKEN")),
    }
    return {
        "mode": m,
        "base_url": BASE_URL(),
        "present": present,
        "fallback_present": fallback
    }

def quick_ping() -> Dict[str, Any]:
    # try a cheap endpoint likely to exist: positions or orders
    code, body = call_api("GET", DH_PATHS["positions"])
    return {"endpoint": "positions", "code": code, "sample": body}

def get_expiries() -> Dict[str, Any]:
    params = {"under_security_id": 13, "under_exchange_segment": "IDX_I"}
    code, body = call_api("GET", DH_PATHS["expiry_list"], params=params)
    # try to pick first date if available
    first_exp = None
    try:
        data = body.get("data",{}).get("data",{})
        arr = data.get("data") or data.get("expiries") or []
        if isinstance(arr, list) and arr:
            first_exp = arr[0]
    except Exception:
        pass
    return {"endpoint":"expiry_list", "code":code, "sample":body, "first_expiry": first_exp}

def test_option_chain(expiry: Optional[str]) -> Dict[str, Any]:
    payload = {"under_security_id":13, "under_exchange_segment":"IDX_I"}
    if expiry: payload["expiry"] = expiry
    code, body = call_api("POST", DH_PATHS["option_chain"], json_body=payload)
    return {"endpoint":"option_chain", "code":code, "req":payload, "sample":body}

def test_market_quote() -> Dict[str, Any]:
    payload = {"securities":{"NSE_EQ":[1333]}}
    code, body = call_api("POST", DH_PATHS["ohlc_data"], json_body=payload)
    return {"endpoint":"ohlc_data", "code":code, "req":payload, "sample":body}

def test_intraday() -> Dict[str, Any]:
    params = {"security_id":1333,"exchange_segment":"NSE","instrument_type":"EQ","interval":"5"}
    code, body = call_api("GET", DH_PATHS["intraday_minute"], params=params)
    return {"endpoint":"intraday_minute_data", "code":code, "params":params, "sample":body}

def test_historical() -> Dict[str, Any]:
    params = {"security_id":1333,"exchange_segment":"NSE","instrument_type":"EQ","from_date":"2025-01-01","to_date":"2025-08-24"}
    code, body = call_api("GET", DH_PATHS["historical_daily"], params=params)
    return {"endpoint":"historical_daily_data", "code":code, "params":params, "sample":body}

def test_core_books() -> Dict[str, Any]:
    o_code, o_body = call_api("GET", DH_PATHS["orders"])
    p_code, p_body = call_api("GET", DH_PATHS["positions"])
    h_code, h_body = call_api("GET", DH_PATHS["holdings"])
    f_code, f_body = call_api("GET", DH_PATHS["fund_limits"])
    return {
        "orders":{"code":o_code,"sample":o_body},
        "positions":{"code":p_code,"sample":p_body},
        "holdings":{"code":h_code,"sample":h_body},
        "fund_limits":{"code":f_code,"sample":f_body},
    }

# --------- aggregated runner ----------
@router.get("/run")
def run_all_tests():
    env = check_env()

    # If base / env missing, stop early but still return structure
    summary: Dict[str, Any] = {"env": env, "base_url_ok": bool(env["base_url"])}

    # Do a light ping
    summary["quick_ping"] = quick_ping()

    # Core books
    summary["core"] = test_core_books()

    # Expiry flow + option-chain
    expiry_res = get_expiries()
    summary["expiry_list"] = expiry_res
    summary["option_chain"] = test_option_chain(expiry_res.get("first_expiry"))

    # Quotes & charts
    summary["market_quote"] = test_market_quote()
    summary["intraday_minute"] = test_intraday()
    summary["historical_daily"] = test_historical()

    # Simple verdicts (true/false)
    def ok(x): return isinstance(x, dict) and int(x.get("code",0)) in (200,201)
    summary["verdicts"] = {
        "env_ok": all(env["present"].values()) and bool(env["base_url"]),
        "positions_ok": ok(summary["quick_ping"]),
        "orders_ok": ok(summary["core"]["orders"]),
        "holdings_ok": ok(summary["core"]["holdings"]),
        "funds_ok": ok(summary["core"]["fund_limits"]),
        "expiry_ok": ok(summary["expiry_list"]),
        "option_chain_ok": ok(summary["option_chain"]),
        "quote_ok": ok(summary["market_quote"]),
        "intraday_ok": ok(summary["intraday_minute"]),
        "historical_ok": ok(summary["historical_daily"]),
    }

    return summary

# --------- very simple HTML dashboard ----------
@router.get("/ui", response_class=HTMLResponse)
def test_ui():
    html = """
    <html><head><title>Test Mode</title>
    <style>
      body{font-family: ui-sans-serif,system-ui; padding:20px; max-width:950px; margin:auto}
      code{background:#f3f3f3; padding:2px 6px; border-radius:5px}
      .ok{color:#0a0}
      .bad{color:#a00}
      pre{background:#0b1020; color:#e6eefb; padding:12px; border-radius:8px; overflow:auto}
    </style></head>
    <body>
      <h1>Options Data – Test Mode</h1>
      <p>Run JSON: <a href="/_test/run" target="_blank">/_test/run</a></p>
      <script>
        async function load(){
          const res = await fetch('/_test/run'); const data = await res.json();
          document.getElementById('json').textContent = JSON.stringify(data, null, 2);

          function flag(b){ return b ? '<b class="ok">OK</b>' : '<b class="bad">FAIL</b>'; }
          const v = data.verdicts || {};
          const rows = [
            ['Env', flag(v.env_ok)],
            ['Positions (ping)', flag(v.positions_ok)],
            ['Orders', flag(v.orders_ok)],
            ['Holdings', flag(v.holdings_ok)],
            ['Fund Limits', flag(v.funds_ok)],
            ['Expiry List', flag(v.expiry_ok)],
            ['Option Chain', flag(v.option_chain_ok)],
            ['Market Quote', flag(v.quote_ok)],
            ['Intraday Minute', flag(v.intraday_ok)],
            ['Historical Daily', flag(v.historical_ok)],
          ];
          document.getElementById('table').innerHTML =
            '<table border="1" cellpadding="8"><tr><th>Check</th><th>Status</th></tr>' +
            rows.map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join('') +
            '</table>';
        }
        load();
      </script>
      <div id="table" style="margin:16px 0;"></div>
      <h3>Raw JSON</h3>
      <pre id="json">{}</pre>
    </body></html>
    """
    return HTMLResponse(content=html)
