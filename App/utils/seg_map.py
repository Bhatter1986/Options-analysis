# App/utils/seg_map.py

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
    return SEG_MAP.get(seg, seg)
