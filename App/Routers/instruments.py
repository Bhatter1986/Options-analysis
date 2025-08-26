# App/Routers/instruments.py
from fastapi import APIRouter, Query
from typing import List, Optional
import os, time, io, csv, requests

router = APIRouter(prefix="/instruments", tags=["instruments"])

INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv",
)

# --- simple in-memory cache (CSV 5 min ke liye) ---
_CACHE: dict = {"ts": 0.0, "text": ""}          # ts = epoch seconds
_CACHE_TTL = 300.0                               # 5 minutes

def _download_master_csv() -> str:
    now = time.time()
    if _CACHE["text"] and (now - _CACHE["ts"] < _CACHE_TTL):
        return _CACHE["text"]
    resp = requests.get(INSTRUMENTS_URL, timeout=20)
    resp.raise_for_status()
    text = resp.content.decode("utf-8", errors="ignore")
    _CACHE["text"] = text
    _CACHE["ts"] = now
    return text

def _row_is_index(row: dict) -> bool:
    seg = (row.get("exchange_segment") or row.get("segment") or "").upper()
    inst = (row.get("instrument") or row.get("instrument_type") or "").upper()
    sym = (row.get("symbol") or row.get("trading_symbol") or "").upper()
    name = (row.get("security_name") or row.get("name") or "").upper()

    # Dhan CSV: indices usually in NSE index segment "IDX_I"
    if seg in {"IDX_I", "NSE_IDX", "BSE_IDX"}:
        return True
    if "INDEX" in inst:
        return True
    # Fallback: common index names
    for key in ("NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "MIDCPNIFTY"):
        if key in sym or key in name:
            return True
    return False

def _pick_fields(row: dict) -> dict:
    return {
        "security_id": row.get("security_id") or row.get("token") or row.get("id"),
        "trading_symbol": row.get("trading_symbol") or row.get("symbol"),
        "security_name": row.get("security_name") or row.get("name"),
        "exchange_segment": row.get("exchange_segment") or row.get("segment"),
        "isin": row.get("isin"),
        "instrument": row.get("instrument") or row.get("instrument_type"),
    }

@router.get("/indices")
def get_indices(
    q: Optional[str] = Query(None, description="search text"),
    limit: int = Query(50, ge=1, le=500),
):
    """
    Return list of all indices (NIFTY, BANKNIFTY, FINNIFTY, SENSEX, etc.)
    Optional `q` filters by symbol/name. `limit` caps results.
    """
    text = _download_master_csv()
    reader = csv.DictReader(io.StringIO(text))
    ql = (q or "").strip().lower()

    out: List[dict] = []
    for row in reader:
        if not _row_is_index(row):
            continue
        picked = _pick_fields(row)
        if ql:
            hay = " ".join([str(v or "") for v in picked.values()]).lower()
            if ql not in hay:
                continue
        out.append(picked)
        if len(out) >= limit:
            break

    return {"count": len(out), "data": out}
