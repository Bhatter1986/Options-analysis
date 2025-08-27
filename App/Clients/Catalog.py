import json, requests

with open("config.json") as f:
    CFG = json.load(f)

BASE = CFG["base_url"]

def _g(path, **params):
    r = requests.get(f"{BASE}{path}", params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def get_indices(q=None, limit=200):
    res = _g("/instruments/indices", q=q)
    rows = (res.get("rows") or res.get("data") or [])
    return rows[:limit]

def search_any(q, limit=200):
    res = _g("/instruments/search", q=q)
    rows = (res.get("rows") or res.get("data") or [])
    return rows[:limit]

def by_id(security_id: str | int):
    return _g("/instruments/by-id", security_id=str(security_id))

def load_watchlist(name: str):
    return CFG["watchlists"].get(name, [])

def refresh_cache():
    r = requests.post(f"{BASE}/instruments/_refresh", timeout=30)
    r.raise_for_status()
    return r.json()
