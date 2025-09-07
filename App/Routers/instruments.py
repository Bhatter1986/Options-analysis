# App/Routers/instruments.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
import os
import httpx
import csv
from io import StringIO
from typing import List, Dict

from App.Services import dhan_client  # reuse our helper

router = APIRouter(prefix="/instruments", tags=["Instruments"])

# Env var fallback (agar user khud set kare)
CSV_URL = os.getenv("DHAN_INSTRUMENTS_CSV_URL", "")


async def fetch_csv(detailed: bool = True) -> List[Dict[str, str]]:
    """Download CSV (compact or detailed) from Dhan and return as list of dicts."""
    url = CSV_URL or dhan_client.get_instruments_csv(detailed=detailed)

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(url)
        r.raise_for_status()
        text = r.text

    reader = csv.DictReader(StringIO(text))
    return [row for row in reader]


@router.get("")
async def list_instruments(limit: int = 50):
    """
    Return instrument list.
    Query param `limit` default=50 for preview.
    """
    try:
        rows = await fetch_csv(detailed=True)
        return {"status": "success", "count": len(rows), "data": rows[:limit]}
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch instruments: {e}")


@router.get("/{security_id}")
async def get_instrument(security_id: str):
    """Lookup a single instrument by Security ID (case-insensitive)."""
    try:
        rows = await fetch_csv(detailed=True)
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch instruments: {e}")

    security_id = security_id.strip().lower()

    for row in rows:
        for key, val in row.items():
            if key.lower() in ("securityid", "sem_smst_security_id") and str(val).lower() == security_id:
                return {"status": "success", "data": row}

    raise HTTPException(404, f"Instrument {security_id} not found")
