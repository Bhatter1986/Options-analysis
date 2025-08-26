import pandas as pd
from fastapi import APIRouter, Query
from pathlib import Path

router = APIRouter(prefix="/instruments", tags=["Instruments"])

CSV_PATH = Path("data/instruments.csv")

# Cache load
_df_cache = None
def load_csv():
    global _df_cache
    if _df_cache is None:
        if CSV_PATH.exists():
            _df_cache = pd.read_csv(CSV_PATH)
        else:
            _df_cache = pd.DataFrame()
    return _df_cache

@router.get("/indices")
def list_indices(q: str = Query(None), limit: int = 50):
    """
    List all indices (from instruments.csv).
    Filter by query `q` if provided.
    """
    df = load_csv()
    if df.empty:
        return {"count": 0, "data": []}

    # Filter only indices
    indices_df = df[df["instrument_type"].str.contains("INDEX", na=False)]

    if q:
        indices_df = indices_df[indices_df["symbol"].str.contains(q, case=False, na=False)]

    result = indices_df.head(limit).to_dict(orient="records")
    return {"count": len(result), "data": result}

@router.get("/search")
def search_instruments(q: str, limit: int = 50):
    """
    Generic search on instruments.csv (name/symbol match).
    """
    df = load_csv()
    if df.empty:
        return {"count": 0, "data": []}

    filtered = df[df["symbol"].str.contains(q, case=False, na=False)]
    result = filtered.head(limit).to_dict(orient="records")
    return {"count": len(result), "data": result}

@router.get("/by-id")
def get_by_id(security_id: int):
    """
    Get instrument by security_id.
    """
    df = load_csv()
    if df.empty:
        return {"detail": "Not Found"}

    row = df[df["security_id"] == security_id]
    if row.empty:
        return {"detail": "Not Found"}

    return row.iloc[0].to_dict()
