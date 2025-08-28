# App/Routers/optionchain_auto.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
import json
import time
from datetime import date, timedelta

from App.utils.seg_map import to_dhan_seg

router = APIRouter(prefix="/optionchain/auto", tags=["optionchain-auto"])

CSV_PATH = Path("data/instruments.csv")
SAVE_DIR = Path("data/optionchain")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

def _load_instruments() -> pd.DataFrame:
    if not CSV_PATH.exists():
        raise HTTPException(503, "instruments.csv missing")
    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False, na_filter=False)
    df.columns = [c.strip().lower() for c in df.columns]
    need = ["security_id","symbol_name","underlying_symbol","segment","instrument_type"]
    for n in need:
        if n not in df.columns:
            raise HTTPException(500, f"instruments.csv missing column: {n}")
    return df

def _payload_from_row(row: pd.Series) -> Dict[str, Any] | None:
    seg = to_dhan_seg(row["instrument_type"], row["segment"])
    if not seg:
        return None
    # Dhan expects int; we keep string and cast when needed
    return {
        "UnderlyingScrip": int(row["security_id"]),
        "UnderlyingSeg": seg,
        "Symbol": row["symbol_name"],
    }

# ---------------- SANDBOX MOCK HELPERS ----------------

def _next_weeklies(n: int = 4) -> List[str]:
    """Simple weekly expiries: next 4 Wednesdays (or Thursdays) for demo."""
    out = []
    d = date.today()
    # find upcoming Wednesday (2) or Thursday (3); choose Wed here
    target_wd = 2
    while d.weekday() != target_wd:
        d += timedelta(days=1)
    for _ in range(n):
        out.append(d.isoformat())
        d += timedelta(days=7)
    return out

def _mock_expirylist() -> Dict[str, Any]:
    return {"data": _next_weeklies(4), "status": "success"}

def _mock_chain() -> Dict[str, Any]:
    # Minimal but realistic structure (matches your SANDBOX responses)
    base = 25000.0
    strikes = [24800, 24900, 25000, 25100, 25200]
    oc: Dict[str, Any] = {}
    for k, s in enumerate(strikes):
        oc[str(s)] = {
            "ce": {
                "greeks": {
                    "delta": round(0.30 + 0.01*k, 5),
                    "theta": round(-10 - k, 5),
                    "gamma": round(0.0008 + 0.0001*k, 5),
                    "vega": round(10 + k, 5),
                },
                "implied_volatility": round(12 + 2*k, 2),
                "last_price": round(80 + 10*k, 2),
                "oi": 10000 + 1000*k,
                "previous_close_price": round(78 + 10*k, 2),
                "previous_oi": 7000 + 800*k,
                "previous_volume": 100000 + 10000*k,
                "top_ask_price": round(79 + 10*k, 2),
                "top_ask_quantity": 250,
                "top_bid_price": round(78 + 10*k, 2),
                "top_bid_quantity": 250,
                "volume": 500000 + 50000*k,
            },
            "pe": {
                "greeks": {
                    "delta": round(-0.30 - 0.01*k, 5),
                    "theta": round(-10 - k, 5),
                    "gamma": round(0.0008 + 0.0001*k, 5),
                    "vega": round(11 + k, 5),
                },
                "implied_volatility": round(15 + 2*k, 2),
                "last_price": round(85 + 8*k, 2),
                "oi": 12000 + 1100*k,
                "previous_close_price": round(86 + 8*k, 2),
                "previous_oi": 8000 + 900*k,
                "previous_volume": 120000 + 9000*k,
                "top_ask_price": round(84 + 8*k, 2),
                "top_ask_quantity": 250,
                "top_bid_price": round(83 + 8*k, 2),
                "top_bid_quantity": 250,
                "volume": 400000 + 40000*k,
            },
        }
    return {"data": {"last_price": base, "oc": oc}}

# ---------------- ENDPOINTS ----------------

@router.get("/_debug")
def auto_debug() -> Dict[str, Any]:
    return {
        "instruments_csv": str(CSV_PATH),
        "exists": CSV_PATH.exists(),
        "save_dir": str(SAVE_DIR),
        "mode": "SANDBOX-auto",
    }

@router.get("/expirylist")
def all_expirylist(q: str | None = Query(None), limit: int = Query(0, ge=0, le=500)):
    """
    SANDBOX: generate expiries and save for each supported underlying (indices).
    Saves: data/optionchain/<SYMBOL>/expiries.json
    """
    df = _load_instruments()
    if q:
        qq = q.lower()
        df = df[df["symbol_name"].str.lower().str.contains(qq) |
                df["underlying_symbol"].str.lower().str.contains(qq)]
    if limit:
        df = df.head(limit)

    items = []
    for _, row in df.iterrows():
        pl = _payload_from_row(row)
        if not pl:
            # skip unmapped segment/type (e.g., equities until we fill SEG_MAP)
            continue
        sym = row["symbol_name"]
        ddir = SAVE_DIR / sym
        ddir.mkdir(parents=True, exist_ok=True)
        data = _mock_expirylist()
        with open(ddir / "expiries.json", "w") as f:
            json.dump(data, f, indent=2)
        items.append({"symbol": sym, "saved": "expiries.json", "count": len(data.get("data", []))})
        time.sleep(0.05)  # tiny sleep; real LIVE will use 3s
    return {"items": items}

@router.post("/fetch")
def fetch_optionchains(
    symbols: List[str] | None = None,
    use_all: bool = False,
    max_expiry: int = Query(1, ge=1, le=10),
):
    """
    SANDBOX: read saved expiries.json for each symbol, write one or more expiry files.
    Saves: data/optionchain/<SYMBOL>/<YYYY-MM-DD>.json
    """
    df = _load_instruments()
    if not use_all and not symbols:
        raise HTTPException(400, "Provide symbols or set use_all=true")

    if not use_all:
        df = df[df["symbol_name"].isin(symbols)]

    results = []
    for _, row in df.iterrows():
        pl = _payload_from_row(row)
        if not pl:
            continue
        sym = row["symbol_name"]
        ddir = SAVE_DIR / sym
        exp_file = ddir / "expiries.json"
        if not exp_file.exists():
            results.append({"symbol": sym, "status": "skip", "detail": "expiries.json missing; call /auto/expirylist first"})
            continue
        exp = json.loads(exp_file.read_text()).get("data", [])
        exp = exp[:max_expiry]
        fetched = []
        for e in exp:
            data = _mock_chain()
            with open(ddir / f"{e}.json", "w") as f:
                json.dump(data, f,
