from __future__ import annotations
from fastapi import APIRouter, HTTPException
from App.services.instruments_refresh import refresh_instruments

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/refresh_instruments")
def admin_refresh_instruments():
    try:
        result = refresh_instruments()
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"refresh failed: {e}")
