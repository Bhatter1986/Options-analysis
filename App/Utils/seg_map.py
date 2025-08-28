# Map instrument_type + segment -> Dhan V2 UnderlyingSeg
# Tweak/extend with Annexure as needed.
SEG_MAP = {
    ("INDEX", "I"): "IDX_I",   # indices
    ("EQ",    "E"): "E_E",     # placeholder for equity options — replace per Annexure if different
    # add more when needed…
}

def to_dhan_seg(instrument_type: str, segment: str) -> str | None:
    return SEG_MAP.get((instrument_type.upper(), segment.upper()))
