SEG_MAP = {
    ("INDEX", "I"): "IDX_I",    # NSE Indices
    ("EQ",    "E"): "E_E",      # NSE Equity
    ("OPTSTK","D"): "D_E",      # NSE Stock Options (placeholder – check Annexure)
    ("FUTSTK","D"): "D_F",      # NSE Stock Futures
}

def to_dhan_seg(instr_type: str, seg: str) -> str | None:
    return SEG_MAP.get((instr_type.upper(), seg.upper()))
