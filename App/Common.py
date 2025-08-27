import os, logging, json, requests, time
from dotenv import load_dotenv
from fastapi import HTTPException, Request

load_dotenv()

MODE              = os.getenv("MODE", "SANDBOX").upper()
WEBHOOK_SECRET    = os.getenv("WEBHOOK_SECRET", "")
DHAN_CLIENT_ID    = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip()

DHAN_BASE_URL = "https://api.dhan.co" if MODE == "LIVE" else "https://api-sandbox.dhan.co"
DHAN_API_BASE = f"{DHAN_BASE_URL}/api/v2"

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("options-api")

def mask(value: str | None, show: int = 4) -> str:
    if not value: return "∅"
    if len(value) <= show: return "*" * len(value)
    return value[:show] + "…" + "*" * (len(value) - show)

def _dhan_headers() -> dict:
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail="Dhan credentials not configured")
    return {"access-token": DHAN_ACCESS_TOKEN, "client-id": DHAN_CLIENT_ID,
            "Accept": "application/json", "Content-Type": "application/json"}

def _safe_json(r: requests.Response):
    try:
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError:
        try: detail = r.json()
        except Exception: detail = r.text
        logger.error(f"Dhan HTTP {r.status_code}: {detail}")
        raise HTTPException(status_code=r.status_code, detail=detail)
    except Exception as e:
        logger.error(f"Dhan API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def dhan_get(path: str, params: dict | None = None, timeout: int = 15):
    url = f"{DHAN_API_BASE}{path}"
    logger.info(f"Dhan GET {url} params={params}")
    return _safe_json(requests.get(url, headers=_dhan_headers(), params=params, timeout=timeout))

def dhan_post(path: str, payload: dict | None = None, timeout: int = 20):
    url = f"{DHAN_API_BASE}{path}"
    logger.info(f"Dhan POST {url} json={payload}")
    return _safe_json(requests.post(url, headers=_dhan_headers(), json=payload, timeout=timeout))

def verify_secret(request: Request):
    if WEBHOOK_SECRET:
        tok = request.headers.get("X-Webhook-Secret")
        logger.info(f"SEC {request.method} {request.url.path} recv={mask(tok)} expect={mask(WEBHOOK_SECRET)}")
        if tok != WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")
    return True
