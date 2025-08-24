# Options Analysis (DhanHQ v2 SDK)

FastAPI service exposing simple endpoints for Orders, Positions, Holdings, Option Chain, and OHLC quotes using the official `dhanhq` Python SDK (v2.0.2).

## Endpoints
- `GET /broker_status` — checks env vars present
- `GET /orders` — order list
- `GET /positions` — positions
- `GET /holdings` — holdings
- `POST /option_chain` — body: `{"under_security_id":13, "under_exchange_segment":"IDX_I", "expiry":"YYYY-MM-DD"}`
- `GET /ohlc?security_id=1333&segment=NSE_EQ` — quick OHLC snapshot

## Local run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill your DHAN_CLIENT_ID & DHAN_ACCESS_TOKEN
uvicorn main:app --reload
