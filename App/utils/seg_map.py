# App/utils/seg_map.py

# Mapping between internal CSV codes and Dhan API codes
SEG_MAP = {
    # Index & Stock identifiers (from instruments.csv)
    "I_INDEX": "IDX_I",     # Index
    "I_STOCK": "IDX_S",     # Stock

    # Options
    "IDXOPT": "OPTIDX",     # Options - Index
    "STKOPT": "OPTSTK",     # Options - Stock

    # Futures
    "IDXFUT": "FUTIDX",     # Futures - Index
    "STKFUT": "FUTSTK",     # Futures - Stock
}

def to_dhan_seg(code: str) -> str:
    """
    Map internal segment code (CSV) -> Dhan API segment code.
    Returns original if not found.
    """
    return SEG_MAP.get(code.upper(), code)
