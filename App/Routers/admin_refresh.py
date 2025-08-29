from __future__ import annotations

import os
import io
import csv
import time
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/admin", tags=["admin"])

RAW_URL = os.getenv(
    "DHAN_MASTER_URL",
    "https://images.dhan.co/api-data/api-scrip-master-detailed.csv",
)

DATA_DIR = "data"
RAW_PATH = os.path.join(DATA_DIR, "instruments_raw.csv")
OUT_PATH = os.path.join(DATA_DIR, "instruments.csv")

# Columns we will emit (stable for our app)
OUT_HEADER = ["security_id", "symbol_name", "underlying_symbol", "segment", "instrument_type"]

def _safe_mkdir(p: str):
    os.makedirs(p, exist_ok=True)

@router.post("/refresh_instruments")
def refresh_instruments():
    """
    Download Dhan detailed scrip master and write two files:
    - data/instruments_raw.csv  (full dump)
    - data/instruments.csv      (small, normalized header our app expects)
    We keep all rows but normalize a few common column aliases safely.
    """
    _safe_mkdir(DATA_DIR)

    try:
        # 1) download
        with httpx.Client(timeout=60.0) as client:
            r = client.get(RAW_URL)
            r.raise_for_status()
            raw_bytes = r.content
    except Exception as e:
        raise HTTPException(502, f"Failed to download scrip master: {e}")

    # Save raw dump
    with open(RAW_PATH, "wb") as f:
        f.write(raw_bytes)

    # 2) Normalize to our header best-effort (columns names vary across dumps).
    # Try to detect reasonable fieldnames.
    text_stream = io.StringIO(raw_bytes.decode("utf-8", errors="ignore"))
    reader = csv.DictReader(text_stream)
    src_cols = [c.strip() for c in (reader.fieldnames or [])]

    # Build a loose mapping for likely column names → our names
    # (we keep it resilient if the CSV headers shift a bit)
    def pick(d: dict, keys: list[str]) -> str:
        for k in keys:
            if k in d and d[k]:
                return str(d[k]).strip()
        return ""

    # Heuristics for common labels seen in master dumps
    # * security id
    C_ID   = [c for c in src_cols if c.lower() in ("security_id","securityid","security id","securitycode")]
    # * symbol / name
    C_SYM  = [c for c in src_cols if c.lower() in ("symbol","symbol_name","trading_symbol","name","securityname")]
    # * underlying (often same as symbol for indices)
    C_U    = [c for c in src_cols if "under" in c.lower() and "symbol" in c.lower()] or C_SYM
    # * exchange/segment
    C_SEG  = [c for c in src_cols if "segment" in c.lower()] + [c for c in src_cols if "exchange" in c.lower()]
    # * instrument type
    C_INST = [c for c in src_cols if "instrument" in c.lower()] + [c for c in src_cols if "type" in c.lower()]

    out_rows = 0
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=OUT_HEADER)
        w.writeheader()

        for row in reader:
            try:
                rec = {
                    "security_id":        pick(row, C_ID),
                    "symbol_name":        pick(row, C_SYM),
                    "underlying_symbol":  pick(row, C_U),
                    "segment":            pick(row, C_SEG),
                    "instrument_type":    pick(row, C_INST),
                }
                # write only if we have a security_id and segment
                if rec["security_id"] and rec["segment"]:
                    w.writerow(rec)
                    out_rows += 1
            except Exception:
                continue

    return {
        "ok": True,
        "raw_url": RAW_URL,
        "raw_path": RAW_PATH,
        "out_path": OUT_PATH,
        "rows": out_rows,
        "ts": int(time.time()),
    }
