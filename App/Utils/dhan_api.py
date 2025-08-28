# App/utils/dhan_api.py
import os, time, requests
from fastapi import HTTPException

BASE_URL = "https://api.dhan.co/v2"
DHAN_TOKEN = os.getenv("DHAN_TOKEN")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")

def call_dhan_api(endpoint: str, payload: dict | None = None, method: str = "POST"):
    if not DHAN_TOKEN or not DHAN_CLIENT_ID:
        raise HTTPException(500, "Dhan env missing: DHAN_TOKEN / DHAN_CLIENT_ID")

    headers = {
        "access-token": DHAN_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json",
    }
    url = f"{BASE_URL}{endpoint}"
    resp = requests.request(method, url, headers=headers, json=payload or {})
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"{endpoint} failed: {resp.text}")
    return resp.json()

def dhan_sleep():
    time.sleep(3)  # 1 req / 3s (rate limit)
