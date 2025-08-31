# App/Services/instruments_loader.py
from __future__ import annotations

import os
import io
import csv
import time
import httpx
from pathlib import Path
from typing import Any, Dict, List, Optional

CSV_URL = os.getenv(
    "DHAN_INSTRUMENTS_CSV_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv",
)
CACHE_PATH = Path(os.getenv("DHAN_INSTRUMENTS_CACHE", "data/dhan_master_cache.csv"))
CACHE_TTL_SEC = 60 * 30  # 30 minutes

def _norm_key(s: str) -> str:
    return (
        s.strip()
         .lower()
         .replace(" ", "_")
         .replace("-", "_")
         .replace("/", "_")
         .replace(".", "")
    )

def _row_get(row: Dict[str, Any], *candidates: str) -> str:
    """
    Safely read a value from a CSV row trying multiple possible header names.
    Returns '' if not found.
    """
    # build normalized mapping once
    nmap = getattr(row, "__nmap", None)
    if nmap is None:
        nmap = {}
        for k, v in row.items():
            nmap[_norm_key(k)] = v
        row.__nmap = nmap  # type: ignore[attr-defined]
    for c in candidates:
        v = nmap.get(_norm_key(c))
        if v is not None:
            return str(v).strip()
    return ""

def _guess_step(name: str, segment: str) -> int:
    n = (name or "").lower()
    if segment == "IDX_I":
        if "bank" in n:
            return 100  # BANKNIFTY step
        return 50       # NIFTY / other index step
    # equities default
    return 10

def _fetch_csv_text() -> str:
    # cache check
    try:
        if CACHE_PATH.exists():
            age = time.time() - CACHE_PATH.stat().st_mtime
            if age < CACHE_TTL_SEC:
                return CACHE_PATH.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass

    # fetch
    with httpx.Client(timeout=30.0) as client:
        r = client.get(CSV_URL)
        r.raise_for_status()
        txt = r.text

    # write cache
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(txt, encoding="utf-8")
    except Exception:
        pass

    return txt

def load_dhan_master() -> List[Dict[str, str]]:
    """
    Returns raw rows (as dicts) from the original Dhan master CSV.
    """
    txt = _fetch_csv_text()
    f = io.StringIO(txt)
    rdr = csv.DictReader(f)
    rows: List[Dict[str, str]] = []
    for row in rdr:
        rows.append(row)
    return rows

# ---------------- Public helpers ----------------

def list_indices_from_master() -> List[Dict[str, Any]]:
    """
    Extract top index underlyings (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY) from original CSV.
    We DO NOT change Dhan format; we only read Security Id & Symbol-ish fields.
    """
    rows = load_dhan_master()
    out: List[Dict[str, Any]] = []

    # We accept multiple possible columns for ID & Name
    # Common candidates:
    # - Security Id / security_id
    # - Trading Symbol / Symbol / Name
    # - Instrument Type / Instrument
    for row in rows:
        secid = _row_get(row, "Security Id", "security_id", "securityid")
        # prefer a "symbol-like" name first; fallback to "name"
        symbol = _row_get(row, "Trading Symbol", "Symbol", "Scrip Name", "Name")
        inst   = _row_get(row, "Instrument", "Instrument Type")

        low_sym = symbol.lower()
        low_inst = inst.lower()

        # We loosely detect 'index' instruments
        is_index = ("index" in low_inst) or any(x in low_sym for x in ["nifty", "banknifty", "finnifty", "midcpnifty"])
        if not is_index:
            continue

        # Deduce segment for option chain underlying (index options)
        segment = "IDX_I"

        # Pick only the main well-known indices; avoid duplicates
        if "banknifty" in low_sym and not any("BANKNIFTY" in x["name"] for x in out):
            out.append({
                "id": int(secid) if secid.isdigit() else None,
                "name": symbol or "BANKNIFTY",
                "segment": segment,
                "step": _guess_step(symbol, segment),
            })
        elif "finnifty" in low_sym and not any("FINNIFTY" in x["name"] for x in out):
            out.append({
                "id": int(secid) if secid.isdigit() else None,
                "name": symbol or "FINNIFTY",
                "segment": segment,
                "step": _guess_step(symbol, segment),
            })
        elif "midcpnifty" in low_sym and not any("MIDCPNIFTY" in x["name"] for x in out):
            out.append({
                "id": int(secid) if secid.isdigit() else None,
                "name": symbol or "MIDCPNIFTY",
                "segment": segment,
                "step": _guess_step(symbol, segment),
            })
        elif "nifty" in low_sym and not any("NIFTY" in x["name"] for x in out):
            out.append({
                "id": int(secid) if secid.isdigit() else None,
                "name": symbol or "NIFTY 50",
                "segment": segment,
                "step": _guess_step(symbol, segment),
            })

    # Filter None ids (sometimes master has multiple forms); keep those with IDs
    out = [x for x in out if isinstance(x.get("id"), int) and x["id"]]
    return out

def search_equities_from_master(q: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fuzzy search equities (stocks) from original CSV.
    We return minimal fields needed by your UI + optionchain API:
      id (underlying security id), name (symbol), segment (NSE_I), step (10)
    """
    if not q:
        return []
    ql = q.strip().lower()
    rows = load_dhan_master()
    res: List[Dict[str, Any]] = []

    for row in rows:
        secid = _row_get(row, "Security Id", "security_id", "securityid")
        symbol = _row_get(row, "Trading Symbol", "Symbol", "Scrip Name", "Name")
        inst   = _row_get(row, "Instrument", "Instrument Type")

        if not secid or not symbol:
            continue

        low_sym = symbol.lower()
        low_inst = inst.lower()

        # Heuristic: include likely equity rows (not INDEX, not FUT/OPT)
        is_equity_like = ("eq" in low_inst) or ("equity" in low_inst) or ("stock" in low_inst)
        if not is_equity_like:
            # also accept when symbol matches and instrument field is blank-ish
            if not ql in low_sym:
                continue

        if ql in low_sym:
            try:
                sid = int(secid)
            except ValueError:
                continue
            item = {
                "id": sid,
                "name": symbol,
                "segment": "NSE_I",   # Underlying segment for equity options (kept consistent with your UI)
                "step": _guess_step(symbol, "NSE_I"),
            }
            # avoid duplicates
            if item not in res:
                res.append(item)
            if len(res) >= limit:
                break

    return res
