# App/utils/seg_map.py

SEG_MAP = {
    "IDXOPT": "OPTIDX",   # Options - Index
    "STKOPT": "OPTSTK",   # Options - Stock
    "IDXFUT": "FUTIDX",   # Futures - Index
    "STKFUT": "FUTSTK",   # Futures - Stock
    # Need be: add/override more codes here.
}

def to_dhan_seg(code: str) -> str:
    """
    Map our/internal segment code -> Dhan API segment code.
    Returns original if unknown (safe fallback).
    """
    return SEG_MAP.get(code.upper(), code)
