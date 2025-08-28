import os, time, requests
from fastapi import HTTPException

BASE_URL = "https://api.dhan.co/v2"

def _active_creds():
    # env names exactly as your .env / Render
    token = os.getenv("DHAN_TOKEN")
    client = os.getenv("DHAN_CLIENT_ID")
    if not token or not client:
        raise HTTPException(500, "Dhan env missing: DHAN_TOKEN / DHAN_CLIENT_ID")
    return token, client

def call_dhan_api(endpoint: str, payload: dict | None=None, method: str="POST"):
    token, client = _active_creds()
    headers = {
        "access-token": token,
        "client-id": client,
        "Content-Type": "application/json",
    }
    url = f"{BASE_URL}{endpoint}"
    r = requests.request(method, url, headers=headers, json=payload or {})
    if r.status_code != 200:
        raise HTTPException(r.status_code, f"{endpoint} failed: {r.text}")
    return r.json()

def dhan_sleep():
    # rate limit: 1 req / 3s
    time.sleep(3)
