# App/Routers/instruments.py
import os
import io
import csv
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

import requests
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("instruments")

router = APIRouter(prefix="/instruments", tags=["instruments"])

# ---- Config ----
INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-script-master-detailed.csv",
)
# Render allows writing to /tmp
INSTRUMENTS_CACHE = Path(os.getenv("INSTRUMENTS_CACHE", "/tmp/instruments.csv"))

# ---- In-memory cache ----
_cache: Dict[str, Any] = {
    "rows": [],          # list[dict] (entire CSV)
    "cols": [],          # list[str] (fieldnames)
    "by_id": {},         # dict[str, dict]  (security_id -> row)
    "indices": [],       # list[dict] subset
    "ready": False,
}


# ---------- helpers ----------
def _download_to_cache() -> None:
    """Download the instruments CSV to the local cache path."""
    logger.info("Downloading instruments CSV from %s", INSTRUMENTS_URL)
    try:
        r = requests.get(INSTRUMENTS_URL, timeout=60)
        r.raise_for_status()
    except Exception as e:
        logger.exception("Failed to download CSV")
        raise HTTPException(status_code=502, detail=f"Download failed: {e}")

    INSTRUMENTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    INSTRUMENTS_CACHE.write_bytes(r.content)
    logger.info("CSV saved to %s (%s bytes)", INSTRUMENTS_CACHE, INSTRUMENTS_CACHE.stat().st_size)


def _load_from_path(path: Path) -> None:
    """Load CSV rows from path into _cache."""
    if not path.is_file():
        raise FileNotFoundError(str(path))

    with path.open("rb") as f:
        raw = f.read()

    # auto-detect encoding via utf-8 fallback
    text = raw.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict[str, Any]] = [dict(r) for r in reader]
    cols: List[str] = list(reader.fieldnames or [])

    # Normalize some commonly-used columns (keep original keys too)
    def norm(v: Optional[str]) -> str:
        return (v or "").strip()

    for r in rows:
        r["security_id"] = norm(r.get("security_id") or r.get("securityId"))
        r["symbol_name"] = norm(r.get("symbol_name") or r.get("symbolName"))
        r["underlying_symbol"] = norm(r.get("underlying_symbol") or r.get("underlyingSymbol"))
        r["segment"] = norm(r.get("segment"))
        r["instrument_type"] = norm(r.get("instrument_type") or r.get("instrumentType"))

    by_id = {r["security_id"]: r for r in rows if r.get("security_id")}
    # Heuristic for indices: segment == 'I' or instrument_type == 'INDEX'
    indices = [r for r in rows if r.get("segment") == "I" or r.get("instrument_type") == "INDEX"]

    _cache.update({
        "rows": rows,
        "cols": cols,
        "by_id": by_id,
        "indices": indices,
        "ready": True,
    })
    logger.info("Loaded %d rows (%d index rows).", len(rows), len(indices))


def _ensure_loaded() -> None:
    """Make sure _cache is ready (download if needed)."""
    if _cache.get("ready") and _cache["rows"]:
        return

    # Prefer cached file if present, else download
    if not INSTRUMENTS_CACHE.is_file():
        _download_to_cache()

    _load_from_path(INSTRUMENTS_CACHE)


def _paginate(items: List[Dict[str, Any]], limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    if offset < 0:
        offset = 0
    if limit <= 0:
        limit = 50
    return items[offset: offset + limit]


# ---------- routes ----------
@router.get("/_debug")
def debug():
    exists = INSTRUMENTS_CACHE.is_file()
    rows = len(_cache.get("rows") or [])
    return {
        "exists": exists,
        "path": str(INSTRUMENTS_CACHE),
        "rows": rows,
        "cols": _cache.get("cols") or [],
        "ready": bool(_cache.get("ready")),
        "url": INSTRUMENTS_URL,
    }


@router.post("/_refresh")
def refresh():
    # force re-download + reload
    _cache.update({"rows": [], "cols": [], "by_id": {}, "indices": [], "ready": False})
    _download_to_cache()
    _load_from_path(INSTRUMENTS_CACHE)
    return {"status": "ok", "rows": len(_cache["rows"])}


@router.get("")
def list_instruments(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    _ensure_loaded()
    data = _paginate(_cache["rows"], limit, offset)
    return {"data": data, "count": len(data)}


@router.get("/indices")
def list_indices(q: Optional[str] = None, limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)):
    _ensure_loaded()
    rows = _cache["indices"]
    if q:
        ql = q.lower()
        rows = [
            r for r in rows
            if ql in (r.get("symbol_name", "").lower())
            or ql in (r.get("underlying_symbol", "").lower())
        ]
    data = _paginate(rows, limit, offset)
    return {"data": data, "count": len(data)}


@router.get("/search")
def search(q: str, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    """Simple substring search across symbol_name / underlying_symbol / security_id."""
    _ensure_loaded()
    ql = q.lower().strip()
    rows = [
        r for r in _cache["rows"]
        if ql in r.get("symbol_name", "").lower()
        or ql in r.get("underlying_symbol", "").lower()
        or ql == r.get("security_id", "").lower()
    ]
    data = _paginate(rows, limit, offset)
    return {"data": data, "count": len(rows)}


@router.get("/by-id")
def by_id(security_id: str = Query(..., description="Exact security_id")):
    _ensure_loaded()
    row = _cache["by_id"].get(str(security_id))
    if not row:
        raise HTTPException(status_code=404, detail="Not Found")
    return row
