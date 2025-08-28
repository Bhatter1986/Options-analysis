# App/utils/seg_map.py

SEG_MAP = {
    # CSV / internal  ->  Dhan API segment codes
    "I": "IDX_I",        # Index (e.g., NIFTY, BANKNIFTY, etc.)
    "S": "STK_S",        # Stocks (if CSV ever has 'S')
    # legacy/internal codes (keep as-is for safety)
    "IDXOPT": "OPTIDX",  # Options - Index
    "STKOPT": "OPTSTK",  # Options - Stock
    "IDXFUT": "FUTIDX",  # Futures - Index
    "STKFUT": "FUTSTK",  # Futures - Stock
}

def to_dhan_seg(code: str) -> str:
    """
    Map our/internal segment code -> Dhan API segment code.
    Returns original if unknown (safe fallback).
    """
    return SEG_MAP.get((code or "").upper(), code)
