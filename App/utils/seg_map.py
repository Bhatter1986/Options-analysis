# App/utils/seg_map.py

SEG_MAP = {
    "IDXOPT": "OPTIDX",   # Options - Index
    "STKOPT": "OPTSTK",   # Options - Stock
    "IDXFUT": "FUTIDX",   # Futures - Index
    "STKFUT": "FUTSTK",   # Futures - Stock
}

def to_dhan_seg(code: str) -> str:
    """
    Map TradingView/our internal segment codes to Dhan API segment codes.
    If not found, return original code.
    """
    return SEG_MAP.get(code.upper(), code)
