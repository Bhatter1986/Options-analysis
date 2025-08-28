# App/utils/seg_map.py
SEG_MAP = {
    # Confirmed for indices (NIFTY, BANKNIFTY, FINNIFTY, SENSEX...)
    ("INDEX", "I"): "IDX_I",

    # ====== PLACEHOLDERS (Annexure se exact fill karein) ======
    # Example ideas (replace with exact):
    # ("EQ", "E"): "EQ_E",         # Equity (cash) underlying segment code
    # ("OPTSTK", "D"): "EQ_D",     # Stock derivatives underlying segment code
    # ("FUTSTK", "D"): "EQ_D",
    # ("CURR", "C"): "CURR_C",
    # ("MCX", "M"): "MCX_M",
    # ==========================================================
}

def to_dhan_seg(instrument_type: str, segment: str) -> str | None:
    key = (instrument_type.upper(), segment.upper())
    return SEG_MAP.get(key)
