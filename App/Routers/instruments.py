# App/Routers/instruments.py
from __future__ import annotations

from fastapi import APIRouter, Query
from pathlib import Path
import pandas as pd
from typing import Dict, Any, List, Optional
import glob

router = APIRouter(prefix="/instruments", tags=["Instruments"])

# ---- Paths & cache ---------------------------------------------------
DATA_DIR = Path("data")
CSV_CANDIDATES = [
    "indices.csv",
    "instruments.csv",
    "*.csv",  # last resort: pick first CSV in /data
]
_cache: Dict[str, Any] = {"rows": None, "cols": None, "count": 0, "source": None}


# ---- Helpers ---------------------------------------------------------
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase + underscores; trim spaces."""
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _choose_csv_file() -> Optional[Path]:
    """Pick the first existing CSV from candidates inside /data."""
    if not DATA_DIR.exists():
        return None
    # exact names first
    for name in CSV_CANDIDATES[:-1]:
        p = DATA_DIR / name
        if p.exists():
            return p
    # wildcard fallback
    for pattern in [CSV_CANDIDATES[-1]]:
        for fp in glob.glob(str(DATA_DIR / pattern)):
            if fp.lower().endswith(".csv"):
                return Path(fp)
    return None


def _coalesce(d: dict, keys: List[str]) -> Any:
    """Return first present, non-empty value for any of the keys."""
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip() != "":
            return v
    return None


def _massage_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Create a resilient, uniform record shape:
      name, instrument_type, security_id, exchange_segment, + all original cols
    """
    rows = []
    for raw in df.to_dict(orient="records"):
        r = dict(raw)

        # Create soft aliases
        name = _coalesce(r, ["name", "index_name", "display_name", "trading_symbol", "symbol", "scrip_name"])
        inst_type = _coalesce(r, ["instrument_type", "type"])
        secid = _coalesce(r, ["security_id", "instrument_id", "token", "id"])
        exch = _coalesce(r, ["exchange_segment", "exchange", "segment"])

        if name is not None:
            r["name"] = name
        if inst_type is not None:
            r["instrument_type"] = inst_type
        if secid is not None:
            r["security_id"] = str(secid)
        if exch is not None:
            r["exchange_segment"] = exch

        rows.append(r)
    return rows


def _load_csv(force: bool = False):
    """Load CSV and cache it."""
    global _cache
    if _cache["rows"] is None or force:
        csv_path = _choose_csv_file()
        if not csv_path or not csv_path.exists():
            _cache = {"rows": [], "cols": [], "count": 0, "source": None}
            return _cache

        df = pd.read_csv(csv_path)
        df = _normalize_columns(df)

        rows = _massage_records(df)
        _cache = {
            "rows": rows,
            "cols": list(df.columns),
            "count": len(rows),
            "source": str(csv_path),
        }
    return _cache


# ---- Endpoints -------------------------------------------------------
@router.get("/")
def list_instruments(
    q: str | None = Query(None, description="search by name"),
    exchange_segment: str | None = None,
    security_id: str | None = None,
    limit: int = 50,
):
    data = _load_csv()["rows"]
    if not data:
        return {"count": 0, "data": []}

    out = data
    if q:
        ql = q.lower()
        out = [r for r in out if ql in str(r.get("name", "")).lower()]

    if exchange_segment:
        out = [r for r in out if str(r.get("exchange_segment", "")).lower() == exchange_segment.lower()]

    if security_id:
        out = [r for r in out if str(r.get("security_id", "")) == str(security_id)]

    return {"count": len(out[:limit]), "data": out[:limit]}


@router.get("/indices")
def list_indices(q: str | None = None, limit: int = 50):
    data = _load_csv()["rows"]
    if not data:
        return {"count": 0, "data": []}

    out = [r for r in data if str(r.get("instrument_type", "")).lower() == "index"]
    if q:
        ql = q.lower()
        out = [r for r in out if ql in str(r.get("name", "")).lower()]

    return {"count": len(out[:limit]), "data": out[:limit]}


@router.get("/search")
def search_instruments(q: str, limit: int = 50):
    data = _load_csv()["rows"]
    if not data:
        return {"count": 0, "data": []}

    ql = q.lower()
    out = []
    for r in data:
        txt = " ".join([str(v).lower() for v in r.values()])
        if ql in txt:
            out.append(r)
    return {"count": len(out[:limit]), "data": out[:limit]}


@router.get("/by-id")
def get_by_id(security_id: str):
    data = _load_csv()["rows"]
    if not data:
        return {"detail": "Not Found"}
    for r in data:
        if str(r.get("security_id")) == str(security_id):
            return r
    return {"detail": "Not Found"}


@router.post("/_refresh")
def refresh_cache():
    data = _load_csv(force=True)
    return {"ok": True, "rows": data["count"], "cols": data["cols"], "source": data["source"]}


# --- SUPER USEFUL for your situation ---
@router.get("/_debug")
def debug_instruments():
    data = _load_csv()
    sample = data["rows"][:3] if data["rows"] else []
    return {
        "source": data["source"],
        "rows": data["count"],
        "cols": data["cols"],
        "sample": sample,
    }
