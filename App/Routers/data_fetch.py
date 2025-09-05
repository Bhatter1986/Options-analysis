cat > App/Routers/data_fetch.py <<'PY'
from fastapi import APIRouter, Query
from App.Services.data_fetch.scheduler import fetch_snapshot

router = APIRouter(prefix="/data", tags=["data"])

@router.get("/snapshot")
def snapshot(symbol: str = Query("NIFTY")):
    snap = fetch_snapshot(symbol)
    return {
        "symbol": snap.symbol,
        "snapshot": snap.model_dump(),
        "sudarshan_inputs": snap.sudarshan_inputs(),
    }
PY
