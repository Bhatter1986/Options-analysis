# App/Routers/optionchain_auto.py
from __future__ import annotations

import csv
import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..utils.seg_map import to_dhan_seg
from ..utils.dhan_api import (
    fetch_expirylist,
    fetch_optionchain,
)

router = APIRouter(prefix="/optionchain/auto", tags=["optionchain_auto"])

# Data locations
ROOT = Path(".")
DATA_DIR = ROOT / "data"
INSTRUMENTS_CSV = DATA_DIR / "instruments.csv"
SAVE_DIR = DATA_DIR / "optionchain"


# ---- Utilities ---------------------------------------------------------------

def _read_instruments(max_rows: Optional[int] = None) -> List[Dict[str, str]]:
    """
    Expect a CSV with headers including:
      security_id, symbol_name, underlying_symbol, segment, instrument_type
    """
    if not INSTRUMENTS_CSV.exists():
        raise HTTPException(status_code=500, detail=f"Missing {INSTRUMENTS_CSV}")

    out: List[Dict[str, str]] = []
    with INSTRUMENTS_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            out.append({k: (v or "").strip() for k, v in row.items()})
            if max_rows is not None and len(out) >= max_rows:
                break
    return out


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _symbol_dir(symbol: str) -> Path:
    d = SAVE_DIR / symbol
    _ensure_dir(d)
    return d


# ---- Endpoints ---------------------------------------------------------------

@router.get("/_debug")
def debug() -> Dict[str, Any]:
    return {
        "ok": True,
        "status": {
            "env": os.getenv("RENDER", "Render"),
            "mode": os.getenv("APP_MODE", "SANDBOX").upper(),
            "token_present": bool(os.getenv("DHAN_SAND_TOKEN") or os.getenv("DHAN_LIVE_TOKEN")),
            "client_id_present": bool(os.getenv("DHAN_SAND_CLIENT_ID") or os.getenv("DHAN_LIVE_CLIENT_ID")),
            "ai_present": bool(os.getenv("OPENAI_API_KEY")),
            "ai_model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            "base_url": os.getenv("DHAN_BASE_URL_SANDBOX") or os.getenv("DHAN_BASE_URL_LIVE") or "",
        },
        "instruments_csv": str(INSTRUMENTS_CSV),
        "instruments_exists": INSTRUMENTS_CSV.exists(),
        "optionchain_dir": str(SAVE_DIR),
    }


@router.get("/expirylist")
def build_expiry_lists(
    limit: int = Query(5, ge=1, le=1000, description="How many rows from instruments.csv")
) -> Dict[str, Any]:
    """
    For first `limit` instruments, fetch expiry list from Dhan and save:
      data/optionchain/<SYMBOL>/expiries.json

    Returns per-symbol status.
    """
    rows = _read_instruments(max_rows=limit)
    results: List[Dict[str, Any]] = []

    for row in rows:
        try:
            sec_id = int(row.get("security_id") or 0)
            seg_in_csv = row.get("segment") or ""
            symbol = row.get("symbol_name") or row.get("underlying_symbol") or f"SEC_{sec_id}"

            if not sec_id:
                raise ValueError("security_id missing")

            dhan_seg = to_dhan_seg(seg_in_csv)
            expiries = fetch_expirylist(sec_id, dhan_seg)

            # Save expiries
            out_path = _symbol_dir(symbol) / "expiries.json"
            with out_path.open("w", encoding="utf-8") as f:
                json.dump({"under_security_id": sec_id, "under_exchange_segment": dhan_seg, "expiries": expiries},
                          f, indent=2, ensure_ascii=False)

            results.append({"symbol": symbol, "security_id": sec_id, "segment": dhan_seg,
                            "expiries_saved": len(expiries), "path": str(out_path)})

        except Exception as e:
            results.append({"symbol": row.get("symbol_name"), "error": str(e)})

    return {"ok": True, "count": len(results), "results": results}


@router.post("/fetch")
def fetch_all_optionchains(
    use_all: bool = Query(True, description="Use all expiries (else only first)"),
    max_expiry: int = Query(1, ge=1, le=10, description="How many expiries per symbol if use_all"),
    limit: int = Query(0, ge=0, le=1000, description="Limit instruments processed (0 = all)"),
) -> Dict[str, Any]:
    """
    Reads each symbol's saved expiries.json and fetches optionchain JSONs.
    Writes to: data/optionchain/<SYMBOL>/<YYYY-MM-DD>.json
    """
    # Collect symbols with expiries.json
    if not SAVE_DIR.exists():
        raise HTTPException(status_code=500, detail=f"Missing dir: {SAVE_DIR}")

    symbols = sorted([p for p in SAVE_DIR.iterdir() if p.is_dir()])
    if limit > 0:
        symbols = symbols[:limit]

    results: List[Dict[str, Any]] = []

    for symdir in symbols:
        try:
            exp_path = symdir / "expiries.json"
            if not exp_path.exists():
                results.append({"symbol": symdir.name, "skipped": "no expiries.json"})
                continue

            meta = json.loads(exp_path.read_text(encoding="utf-8"))
            sec_id = int(meta["under_security_id"])
            seg = str(meta["under_exchange_segment"])
            expiries: List[str] = list(meta.get("expiries") or [])

            if not expiries:
                results.append({"symbol": symdir.name, "skipped": "no expiries"})
                continue

            target_expiries = expiries if use_all else expiries[:1]
            if use_all and max_expiry > 0:
                target_expiries = target_expiries[:max_expiry]

            fetched = 0
            for exp in target_expiries:
                chain = fetch_optionchain(sec_id, seg, exp)
                out_path = symdir / f"{exp}.json"
                with out_path.open("w", encoding="utf-8") as f:
                    json.dump(chain, f, indent=2, ensure_ascii=False)
                fetched += 1

            results.append({"symbol": symdir.name, "fetched": fetched})

        except Exception as e:
            results.append({"symbol": symdir.name, "error": str(e)})

    return {"ok": True, "count": len(results), "results": results}
