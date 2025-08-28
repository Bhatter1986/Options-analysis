from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
import pandas as pd, json

from App.utils.dhan_api import fetch_expirylist, fetch_optionchain
from App.utils.seg_map import to_dhan_seg

router = APIRouter(prefix="/optionchain/auto", tags=["optionchain-auto"])

CSV_PATH  = Path("data/instruments.csv")
SAVE_DIR  = Path("data/optionchain")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

def load_instruments():
    if not CSV_PATH.exists():
        raise HTTPException(503, "instruments.csv missing")
    df = pd.read_csv(CSV_PATH, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def payload_from_row(row):
    seg = to_dhan_seg(row["instrument_type"], row["segment"])
    if not seg:
        return None
    return int(row["security_id"]), seg

@router.get("/_debug")
def debug_status():
    return {
        "ok": True,
        "instruments_csv": str(CSV_PATH),
        "instruments_exists": CSV_PATH.exists(),
        "optionchain_dir": str(SAVE_DIR),
    }

@router.get("/expirylist")
def all_expirylist(limit: int = Query(5, ge=1, le=100)):
    df = load_instruments().head(limit)
    results = []
    for _, row in df.iterrows():
        pl = payload_from_row(row)
        if not pl: continue
        sid, seg = pl
        try:
            expiries = fetch_expirylist(sid, seg)
            sym = row["symbol_name"]
            ddir = SAVE_DIR / sym
            ddir.mkdir(parents=True, exist_ok=True)
            with open(ddir / "expiries.json", "w") as f:
                json.dump(expiries, f, indent=2)
            results.append({"symbol": sym, "expiries": expiries})
        except Exception as e:
            results.append({"symbol": row["symbol_name"], "error": str(e)})
    return {"ok": True, "count": len(results), "results": results}

@router.post("/fetch")
def fetch_chains(use_all: bool = True, max_expiry: int = Query(1, ge=1, le=5)):
    df = load_instruments() if use_all else pd.DataFrame()
    results = []
    for _, row in df.iterrows():
        pl = payload_from_row(row)
        if not pl: continue
        sid, seg = pl
        sym = row["symbol_name"]
        ddir = SAVE_DIR / sym
        exp_file = ddir / "expiries.json"
        if not exp_file.exists():
            results.append({"symbol": sym, "error": "no expiries.json"})
            continue
        expiries = json.load(open(exp_file))[:max_expiry]
        fetched = []
        for e in expiries:
            try:
                data = fetch_optionchain(sid, seg, e)
                with open(ddir / f"{e}.json", "w") as f:
                    json.dump(data, f, indent=2)
                fetched.append(e)
            except Exception as er:
                fetched.append({"expiry": e, "error": str(er)})
        results.append({"symbol": sym, "fetched": fetched})
    return {"ok": True, "count": len(results), "results": results}
