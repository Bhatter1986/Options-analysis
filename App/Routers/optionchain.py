# App/Routers/optionchain.py
from __future__ import annotations

import os, json, time, random
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/optionchain", tags=["option-chain"])

# -----------------------------
# ENV / CONFIG
# -----------------------------
APP_MODE = os.getenv("APP_MODE", "SANDBOX").upper()  # SANDBOX or LIVE
DHAN_BASE = "https://api.dhan.co/v2"
DHAN_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")

DATA_DIR = Path("data")
INSTR_CSV = DATA_DIR / "instruments.csv"
OC_ROOT   = DATA_DIR / "optionchain"   # <SYMBOL>/expiries.json, <SYMBOL>/<YYYY-MM-DD>.json
OC_ROOT.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Helpers
# -----------------------------
def _dhan_headers() -> Dict[str, str]:
    if not DHAN_TOKEN or not DHAN_CLIENT_ID:
        raise HTTPException(500, detail="Missing DHAN_ACCESS_TOKEN or DHAN_CLIENT_ID")
    return {
        "access-token": DHAN_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json",
    }

def _dhan_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{DHAN_BASE}{path}"
    resp = requests.post(url, headers=_dhan_headers(), json=payload, timeout=20)
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, detail=f"{path} failed: {resp.text}")
    return resp.json()

def _load_instruments() -> pd.DataFrame:
    if not INSTR_CSV.exists():
        raise HTTPException(503, detail="instruments.csv not found on server")
    df = pd.read_csv(INSTR_CSV, dtype=str, keep_default_na=False, na_filter=False)
    df.columns = [c.strip().lower() for c in df.columns]
    need = ["security_id", "symbol_name", "underlying_symbol", "segment", "instrument_type"]
    for n in need:
        if n not in df.columns:
            raise HTTPException(500, detail=f"instruments.csv missing column '{n}'")
    return df

def _symbol_for_sid(security_id: str) -> Optional[str]:
    try:
        df = _load_instruments()
    except HTTPException:
        return None
    hit = df[df["security_id"] == str(security_id)]
    if hit.empty:
        return None
    # prefer symbol_name; fallback to underlying_symbol
    sym = hit.iloc[0]["symbol_name"] or hit.iloc[0]["underlying_symbol"]
    return (sym or "").strip() or None

def _sandbox_expiries(security_id: str) -> List[str]:
    """If we have saved expiries file, return that. Else generate some weekly dates."""
    sym = _symbol_for_sid(security_id) or security_id
    exp_file = OC_ROOT / sym / "expiries.json"
    if exp_file.exists():
        try:
            return (json.loads(exp_file.read_text()) or {}).get("data", [])
        except Exception:
            pass
    # fallback mock: 4 weekly Wednesdays ahead
    today = pd.Timestamp.utcnow().normalize()
    out = []
    d = today + pd.Timedelta(days=1)
    while len(out) < 4:
        if d.weekday() in (2, 3):  # Wed/Thu
            out.append(str(d.date()))
        d += pd.Timedelta(days=1)
    return out

def _sandbox_chain(security_id: str, expiry: str) -> Dict[str, Any]:
    """
    If we have a saved file data/optionchain/<SYMBOL>/<expiry>.json, return that.
    Else generate small synthetic OC around a center strike.
    """
    sym = _symbol_for_sid(security_id) or security_id
    ddir = OC_ROOT / sym
    f = ddir / f"{expiry}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass

    # tiny synthetic chain
    center = 25000  # arbitrary center
    strikes = [center - 200, center - 100, center, center + 100, center + 200]
    oc = {}
    for k in strikes:
        ce_iv = round(random.uniform(12, 22), 2)
        pe_iv = round(random.uniform(12, 22), 2)
        ce_lp = round(random.uniform(80, 160), 2)
        pe_lp = round(random.uniform(80, 160), 2)
        oc[str(k)] = {
            "ce": {
                "greeks": {"delta": round(random.uniform(0.3, 0.7), 5),
                           "theta": round(random.uniform(-15, -5), 5),
                           "gamma": round(random.uniform(0.0008, 0.002), 5),
                           "vega":  round(random.uniform(8, 16), 5)},
                "implied_volatility": ce_iv,
                "last_price": ce_lp,
                "oi": random.randint(5000, 25000),
                "previous_close_price": round(ce_lp * random.uniform(0.9, 1.1), 2),
                "previous_oi": random.randint(4000, 20000),
                "previous_volume": random.randint(50_000, 2_000_000),
                "top_ask_price": round(ce_lp - 1, 2),
                "top_ask_quantity": 250,
                "top_bid_price": round(ce_lp - 2, 2),
                "top_bid_quantity": 250,
                "volume": random.randint(100_000, 5_000_000),
            },
            "pe": {
                "greeks": {"delta": round(random.uniform(-0.7, -0.3), 5),
                           "theta": round(random.uniform(-15, -5), 5),
                           "gamma": round(random.uniform(0.0008, 0.002), 5),
                           "vega":  round(random.uniform(8, 16), 5)},
                "implied_volatility": pe_iv,
                "last_price": pe_lp,
                "oi": random.randint(5000, 25000),
                "previous_close_price": round(pe_lp * random.uniform(0.9, 1.1), 2),
                "previous_oi": random.randint(4000, 20000),
                "previous_volume": random.randint(50_000, 2_000_000),
                "top_ask_price": round(pe_lp - 1, 2),
                "top_ask_quantity": 250,
                "top_bid_price": round(pe_lp - 2, 2),
                "top_bid_quantity": 250,
                "volume": random.randint(100_000, 5_000_000),
            },
        }
    return {"data": {"last_price": float(center), "oc": oc}}

