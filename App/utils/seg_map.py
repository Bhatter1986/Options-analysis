# App/utils/seg_map.py

# Mapping between our CSV segment codes and Dhan API expected codes
SEG_MAP = {
    # Indexes
    "I_INDEX": "IDX_I",
    "I_STOCK": "IDX_S",

    # Futures
    "FUTIDX": "FUTIDX",
    "FUTSTK": "FUTSTK",

    # Options
    "OPTIDX": "OPTIDX",
    "OPTSTK": "OPTSTK",
}

def to_dhan_seg(seg: str) -> str:
    """
    Map segment code from instruments.csv to Dhan API segment code.
    If not found, return as-is.
    """
    return SEG_MAP.get(seg, seg)
