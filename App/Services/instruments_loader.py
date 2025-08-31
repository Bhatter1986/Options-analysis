# App/Services/instruments_loader.py
from __future__ import annotations

import os, io, csv, time
import httpx
from pathlib import Path
from typing import Any, Dict, List

CSV_URL = os.getenv(
    "DHAN_INSTRUMENTS_CSV_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv",
)
CACHE_PATH = Path(os.getenv("DHAN_INSTRUMENTS_CACHE", "data/dhan_master_cache.csv"))
CACHE_TTL_SEC = 60 * 30  # 30 min

def _norm_key(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "")

def _row_get(row: Dict[str, Any], *candidates: str) -> str:
    nmap = getattr(row, "__nmap", None)
    if nmap is None:
        nmap = {_norm_key(k): v for k, v in row.items()}
        row.__nmap = nmap  # type: ignore[attr-defined]
    for c in candidates:
        v = nmap.get(_norm_key(c))
        if v is not None:
            return str(v).strip()
    return ""

def _guess_step(name: str, segment: str) -> int:
    n = (name or "").lower()
    if segment == "IDX_I":
        return 100 if "bank" in n else 50
    return 10

def _fetch_csv_text() -> str:
    try:
        if CACHE_PATH.exists():
            age = time.time() - CACHE_PATH.stat().st_mtime
            if age < CACHE_TTL_SEC:
                return CACHE_PATH.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass
    with httpx.Client(timeout=30.0) as client:
        r = client.get(CSV_URL)
        r.raise_for_status()
        txt = r.text
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(txt, encoding="utf-8")
    except Exception:
        pass
    return txt

def load_dhan_master() -> List[Dict[str, str]]:
    txt = _fetch_csv_text()
    f = io.StringIO(txt)
    rdr = csv.DictReader(f)
    return [row for row in rdr]

def list_indices_from_master() -> List[Dict[str, Any]]:
    rows = load_dhan_master()
    out: List[Dict[str, Any]] = []
    for row in rows:
        secid  = _row_get(row, "Security Id", "security_id", "securityid")
        symbol = _row_get(row, "Trading Symbol", "Symbol", "Scrip Name", "Name")
        inst   = _row_get(row, "Instrument", "Instrument Type")
        if not secid or not symbol: 
            continue
        low_sym, low_inst = symbol.lower(), inst.lower()
        is_index = ("index" in low_inst) or any(x in low_sym for x in ["nifty", "banknifty", "finnifty", "midcpnifty"])
        if not is_index:
            continue
        seg = "IDX_I"
        try:
            sid = int(secid)
        except ValueError:
            continue
        if "banknifty" in low_sym and not any("BANKNIFTY" in x["name"] for x in out):
            out.append({"id": sid, "name": symbol, "segment": seg, "step": _guess_step(symbol, seg)})
        elif "finnifty" in low_sym and not any("FINNIFTY" in x["name"] for x in out):
            out.append({"id": sid, "name": symbol, "segment": seg, "step": _guess_step(symbol, seg)})
        elif "midcpnifty" in low_sym and not any("MIDCPNIFTY" in x["name"] for x in out):
            out.append({"id": sid, "name": symbol, "segment": seg, "step": _guess_step(symbol, seg)})
        elif "nifty" in low_sym and not any("NIFTY" in x["name"] for x in out):
            out.append({"id": sid, "name": symbol, "segment": seg, "step": _guess_step(symbol, seg)})
    return [x for x in out if x.get("id")]
    
def search_equities_from_master(q: str, limit: int = 10) -> List[Dict[str, Any]]:
    if not q: 
        return []
    ql = q.strip().lower()
    rows = load_dhan_master()
    res: List[Dict[str, Any]] = []
    for row in rows:
        secid  = _row_get(row, "Security Id", "security_id", "securityid")
        symbol = _row_get(row, "Trading Symbol", "Symbol", "Scrip Name", "Name")
        inst   = _row_get(row, "Instrument", "Instrument Type")
        if not secid or not symbol:
            continue
        low_sym, low_inst = symbol.lower(), inst.lower()
        is_equity_like = ("eq" in low_inst) or ("equity" in low_inst) or ("stock" in low_inst)
        if ql in low_sym and (is_equity_like or True):
            try:
                sid = int(secid)
            except ValueError:
                continue
            item = {"id": sid, "name": symbol, "segment": "NSE_I", "step": _guess_step(symbol, "NSE_I")}
            if item not in res:
                res.append(item)
            if len(res) >= limit:
                break
    return res