# -----------------------------
# DEBUG
# -----------------------------
@router.get("/_debug")
def oc_debug() -> Dict[str, Any]:
    exists = INSTR_CSV.exists()
    return {
        "mode": APP_MODE,
        "dhan_env_ok": bool(DHAN_TOKEN) and bool(DHAN_CLIENT_ID),
        "instruments_csv": str(INSTR_CSV),
        "instruments_exists": exists,
        "optionchain_dir": str(OC_ROOT),
    }

# -----------------------------
# EXPIRY LIST  (POST body — exact Dhan shape)
# -----------------------------
@router.post("/expirylist")
def expirylist_post(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Dhan shape:
    {
      "UnderlyingScrip": 25,           # int
      "UnderlyingSeg": "IDX_I"         # e.g. indices segment
    }
    """
    u = payload.get("UnderlyingScrip")
    seg = payload.get("UnderlyingSeg")
    if u is None or seg is None:
        raise HTTPException(400, detail="UnderlyingScrip and UnderlyingSeg required")

    # LIVE → call Dhan
    if APP_MODE == "LIVE":
        return _dhan_post("/optionchain/expirylist", {"UnderlyingScrip": int(u), "UnderlyingSeg": str(seg)})

    # SANDBOX → local or mock
    data = _sandbox_expiries(str(u))
    return {"data": data, "status": "success"}

# -----------------------------
# EXPIRY LIST  (GET wrapper — convenient)
# -----------------------------
@router.get("/expirylist")
def expirylist_get(
    under_security_id: int = Query(..., description="Underlying security_id"),
    under_exchange_segment: str = Query(..., description="Segment e.g. IDX_I"),
):
    return expirylist_post({"UnderlyingScrip": under_security_id, "UnderlyingSeg": under_exchange_segment})

# -----------------------------
# OPTION CHAIN (POST body — exact Dhan shape)
# -----------------------------
@router.post("")
def optionchain_post(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Dhan shape:
    {
      "UnderlyingScrip": 25,
      "UnderlyingSeg": "IDX_I",
      "Expiry": "YYYY-MM-DD"
    }
    """
    u = payload.get("UnderlyingScrip")
    seg = payload.get("UnderlyingSeg")
    exp = payload.get("Expiry")
    if u is None or seg is None or not exp:
        raise HTTPException(400, detail="UnderlyingScrip, UnderlyingSeg and Expiry are required")

    if APP_MODE == "LIVE":
        return _dhan_post("/optionchain", {"UnderlyingScrip": int(u), "UnderlyingSeg": str(seg), "Expiry": str(exp)})

    # SANDBOX
    return _sandbox_chain(str(u), str(exp))

# -----------------------------
# OPTION CHAIN (GET wrapper — convenient)
# -----------------------------
@router.get("")
def optionchain_get(
    under_security_id: int = Query(...),
    under_exchange_segment: str = Query(...),
    expiry: str = Query(...),
):
    return optionchain_post({"UnderlyingScrip": under_security_id,
                             "UnderlyingSeg": under_exchange_segment,
                             "Expiry": expiry})
