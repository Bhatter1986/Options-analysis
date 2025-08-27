# --- /instruments/by-id ------------------------------------------------------
from fastapi import HTTPException

@router.get("/by-id")
def by_id(security_id: str = Query(..., description="Exact Dhan security_id")):
    _ensure_loaded()
    df = _cache["rows"]
    if df is None:
        raise HTTPException(status_code=503, detail="Cache not ready")

    # normalize column name (lowercase safety)
    if "security_id" not in df.columns:
        # map lowercase names just in case
        cols_map = {c.lower(): c for c in df.columns}
        if "security_id" not in cols_map:
            raise HTTPException(status_code=500, detail="security_id column missing")
        real_col = cols_map["security_id"]
    else:
        real_col = "security_id"

    sid = str(security_id).strip()           # always compare as string
    try:
        row = df[df[real_col].astype(str) == sid].head(1)
        if row.empty:
            raise HTTPException(status_code=404, detail="Not Found")
        return row.iloc[0].to_dict()
    except HTTPException:
        raise
    except Exception as e:
        # defensive: don't 500 with stack traces
        raise HTTPException(status_code=400, detail=f"bad request: {e}")
