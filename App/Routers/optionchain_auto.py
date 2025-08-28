# App/Routers/optionchain_auto.py
from __future__ import annotations
from fastapi import APIRouter, Query, HTTPException
from pathlib import Path
import pandas as pd
import json

from App.utils.dhan_api import call_dhan_api, dhan_sleep
from App.utils.seg_map import to_dhan_seg

router = APIRouter(prefix="/optionchain/auto", tags=["optionchain-auto"])

CSV_PATH = Path("data/instruments.csv")
SAVE_DIR = Path("data/optionchain")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

def load_instruments() -> pd.DataFrame:
    if not CSV_PATH.exists():
        raise HTTPException(503, "instruments.csv missing")
    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False, na_filter=False)
    df.columns = [c.strip().lower() for c in df.columns]
    need = ["security_id","symbol_name","underlying_symbol","segment","instrument_type"]
    for n in need:
        if n not in df.columns:
            raise HTTPException(500, f"instruments.csv missing column: {n}")
    return df

def payload_from_row(row: pd.Series) -> dict | None:
    seg = to_dhan_seg(row["instrument_type"], row["segment"])
    if not seg:
        return None
    try:
        sid = int(str(row["security_id"]).strip())
    except ValueError:
        return None
    return {"UnderlyingScrip": sid, "UnderlyingSeg": seg}

@router.get("/expirylist")
def all_expirylist(q: str | None = Query(None), limit: int = Query(0, ge=0, le=500)):
    """
    Pull expirylist for ALL (or filtered) underlyings.
    Saves: data/optionchain/<SYMBOL>/expiries.json
    """
    df = load_instruments()
    if q:
        qq = q.lower()
        df = df[df["symbol_name"].str.lower().str.contains(qq) |
                df["underlying_symbol"].str.lower().str.contains(qq)]
    if limit and limit > 0:
        df = df.head(limit)

    items = []
    for _, row in df.iterrows():
        sym = row["symbol_name"]
        pl = payload_from_row(row)
        if not pl:
            items.append({"symbol": sym, "status": "skip_no_seg"})
            continue
        try:
            res = call_dhan_api("/optionchain/expirylist", pl)
            ddir = SAVE_DIR / sym
            ddir.mkdir(parents=True, exist_ok=True)
            with open(ddir / "expiries.json", "w") as f:
                json.dump(res, f, indent=2)
            items.append({"symbol": sym, "status": "ok", "count": len(res.get("data", []))})
        except HTTPException as e:
            items.append({"symbol": sym, "status": "err", "detail": str(e)})
        dhan_sleep()
    return {"items": items}

@router.post("/fetch")
def fetch_optionchains(
    symbols: list[str] | None = None,
    use_all: bool = False,
    max_expiry: int = Query(1, ge=1, le=10)
):
    """
    For given symbols (or ALL), read expiries.json & fetch optionchain for N expiries.
    Saves: data/optionchain/<SYMBOL>/<YYYY-MM-DD>.json
    """
    df = load_instruments()
    if not use_all and not symbols:
        raise HTTPException(400, "Provide symbols or set use_all=true")
    if not use_all:
        df = df[df["symbol_name"].isin(symbols)]

    results = []
    for _, row in df.iterrows():
        sym = row["symbol_name"]
        pl = payload_from_row(row)
        if not pl:
            results.append({"symbol": sym, "status": "skip_no_seg"})
            continue

        ddir = SAVE_DIR / sym
        exp_file = ddir / "expiries.json"
        if not exp_file.exists():
            results.append({"symbol": sym, "status": "skip_no_expiries", "detail": "call /auto/expirylist first"})
            continue

        with open(exp_file) as f:
            exps = (json.load(f) or {}).get("data", [])
        exps = exps[:max_expiry]

        fetched = []
        for e in exps:
            body = {**pl, "Expiry": e}
            try:
                res = call_dhan_api("/optionchain", body)
                with open(ddir / f"{e}.json", "w") as f:
                    json.dump(res, f, indent=2)
                fetched.append(e)
            except HTTPException as er:
                fetched.append({"expiry": e, "err": str(er)})
            dhan_sleep()
        results.append({"symbol": sym, "fetched": fetched})
    return {"ok": True, "results": results}
