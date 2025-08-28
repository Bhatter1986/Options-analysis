# App/utils/seg_map.py
# Map (instrument_type, segment) -> Dhan Annexure segment code
# Indices: IDX_I confirmed. Stocks: replace "E_E" with exact code from Annexure if different.
SEG_MAP = {
    ("INDEX", "I"): "IDX_I",   # NIFTY, BANKNIFTY, FINNIFTY, SENSEX...
    ("EQ",    "E"): "E_E",     # <- verify with Annexure; update if required
    # Add more when needed (examples):
    ("OPTSTK", "D"): "D_D",    # placeholder, fill with real code from Annexure
    ("FUTSTK", "D"): "D_D",    # placeholder
}

def to_dhan_seg(instrument_type: str, segment: str) -> str | None:
    key = (instrument_type.upper(), segment.upper())
    return SEG_MAP.get(key)
