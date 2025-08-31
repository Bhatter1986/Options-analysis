#!/usr/bin/env python3
"""
Generate data/instruments.csv from Dhan master CSV.

Output schema:
id,name,segment,step
"""

from __future__ import annotations
import csv
import sys
import requests
from io import StringIO
from pathlib import Path

MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

# Jo watchlist chahiye – feel free to edit/add
INDEX_SYMBOLS = {
    "NIFTY 50": {"step": 50, "segment": "IDX_I"},
    "BANKNIFTY": {"step": 100, "segment": "IDX_I"},
}
STOCK_SYMBOLS = {
    # symbol -> step
    "RELIANCE": {"step": 10, "segment": "NSE_E"},
    "HDFCBANK": {"step": 10, "segment": "NSE_E"},
    "TCS": {"step": 10, "segment": "NSE_E"},
    "INFY": {"step": 10, "segment": "NSE_E"},
}

OUT_PATH = Path("data/instruments.csv")


def _normalize_segment(row: dict) -> str:
    """
    Dhan master CSV me kabhi column ka naam 'SEGMENT' hota hai,
    kabhi 'EXCHANGE_SEGMENT'. Dono handle karo.
    """
    seg = (
        row.get("SEGMENT")
        or row.get("EXCHANGE_SEGMENT")
        or row.get("EXCHANGE-SEGMENT")
        or ""
    ).strip()
    return seg


def _security_id(row: dict) -> int:
    # Common names across Dhan dumps
    for key in ("SMST_SECURITY_ID", "SECURITY_ID", "SECURITYID"):
        if key in row and row[key].strip():
            try:
                return int(row[key].strip())
            except Exception:
                pass
    return 0


def _symbol_name(row: dict) -> str:
    for key in ("SYMBOL_NAME", "TRADING_SYMBOL", "SYMBOL"):
        if key in row and row[key].strip():
            return row[key].strip()
    return ""


def fetch_master_rows() -> list[dict]:
    r = requests.get(MASTER_URL, timeout=30)
    r.raise_for_status()
    csv_text = r.text
    sio = StringIO(csv_text)
    reader = csv.DictReader(sio)
    return list(reader)


def pick_rows(rows: list[dict]) -> list[dict]:
    """Filter: indices in INDEX_SYMBOLS + stocks in STOCK_SYMBOLS (NSE)."""
    out: list[dict] = []

    # 1) Indices
    for row in rows:
        name = _symbol_name(row)
        seg = _normalize_segment(row)
        if name in INDEX_SYMBOLS and seg.startswith("IDX"):
            info = INDEX_SYMBOLS[name]
            out.append(
                {
                    "id": _security_id(row),
                    "name": f"{name} (ID)",
                    "segment": info["segment"],
                    "step": info["step"],
                }
            )

    # 2) Stocks (NSE_E)
    wanted = set(STOCK_SYMBOLS.keys())
    for row in rows:
        name = _symbol_name(row)
        seg = _normalize_segment(row)
        if name in wanted and seg == "NSE_E":
            info = STOCK_SYMBOLS[name]
            out.append(
                {
                    "id": _security_id(row),
                    "name": f"{name} (EQ)",
                    "segment": info["segment"],
                    "step": info["step"],
                }
            )

    # de-dup by id
    dedup = {}
    for x in out:
        if x["id"] and x["id"] not in dedup:
            dedup[x["id"]] = x
    return list(dedup.values())


def write_csv(rows: list[dict]) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "segment", "step"])
        for r in rows:
            w.writerow([r["id"], r["name"], r["segment"], r["step"]])


def main() -> int:
    print("Downloading Dhan master CSV ...")
    rows = fetch_master_rows()
    print(f"Fetched {len(rows)} master rows")

    picked = pick_rows(rows)
    if not picked:
        print("ERROR: Nothing matched – check symbols/segments.", file=sys.stderr)
        return 2

    write_csv(picked)
    print(f"Wrote {OUT_PATH} with {len(picked)} instruments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
