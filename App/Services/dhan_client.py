# App/Services/dhan_client.py
import os
from typing import Dict, Any
import httpx

DHAN_BASE_URL = os.getenv("DHAN_BASE_URL", "https://api.dhan.co")  # change if needed
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

DEFAULT_TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SEC", "15"))

HEADERS = {
    "Client-Id": DHAN_CLIENT_ID,
    "Access-Token": DHAN_ACCESS_TOKEN,
    # If your Dhan account expects different names, change here once
}

ALLOWED_PREFIXES = (
    "/market",       # marketfeed/marketquote/marketdepth etc.
    "/quotes",       # quotes endpoints
    "/option",       # optionchain-like
    "/chart",        # chart/historical
    "/instruments",  # instruments
    "/indices",      # indices
)

def _allowed(path: str) -> bool:
    path = path.strip() or "/"
    return any(path.startswith(p) for p in ALLOWED_PREFIXES)

async def get_json(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safe GET proxy to Dhan with allow-listed path prefixes.
    """
    if not _allowed(path):
        return {"ok": False, "error": f"path '{path}' not allowed", "allowed": list(ALLOWED_PREFIXES)}

    url = DHAN_BASE_URL.rstrip("/") + path
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, headers=HEADERS) as client:
        resp = await client.get(url, params=params)
        # Try JSON first, else return text
        try:
            data = resp.json()
        except Exception:
            data = {"raw": await resp.aread()}
        return {
            "ok": resp.is_success,
            "status_code": resp.status_code,
            "url": str(resp.request.url),
            "data": data,
        }
