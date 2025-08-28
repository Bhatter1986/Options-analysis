# App/Routers/optionchain_auto.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..utils.seg_map import to_dhan_seg
from ..utils.dhan_api import (
    fetch_expirylist,
    fetch_optionchain,
)

router = APIRouter(prefix="/optionchain/auto", tags=["optionchain_auto"])

INSTRUMENTS_CSV = Path("data/instruments.csv")
OPTIONCHAIN_DIR = Path("data/optionchain")

# ---- Models ------------------------------------------------------------------

class ResultItem(BaseModel):
    symbol: str
    error: str = ""
    expiry: Optional[str] = None
    saved_at: Optional[str] = None
    contracts: Optional[int] = None

class FetchResponse(BaseModel):
    ok: bool = True
    count: int = 0
    results: List[ResultItem] = []

# ---- Utils -------------------------------------------------------------------

def _load_rows(limit: Optional[int] = None) -> List[Dict[str, str]]:
    if not INSTRUMENTS_CSV.exists():
        raise HTTPException(500, f"{INSTRUMENTS_CSV} not found")
    with INSTRUMENTS_CSV.open(newline="") as f:
        r = csv.DictReader(f)
        rows = list(r)
    if limit:
        rows = rows[: int(limit)]
    return rows

def _want_symbols_filter(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    want = {"NIFTY", "BANKNIFTY", "NIFTYNXT50", "FINNIFTY", "SENSEX"}
    return [r for r in rows if r.get("symbol_name") in want]

# ---- Endpoints ---------------------------------------------------------------

@router.get("/_debug")
def debug():
    return {
        "ok": True,
        "status": {
            "env": "true",
            "mode": "SANDBOX",
            "token_present": True,
            "client_id_present": True,
            "ai_present": False,
            "ai_model": "gpt-4.1-mini",
            "base_url": "",
        },
        "instruments_csv": str(INSTRUMENTS_CSV),
        "instruments_exists": INSTRUMENTS_CSV.exists(),
        "optionchain_dir": str(OPTIONCHAIN_DIR),
    }

@router.get("/expirylist")
def build_expiry_list(limit: int = Query(5, ge=1, le=50)):
    rows = _want_symbols_filter(_load_rows(limit=None))
    rows = rows[:limit]

    out: List[ResultItem] = []
    for row in rows:
        symbol = row["symbol_name"]
        seg_csv = row.get("segment", "")
        seg = to_dhan_seg(seg_csv)  # e.g. I -> IDX_I
        sec_id = int(row["security_id"])

        try:
            expiries = fetch_expirylist(sec_id, seg)  # returns list of YYYY-MM-DD
            out.append(ResultItem(symbol=symbol, error="", expiry=expiries[0] if expiries else None))
        except HTTPException as e:
            out.append(ResultItem(symbol=symbol, error=str(e.detail)))
        except Exception as e:
            out.append(ResultItem(symbol=symbol, error=str(e)))

    return {"ok": True, "count": len(out), "results": [r.dict() for r in out]}

@router.post("/fetch", response_model=FetchResponse)
def fetch_all(use_all: bool = True, max_expiry: int = 1):
    """
    For each wanted symbol:
    - get expiry list
    - pick nearest (first)
    - fetch optionchain for that expiry
    """
    rows = _want_symbols_filter(_load_rows(limit=None))
    results: List[ResultItem] = []

    for row in rows:
        symbol = row["symbol_name"]
        seg = to_dhan_seg(row.get("segment", ""))
        sec_id = int(row["security_id"])

        try:
            expiries = fetch_expirylist(sec_id, seg)
            if not expiries:
                results.append(ResultItem(symbol=symbol, error="No expiries"))
                continue

            expiry = expiries[0]  # nearest
            chain = fetch_optionchain(sec_id, seg, expiry)

            # (optional) save to disk if you want
            # OPTIONCHAIN_DIR.mkdir(parents=True, exist_ok=True)
            # (you can write json to file here if needed)

            contracts = len(chain) if isinstance(chain, list) else 0
            results.append(ResultItem(symbol=symbol, error="", expiry=expiry, contracts=contracts))

        except HTTPException as e:
            results.append(ResultItem(symbol=symbol, error=str(e.detail)))
        except Exception as e:
            results.append(ResultItem(symbol=symbol, error=str(e)))

        if not use_all and len(results) >= 1:
            break

    return FetchResponse(ok=True, count=len(results), results=results)
