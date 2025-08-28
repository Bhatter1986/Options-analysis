# App/Routers/optionchain_auto.py

from __future__ import annotations
from fastapi import APIRouter, Query, HTTPException
from pathlib import Path
import pandas as pd
import json, time

from App.utils.dhan_api import call_dhan_api, dhan_sleep
from App.utils.seg_map import to_dhan_seg

router = APIRouter(prefix="/optionchain/auto", tags=["optionchain-auto"])

# Paths
CSV_PATH = Path("data/instruments.csv")
SAVE_DIR = Path("data/optionchain")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Helpers ----------
def load_instruments() -> pd.DataFrame:
    """Load instruments.csv into DataFrame."""
    if not CSV_PATH.exists():
        raise HTTPException(503, "instruments.csv missing")
    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False, na_filter=False)
    df.columns = [c.strip().lower() for c in df.columns]

    required = ["security_id", "symbol_name", "underlying_symbol", "segment", "instrument_type"]
    for col in required:
        if col not in df.columns:
            raise HTTPException(500, f"instruments.csv missing column: {col}")
    return df

def payload_from_row(row: pd.Series) -> dict | None:
    """Convert instruments.csv row to Dhan payload."""
    seg = to_dhan_seg(row["instrument_type"], row["segment"])
    if not seg:
        return None
    return {
        "UnderlyingScrip": int(row["security_id"]),  # Dhan expects int
        "UnderlyingSeg": seg,
    }

def write_json(path: Path, data: dict) -> None:
    """Safe JSON writer with auto dir creation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ---------- Routes ----------
@router.get("/_debug")
def debug_info():
    """Debug info for optionchain automation."""
    return {
        "instruments_csv": str(CSV_PATH),
        "instruments_exists": CSV_PATH.exists(),
        "optionchain_dir": str(SAVE_DIR),
    }

@router.get("/expirylist")
def all_expirylist(q: str | None = Query(None), limit: int = Query(0, ge=0, le=500)):
    """
    Pull expirylist for ALL (or filtered) underlyings.
    Saves per symbol: data/optionchain/<SYMBOL>/expiries.json
    """
    df = load_instruments()

    if q:
        qlow = q.lower()
        df = df[df["symbol_name"].str.lower().str.contains(qlow) |
                df["underlying_symbol"].str.lower().str.contains(qlow)]

    if limit and limit > 0:
        df = df.head(limit)

    out = []
    for _, row in df.iterrows():
        pl = payload_from_row(row)
        if not pl:
            continue
        try:
            res = call_dhan_api("/optionchain/expirylist", pl)
            sym = row["symbol_name"]
            ddir = SAVE_DIR / sym
            write_json(ddir / "expiries.json", res)
            out.append({
                "symbol": sym,
                "payload": pl,
                "status": "ok",
                "count": len(res.get("data", []))
            })
        except Exception as e:
            out.append({
                "symbol": row["symbol_name"],
                "payload": pl,
                "status": "err",
                "detail": str(e)
            })
        dhan_sleep()
    return {"items": out}

@router.post("/fetch")
def fetch_optionchains(
    symbols: list[str] | None = None,
    use_all: bool = False,
    max_expiry: int = Query(1, ge=1, le=10)
):
    """
    For given symbols (or ALL), read expiries.json and fetch optionchain for N expiries.
    Saves: data/optionchain/<SYMBOL>/<YYYY-MM-DD>.json
    """
    df = load_instruments()
    if not use_all and not symbols:
        raise HTTPException(400, "Provide symbols or set use_all=true")

    if not use_all:
        df = df[df["symbol_name"].isin(symbols)]

    results = []
    for _, row in df.iterrows():
        pl = payload_from_row(row)
        if not pl:
            continue
        sym = row["symbol_name"]
        ddir = SAVE_DIR / sym
        exp_file = ddir / "expiries.json"

        if not exp_file.exists():
            results.append({
                "symbol": sym,
                "status": "skip",
                "detail": "expiries.json missing; call /auto/expirylist first"
            })
            continue

        expiries = []
        try:
            with open(exp_file, encoding="utf-8") as f:
                expiries = json.load(f).get("data", [])
        except Exception as e:
            results.append({"symbol": sym, "status": "err", "detail": f"bad exp file: {e}"})
            continue

        expiries = expiries[:max_expiry]
        fetched = []
        for e in expiries:
            body = {**pl, "Expiry": e}
            try:
                res = call_dhan_api("/optionchain", body)
                write_json(ddir / f"{e}.json", res)
                fetched.append(e)
            except Exception as er:
                fetched.append({"expiry": e, "err": str(er)})
            dhan_sleep()

        results.append({"symbol": sym, "fetched": fetched})
    return {"ok": True, "results": results}
