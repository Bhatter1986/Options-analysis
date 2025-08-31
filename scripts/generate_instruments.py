import csv, requests
from pathlib import Path

MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
OUT = Path("data/instruments.csv")

# Jo items dashboard me chahiye (id later fetch hogi CSV se)
WHITELIST = {
    "NIFTY 50":     {"segment": "IDX_I", "step": 50},
    "BANKNIFTY":    {"segment": "IDX_I", "step": 100},
    "FINNIFTY":     {"segment": "IDX_I", "step": 50},
    "RELIANCE":     {"segment": "NSE_E", "step": 10},
    "HDFCBANK":     {"segment": "NSE_E", "step": 10},
    "TCS":          {"segment": "NSE_E", "step": 10},
    "INFY":         {"segment": "NSE_E", "step": 10},
}

def main():
    print("Downloading Dhan master…")
    r = requests.get(MASTER_URL, timeout=60)
    r.raise_for_status()

    rows = csv.DictReader(r.text.splitlines())
    out = [("id","name","segment","step")]  # 4 columns, no extra commas/quotes

    for row in rows:
        name = (row.get("SEM_TRADING_SYMBOL") or "").strip()
        sec_id = (row.get("SEM_SMST_SECURITY_ID") or "").strip()
        exch = (row.get("SEM_EXM_EXCH_ID") or "").strip()

        # basic filters: required fields
        if not (name and sec_id and exch):
            continue

        for key, meta in WHITELIST.items():
            if key in name:
                out.append((sec_id, name, meta["segment"], str(meta["step"])))
                break

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(",".join(map(str, r)) for r in out), encoding="utf-8")
    print(f"Wrote {OUT} ({len(out)-1} instruments)")

if __name__ == "__main__":
    main()
