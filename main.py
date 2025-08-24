from fastapi import FastAPI, Request
import os
import requests

app = FastAPI()

# -------------------------
# Env helper functions
# -------------------------

def get_mode():
    return (os.getenv("MODE", "LIVE") or "LIVE").upper()

def pick(*names):
    """Return first non-empty env var out of the given names."""
    for n in names:
        v = os.getenv(n)
        if v and v.strip():
            return v.strip()
    return None

def load_dhan_creds():
    mode = get_mode()  # LIVE or SANDBOX

    if mode == "SANDBOX":
        client_id = pick("DHAN_SANDBOX_CLIENT_ID", "DHAN_CLIENT_ID_SANDBOX", "DHAN_CLIENT_ID")
        access    = pick("DHAN_SANDBOX_ACCESS_TOKEN", "DHAN_ACCESS_TOKEN_SANDBOX", "DHAN_ACCESS_TOKEN")
        base_url  = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")
    else:  # LIVE
        client_id = pick("DHAN_LIVE_CLIENT_ID", "DHAN_CLIENT_ID")
        access    = pick("DHAN_LIVE_ACCESS_TOKEN", "DHAN_ACCESS_TOKEN")
        base_url  = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")

    return {
        "mode": mode,
        "client_id": client_id,
        "access_token": access,
        "base_url": base_url,
    }

def make_headers():
    creds = load_dhan_creds()
    return {
        "Content-Type": "application/json",
        "access-token": creds["access_token"] or "",
        "client-id": creds["client_id"] or ""
    }

# -------------------------
# API Endpoints
# -------------------------

@app.get("/broker_status")
def broker_status():
    c = load_dhan_creds()
    return {
        "mode": c["mode"],
        "env": c["mode"],
        "token_present": bool(c["access_token"]),
        "client_id_present": bool(c["client_id"]),
    }

@app.get("/orders")
def get_orders():
    creds = load_dhan_creds()
    url = f"{creds['base_url']}/orders"
    r = requests.get(url, headers=make_headers())
    return r.json()

@app.get("/positions")
def get_positions():
    creds = load_dhan_creds()
    url = f"{creds['base_url']}/positions"
    r = requests.get(url, headers=make_headers())
    return r.json()

@app.get("/expiry_list")
def get_expiry_list(under_security_id: int, under_exchange_segment: str):
    creds = load_dhan_creds()
    url = f"{creds['base_url']}/expiry-list"
    body = {
        "under_security_id": under_security_id,
        "under_exchange_segment": under_exchange_segment
    }
    r = requests.post(url, headers=make_headers(), json=body)
    return r.json()

@app.post("/option_chain")
async def option_chain(request: Request):
    creds = load_dhan_creds()
    url = f"{creds['base_url']}/option-chain"
    body = await request.json()
    r = requests.post(url, headers=make_headers(), json=body)
    return r.json()

# -------------------------
# Debug helper (optional)
# -------------------------
@app.get("/debug_env")
def debug_env():
    keys = [
        "MODE",
        "DHAN_LIVE_CLIENT_ID","DHAN_LIVE_ACCESS_TOKEN",
        "DHAN_CLIENT_ID","DHAN_ACCESS_TOKEN",
        "DHAN_SANDBOX_CLIENT_ID","DHAN_SANDBOX_ACCESS_TOKEN",
    ]
    return {k: os.getenv(k, None) for k in keys}
