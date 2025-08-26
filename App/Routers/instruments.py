# App/Routers/instruments.py
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
import requests, csv, io, time, re, os

router = APIRouter(prefix="/instruments", tags=["instruments"])

# ------- Config -------
CSV_URL = os.getenv(
    "INSTRUMENTS_URL",
    # fallback (agar env na ho to, optional)
    "https://images.dhan.co/api-data/api-script-master-detailed.csv",
)
CACHE_TTL_SECONDS = int(os.getenv("INSTRUMENTS_TTL", "21600"))  # 6 hours

# ------- Cache -------
_CACHE: Dict[str, Any] = {"rows": None, "ts": 0, "source": None}

# ------- Helpers -------
def _slug(s: str) -> str:
    """Normalize header names: lower + non-alnum -> underscore."""
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower())

def _now() -> float:
    return time.time()

def _fetch_csv_rows() -> List[Dict[str, Any]]:
    """Download + parse CSV, normalize headers, return list of dict rows."""
    # cache hit?
    if _CACHE["rows"] is not None and (_now() - _CACHE["ts"]) < CACHE_TTL_SECONDS:
        return _CACHE["rows"]

    # download
    resp = requests.get(CSV_URL, timeout=30)
    resp.raise_for_status()

    # parse
    content = resp.content.decode("utf-8-sig", errors="ignore")
    reader = csv.reader(io.StringIO(content))
    raw_headers = next(reader)
    # build header map
    norm_headers = [_slug(h) for h in raw_headers]

    rows: List[Dict[str, Any]] = []
    for raw in reader:
        if not raw:
            continue
        rec = {}
        for i, val in enumerate(raw):
            key = norm_headers[i] if i < len(norm_headers) else f"col_{i}"
            rec[key] = val.strip()
        # computed conveniences
        rec["_security_id"] = _coerce_int(
            rec.get("security_id") or rec.get("instrument_token") or rec.get("token")
        )
        rec["_exchange_segment"] = (
            rec.get("exchange_segment")
            or rec.get("segment")
            or rec.get("exchange")
            or ""
        ).strip().upper()

        # "name" style
        rec["_name"] = (
            rec.get("name")
            or rec.get("instrument_name")
            or rec.get("trading_symbol")
            or rec.get("symbol")
            or ""
        ).strip()

        rec["_symbol"] = (rec.get("symbol") or rec.get("trading_symbol") or "").strip()

        # instrument type (INDEX / EQ / FUTIDX / OPTIDX etc.)
        rec["_instrument_type"] = (
            rec.get("instrument_type") or rec.get("type") or ""
        ).strip().upper()

        # Heuristic: is index?
        seg = rec["_exchange_segment"]
        itype = rec["_instrument_type"]
        sym = rec["_symbol"].upper()
        name = rec["_name"].upper()
        rec["_is_index"] = (
            seg in {"IDX_I", "NSE_INDEX", "BSE_INDEX", "INDEX"}
            or "INDEX" in itype
            or ("NIFTY" in sym or "BANKNIFTY" in sym or "FINNIFTY" in sym or "SENSEX" in sym)
            or ("NIFTY" in name or "BANKNIFTY" in name or "FINNIFTY" in name or "SENSEX" in name)
        )

        rows.append(rec)

    _CACHE.update({"rows": rows, "ts": _now(), "source": CSV_URL})
    return rows

def _coerce_int(x: Optional[str]) -> Optional[int]:
    try:
        return int(str(x).strip())
    except Exception:
        return None

def _match_q(rec: Dict[str, Any], q: str) -> bool:
    if not q:
        return True
    q = q.lower()
    for k in ("_name", "_symbol"):
        v = (rec.get(k) or "").lower()
        if q in v:
            return True
    return False

def _pick(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Return compact fields for API."""
    return {
        "security_id": rec["_security_id"],
        "exchange_segment": rec["_exchange_segment"],
        "name": rec["_name"],
        "symbol": rec["_symbol"],
        "instrument_type": rec["_instrument_type"],
    }

# ------- Routes -------

@router.get("/indices")
def list_indices(
    q: str = Query(default="", description="filter by text (name/symbol)"),
    limit: int = Query(default=50, ge=1, le=500),
):
    """
    All indices (NIFTY/BANKNIFTY/FINNIFTY/SENSEX, etc.)
    """
    rows = _fetch_csv_rows()
    out = [_pick(r) for r in rows if r["_is_index"] and _match_q(r, q)]
    return {"count": len(out[:limit]), "data": out[:limit]}

@router.get("/search")
def search_instruments(
    q: str = Query(..., description="search text"),
    exchange_segment: Optional[str] = Query(None, description="e.g. NSE_EQ, IDX_I"),
    limit: int = Query(default=50, ge=1, le=500),
):
    """
    Generic text search across instruments. Optional exchange_segment filter.
    """
    ex = (exchange_segment or "").strip().upper()
    rows = _fetch_csv_rows()
    results: List[Dict[str, Any]] = []
    for r in rows:
        if ex and r["_exchange_segment"] != ex:
            continue
        if _match_q(r, q):
            results.append(_pick(r))

    # simple ranking: startswith > contains
    ql = q.lower()
    results.sort(
        key=lambda x: (
            0
            if (x["symbol"] or "").lower().startswith(ql) or (x["name"] or "").lower().startswith(ql)
            else 1,
            len(x["symbol"] or x["name"] or ""),
        )
    )
    return {"count": len(results[:limit]), "data": results[:limit]}

@router.get("/by-id")
def instrument_by_id(security_id: int = Query(..., description="exact security_id")):
    rows = _fetch_csv_rows()
    for r in rows:
        if r["_security_id"] == security_id:
            return {"data": _pick(r)}
    raise HTTPException(status_code=404, detail="Not Found")

@router.post("/_refresh")
def refresh_cache():
    _CACHE["rows"] = None
    _CACHE["ts"] = 0
    return {"ok": True, "msg": "cache cleared"}
