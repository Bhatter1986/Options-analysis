# App/utils/seg_map.py
from __future__ import annotations

# Map your CSV (instrument_type, segment) -> Dhan UnderlyingSeg
# Indices are correct with IDX_I. Add more later as needed.
SEG_MAP = {
    ("INDEX", "I"): "IDX_I",
    # TODO (when going LIVE with stocks/currency/etc):
    # ("EQ", "E"): "<PUT_CORRECT_CODE_FROM_ANNEXURE>",
    # ("OPTSTK", "D"): "<...>",
    # ("FUTSTK", "D"): "<...>",
}

def to_dhan_seg(instrument_type: str, segment: str) -> str | None:
    return SEG_MAP.get((instrument_type.upper(), segment.upper()))
