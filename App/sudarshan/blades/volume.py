# App/sudarshan/blades/volume.py
from typing import Dict, Any, Optional

def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))

async def analyze_volume(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Volume blade (buyer-friendly): volume spike + confirmation ko score karta hai.

    Accepts (all optional):
      - volume_spike: bool
      - confirmation: bool
      - spike_ratio: float (curr_vol / avg_vol), e.g. 1.8 = 80% higher
      - avg_volume: float (informational)
      - curr_volume: float (informational)

    Returns:
      - volume_spike: bool
      - confirmation: bool
      - spike_ratio: float | None
      - score: 0..1
      - signal: "spike" | "normal"
      - notes: str
    """
    data = data or {}
    vol_spike = bool(data.get("volume_spike", False))
    confirm   = bool(data.get("confirmation", False))

    spike_ratio = data.get("spike_ratio", None)
    try:
        spike_ratio = float(spike_ratio) if spike_ratio is not None else None
    except Exception:
        spike_ratio = None

    score = 0.5
    notes = []

    if vol_spike:
        score += 0.2
        notes.append("volume_spike")

    if confirm:
        score += 0.2
        notes.append("confirmation")

    if spike_ratio is not None:
        # Map ratio to +0..+0.2 bonus (1.0->0, 2.0->~0.2)
        bonus = (spike_ratio - 1.0) / 5.0
        bonus = _clamp(bonus, 0.0, 0.2)
        if bonus > 0:
            score += bonus
            notes.append(f"spike_ratio={spike_ratio:.2f}")

    score = _clamp(score)
    signal = "spike" if (vol_spike or (spike_ratio is not None and spike_ratio >= 1.5)) else "normal"

    return {
        "volume_spike": vol_spike,
        "confirmation": confirm,
        "spike_ratio": None if spike_ratio is None else float(f"{spike_ratio:.3f}"),
        "score": float(f"{score:.3f}"),
        "signal": signal,
        "notes": ", ".join(notes) if notes else "",
    }
