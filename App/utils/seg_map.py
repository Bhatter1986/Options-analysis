# App/utils/seg_map.py
SEG_MAP = {
    "IDX_I": "Index - NSE Indices",
    "EQ": "Equity - Stocks",
    "FUTIDX": "Futures - Index",
    "FUTSTK": "Futures - Stocks",
    "OPTIDX": "Options - Index",
    "OPTSTK": "Options - Stocks"
}

def get_segment_name(code: str) -> str:
    return SEG_MAP.get(code, code)
