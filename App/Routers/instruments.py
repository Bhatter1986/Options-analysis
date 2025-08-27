# App/Routers/instruments.py
import csv
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
import os

router = APIRouter(prefix="/instruments", tags=["instruments"])
log = logging.getLogger("instruments")

# -------- Config / CSV sources --------
INSTRUMENTS_URL = os.getenv(
    "INSTRUMENTS_URL",
    "https://images.dhan.co/api-data/api-script-master-detailed.csv",
)
CACHE_DIR = Path(os.getenv("CACHE_DIR", "/tmp"))
CSV_CACHE = CACHE_DIR / "instruments.csv"
CSV_TTL_SEC = int(os.getenv("INSTRUMENTS_TTL_SEC", "86400"))  # 24h

# config.json (repo root)
CONFIG_PATH = Path("config.json")
CONFIG_TTL_SEC = 60  # reload if changed within a minute

# -------- In-memory caches --------
_csv_rows: List[Dict[str, Any]] = []
_csv_loaded_at: float = 0.0
_config: Dict[str, Any] = {}
_config_loaded_at: float = 0.0
_config_mtime_seen: float = 0.0

# -------- Models --------
class RefreshResp(BaseModel):
    status: str
    csv_rows: int
    csv_source: str
    config_loaded: bool

# -------- Utilities --------
def _safe_lower(s: Any) -> str:
    return str(s or "").lower()

def _load_config(force: bool = False) -> Dict[str, Any]:
    """Load config.json with light caching; tolerate missing file."""
    global _config, _config_loaded_at, _config_mtime_seen
    try:
        mtime = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else 0.0
    except Exception:
        mtime = 0.0

    now = time.time()
    should_reload = (
        force
        or not _config
        or (mtime and mtime != _config_mtime_seen)
        or (now - _config_loaded_at > CONFIG_TTL_SEC)
    )

    if not should_reload:
        return _config

    if CONFIG_PATH.exists():
        try:
            _config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            _config_loaded_at = now
            _config_mtime_seen = mtime
            log.info("config.json loaded (%s)", CONFIG_PATH)
        except Exception as e:
            log.warning("config.json parse error: %s", e)
            _config = {}
            _config_loaded_at = now
            _config_mtime_seen = mtime
    else:
        _config = {}
        _config_loaded_at = now
        _config_mtime_seen = mtime
        log.info("config.json not found; continuing with empty config")

    return _config

def _download_csv_if_stale(force: bool = False) -> Path:
    """Ensure CSV cache is present/fresh."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    age = time.time() - CSV_CACHE.stat().st_mtime if CSV_CACHE.exists() else 10**9
    if (not force) and CSV_CACHE.exists() and age < CSV_TTL_SEC:
        return CSV_CACHE

    log.info("Downloading instruments CSV: %s", INSTRUMENTS_URL)
    r = requests.get(INSTRUMENTS_URL, timeout=30)
    r.raise_for_status()
    CSV_CACHE.write_bytes(r.content)
    log.info("Saved instruments to %s (%d bytes)", CSV_CACHE, len(r.content))
    return CSV_CACHE

def _load_csv_into_memory(force: bool = False) -> int:
    """Load CSV rows into memory once; return count."""
    global _csv_rows, _csv_loaded_at
    path = _download_csv_if_stale(force=force)
    rows: List[Dict[str, Any]] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    _csv_rows = rows
    _csv_loaded_at = time.time()
    log.info("CSV loaded into memory: %s rows=%d", path, len(rows))
    return len(rows)

def _ensure_loaded():
    if not _csv_rows:
        _load_csv_into_memory(force=False)
    _load_config(force=False)

def _is_index_row(row: Dict[str, Any]) -> bool:
    # Dhan master CSV usually: segment 'I' for indices or instrument_type 'INDEX'
    seg = str(row.get("segment") or row.get("exchange_segment") or "").upper()
    itype = str(row.get("instrument_type") or "").upper()
    return seg == "I" or itype == "INDEX"

def _row_matches_q(row: Dict[str, Any], q: str) -> bool:
    if not q:
        return True
    hay = " ".join([
        str(row.get("symbol_name") or row.get("symbol") or ""),
        str(row.get("trading_symbol") or ""),
        str(row.get("underlying_symbol") or ""),
        str(row.get("security_id") or ""),
        str(row.get("isin") or ""),
        str(row.get("name") or ""),
    ]).lower()
    return q in hay

# -------- Endpoints --------
@router.get("/_debug")
def instruments_debug():
    _ensure_loaded()
    src = str(CSV_CACHE) if CSV_CACHE.exists() else "(mem)"
    cfg = _load_config()
    return {
        "status": "ok",
        "csv": {
            "rows": len(_csv_rows),
            "cache_path": src,
            "loaded_at": _csv_loaded_at,
            "url": INSTRUMENTS_URL,
            "ttl_sec": CSV_TTL_SEC,
        },
        "config": {
            "present": bool(cfg),
            "watchlists_keys": list((cfg.get("watchlists") or {}).keys()),
            "filters_keys": list((cfg.get("filters") or {}).keys()),
            "path": str(CONFIG_PATH.resolve()),
            "loaded_at": _config_loaded_at,
        },
    }

@router.post("/_refresh", response_model=RefreshResp)
def instruments_refresh(force: bool = Query(True)):
    csv_count = _load_csv_into_memory(force=force)
    cfg = _load_config(force=True)
    return RefreshResp(
        status="refreshed",
        csv_rows=csv_count,
        csv_source=str(CSV_CACHE),
        config_loaded=bool(cfg),
    )

@router.get("")
def instruments_sample(limit: int = Query(50, ge=1, le=500)):
    _ensure_loaded()
    return {"data": _csv_rows[:limit], "count": min(limit, len(_csv_rows))}

@router.get("/watchlists")
def instruments_watchlists():
    cfg = _load_config()
    return {"watchlists": cfg.get("watchlists") or {}}

@router.get("/indices")
def instruments_indices(q: str = Query("", description="text filter"), limit: int = Query(100, ge=1, le=1000)):
    _ensure_loaded()
    qq = q.strip().lower()
    out: List[Dict[str, Any]] = []
    for row in _csv_rows:
        if not _is_index_row(row):
            continue
        if qq and not _row_matches_q(row, qq):
            continue
        out.append({
            "security_id": row.get("security_id"),
            "symbol_name": row.get("symbol_name") or row.get("symbol"),
            "underlying_symbol": row.get("underlying_symbol"),
            "segment": row.get("segment") or row.get("exchange_segment"),
            "instrument_type": row.get("instrument_type"),
        })
        if len(out) >= limit:
            break
    return {"data": out, "count": len(out)}

@router.get("/search")
def instruments_search(q: str = Query(..., description="free text"), limit: int = Query(100, ge=1, le=1000)):
    _ensure_loaded()
    qq = q.strip().lower()
    out: List[Dict[str, Any]] = []
    for row in _csv_rows:
        if _row_matches_q(row, qq):
            out.append(row)
            if len(out) >= limit:
                break
    return {"data": out, "count": len(out)}

@router.get("/by-id")
def instruments_by_id(security_id: str = Query(...)):
    _ensure_loaded()
    for row in _csv_rows:
        if str(row.get("security_id")) == str(security_id):
            return {"data": row}
    raise HTTPException(status_code=404, detail="security_id not found")
