import pandas as pd
from fastapi import APIRouter, Query, HTTPException
from typing import Optional

router = APIRouter(prefix="/instruments", tags=["instruments"])

# In-memory cache
_cache = {
    "rows": None,
    "cols": None,
    "path": "instruments.csv"  # CSV ka location (root me rakha hai to ye chalega)
}


# ------------------ Helpers ------------------ #
def _load_csv(force: bool = False):
    if _cache["rows"] is None or force:
        df = pd.read_csv(_cache["path"])
        _cache["rows"] = df.to_dict(orient="records")
        _cache["cols"] = list(df.columns)
    return _cache


# ------------------ Endpoints ------------------ #

@router.get("/_debug")
def debug_cache():
    """Return debug info (rows count + columns)"""
    if _cache["rows"] is None:
        return {"rows": 0, "cols": []}
    return {"rows": len(_cache["rows"]), "cols": _cache["cols"]}


@router.post("/_refresh")
def refresh_cache():
    """Force reload CSV into memory"""
    _load_csv(force=True)
    return {"status": "refreshed", "rows": len(_cache["rows"])}


@router.get("/")
def list_instruments(limit: int = 50):
    """Return sample instruments (default 50 rows)"""
    data = _load_csv()["rows"]
    return {"rows": data[:limit]}


@router.get("/indices")
def list_indices(q: Optional[str] = Query(None)):
    """Return only index instruments (optionally filter by q)"""
    df = pd.DataFrame(_load_csv()["rows"])
    df.columns = [c.lower() for c in df.columns]

    # Filter instrument_type == INDEX
    indices = df[df["instrument_type"].str.upper() == "INDEX"]

    if q:
        indices = indices[indices["symbol_name"].str.contains(q, case=False, na=False)]

    return {"rows": indices.to_dict(orient="records")}


@router.get("/search")
def search_instruments(q: str):
    """Search instruments by symbol_name or underlying_symbol"""
    df = pd.DataFrame(_load_csv()["rows"])
    df.columns = [c.lower() for c in df.columns]

    mask = (
        df["symbol_name"].str.contains(q, case=False, na=False) |
        df["underlying_symbol"].str.contains(q, case=False, na=False)
    )
    results = df[mask]
    return {"rows": results.to_dict(orient="records")}


@router.get("/by-id")
def get_instrument_by_id(security_id: str):
    """
    Return a single instrument row by its security_id.
    Always compare as string (CSV may store ids as int or str).
    """
    try:
        df = pd.DataFrame(_load_csv()["rows"])
        df.columns = [c.lower() for c in df.columns]

        if "security_id" not in df.columns:
            raise HTTPException(status_code=500, detail="CSV missing security_id")

        sid = str(security_id).strip()
        match = df[df["security_id"].astype(str) == sid]

        if match.empty:
            raise HTTPException(status_code=404, detail="Not Found")

        return match.iloc[0].to_dict()  # ek hi JSON object
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
