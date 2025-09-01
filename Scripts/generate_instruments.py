# scripts/generate_instruments.py
import csv
import requests
from pathlib import Path

# Dhan master scrip CSV
MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
OUT_FILE = Path("data/instruments.csv")

# Top instruments for dashboard
WHITELIST = {
    "NIFTY 50": {"step": 50, "segment": "IDX_I"},
    "BANKNIFTY": {"step": 100, "segment": "IDX_I"},
    "FINNIFTY": {"step": 50, "segment": "IDX_I"},
    "RELIANCE": {"step": 10, "segment": "NSE_E"},
    "HDFCBANK": {"step": 10, "segment": "NSE_E"},
    "TCS": {"step": 10, "segment": "NSE_E"},
    "INFY": {"step": 10, "segment": "NSE_E"},
}

def main():
    print("Downloading Dhan master CSV…")
    r = requests.get(MASTER_URL)
    r.raise_for_status()
    lines = r.text.splitlines()
    reader = csv.DictReader(lines)

    out_rows = [("id", "name", "segment", "step")]

    for row in reader:
        name = row.get("SEM_TRADING_SYMBOL", "").strip()
        seg = row.get("SEM_EXM_EXCH_ID", "").strip()
        sec_id = row.get("SEM_SMST_SECURITY_ID", "").strip()

        for key, meta in WHITELIST.items():
            if key in name:
                out_rows.append((sec_id, name, meta["segment"], meta["step"]))

    # write instruments.csv
    OUT_FILE.write_text("\n".join([",".join(map(str, r)) for r in out_rows]), encoding="utf-8")
    print(f"Wrote {OUT_FILE} with {len(out_rows)-1} instruments")

if __name__ == "__main__":
    main()




