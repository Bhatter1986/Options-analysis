from fastapi import HTTPException

@router.get("/by-id")
def get_by_id(security_id: str):
    """
    Return single instrument row by security_id (string-safe match).
    Example: /instruments/by-id?security_id=2
    """
    try:
        # ensure cache/dataframe ready
        if _cache.get("rows") is None:
            _load_csv()  # your existing loader util

        df = _cache["rows"]                # pandas DataFrame
        col = "security_id"
        if col not in df.columns:
            raise HTTPException(status_code=500, detail=f"Column '{col}' missing")

        # cast both sides to string for safe comparison
        m = df[col].astype(str) == str(security_id)
        hit = df.loc[m]

        if hit.empty:
            # proper 404 when not found
            raise HTTPException(status_code=404, detail="Not Found")

        return hit.iloc[0].to_dict()
    except HTTPException:
        # re-raise clean HTTP errors
        raise
    except Exception as e:
        # any unexpected error => 500 with message
        raise HTTPException(status_code=500, detail=f"by-id failed: {e}")
