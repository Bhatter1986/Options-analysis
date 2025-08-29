from __future__ import annotations
import os, io, time, csv
from typing import List
import httpx

DHAN_MASTER_URL = os.getenv(
    "DHAN_MASTER_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
)

# Final minimal CSV jisko hamari app use karti hai
OUT_PATH = os.getenv("INSTRUMENTS_OUT_PATH", "data/instruments.csv")

# Columns we want in output
OUT_HEADER = ["security_id","symbol_name","underlying_symbol","segment","instrument_type"]

# Map Dhan master columns -> hamare columns
# (Dhan master headings kabhi-kabhi change ho sakti hain, isliye sabse common names handle)
CANDIDATE_COLS = {
    "security_id": ["security_id","SecurityId","securityId"],
    "symbol_name": ["symbol_name","SymbolName","tradingsymbol","TradingSymbol"],
    "underlying_symbol": ["underlying_symbol","UnderlyingSymbol","underlying","Underlying"],
    "segment": ["segment","Segment","exchange_segment","ExchangeSegment"],
    "instrument_type": ["instrument_type","InstrumentType","instrument","Instrument"]
}

def _pick(colmap: dict, row: dict, key: str, default: str="") -> str:
    for k in CANDIDATE_COLS[key]:
        if k in row and row[k] is not None:
            return str(row[k]).strip()
    # fallback: try lower/upper keys
    for k in list(row.keys()):
        if k.lower() == key.lower():
            return str(row[k]).strip()
    return default

def refresh_instruments(timeout: float = 60.0) -> dict:
    """
    Download Dhan master CSV → normalize → write data/instruments.csv
    Returns brief stats.
    """
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    t0 = time.time()

    # 1) download
    with httpx.Client(timeout=timeout) as client:
        r = client.get(DHAN_MASTER_URL)
        r.raise_for_status()
    raw_csv = r.text

    # 2) parse + normalize
    rdr = csv.DictReader(io.StringIO(raw_csv))
    rows: List[dict] = []
    seen = set()

    for row in rdr:
        rec = {
            "security_id": _pick(CANDIDATE_COLS, row, "security_id"),
            "symbol_name": _pick(CANDIDATE_COLS, row, "symbol_name"),
            "underlying_symbol": _pick(CANDIDATE_COLS, row, "underlying_symbol"),
            "segment": _pick(CANDIDATE_COLS, row, "segment"),
            "instrument_type": _pick(CANDIDATE_COLS, row, "instrument_type"),
        }

        # basic sanity: security_id + something
        if not rec["security_id"] or not rec["symbol_name"]:
            continue

        key = (rec["security_id"], rec["segment"], rec["instrument_type"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(rec)

    # 3) write compact CSV our app expects
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_HEADER)
        w.writeheader()
        for rec in rows:
            w.writerow(rec)

    dt = time.time() - t0
    return {
        "ok": True,
        "source": DHAN_MASTER_URL,
        "out_path": OUT_PATH,
        "rows": len(rows),
        "took_sec": round(dt, 2),
    }
