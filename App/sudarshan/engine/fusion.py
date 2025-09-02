# App/sudarshan/engine/fusion.py
from __future__ import annotations

from typing import Any, Dict, Mapping

# ---- Defaults (keep in sync with your UI sliders, if any)
DEFAULT_WEIGHTS: Dict[str, float] = {
    "price": 1.0,
    "oi": 1.0,
    "greeks": 0.8,
    "volume": 0.7,
    "sentiment": 0.5,
}
DEFAULT_MIN_CONFIRMS: int = 3


def _as_bool(value: Any) -> bool:
    """Safely coerce truthy values to bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        return v in ("1", "true", "yes", "y", "on")
    return bool(value)


def _score_bool(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _normalize_weights(w: Mapping[str, float] | None) -> Dict[str, float]:
    """Merge with defaults and ensure all required keys exist."""
    merged = dict(DEFAULT_WEIGHTS)
    if w:
        for k, v in w.items():
            try:
                merged[k] = float(v)
            except Exception:
                # ignore bad inputs; keep default
                pass
    return merged


async def fuse(
    inputs: Mapping[str, Any],
    weights: Mapping[str, float] | None = None,
    min_confirms: int | None = None,
) -> Dict[str, Any]:
    """
    Combine individual blade decisions into one fused signal.

    Parameters
    ----------
    inputs:
        Dict with per-blade outputs, e.g.:
        {
          "price":     {"trend": "bullish"},
          "oi":        {"signal": "long_buildup"},
          "greeks":    {"delta_bias": "long"},
          "volume":    {"volume_spike": True, "confirmation": True},
          "sentiment": {"sentiment": "bullish"}
        }
    weights:
        Optional per-blade weights. Missing keys fall back to defaults.
    min_confirms:
        Minimum number of blades that must be true for confirmation.

    Returns
    -------
    {
      "confirmation": bool,
      "confirms": int,
      "min_confirms": int,
      "score": float (0..1),
      "detail": { "price": bool, "oi": bool, "greeks": bool, "volume": bool, "sentiment": bool }
    }
    """
    # Prepare config
    w = _normalize_weights(weights)
    minc = int(min_confirms or DEFAULT_MIN_CONFIRMS)

    # ----- Evaluate each blade into True/False
    detail: Dict[str, bool] = {}

    # price: bullish?
    price = (inputs.get("price") or {})
    detail["price"] = (price.get("trend") or "").lower() == "bullish"

    # oi: long buildup?
    oi = (inputs.get("oi") or {})
    detail["oi"] = (oi.get("signal") or "").lower() == "long_buildup"

    # greeks: delta bias long?
    greeks = (inputs.get("greeks") or {})
    detail["greeks"] = (greeks.get("delta_bias") or "").lower() == "long"

    # volume: spike AND confirmation?
    vol = (inputs.get("volume") or {})
    vol_spike = _as_bool(vol.get("volume_spike", False))
    vol_conf  = _as_bool(vol.get("confirmation", True))  # default True if not provided
    detail["volume"] = vol_spike and vol_conf

    # sentiment: bullish?
    sent = (inputs.get("sentiment") or {})
    detail["sentiment"] = (sent.get("sentiment") or "").lower() == "bullish"

    # ----- Aggregate
    confirms = sum(1 for v in detail.values() if v)
    confirmation = confirms >= max(1, minc)  # guard against weird minc

    total_weight = sum(float(v) for v in w.values()) or 1.0
    raw_score = (
        w["price"] * _score_bool(detail["price"])
        + w["oi"] * _score_bool(detail["oi"])
        + w["greeks"] * _score_bool(detail["greeks"])
        + w["volume"] * _score_bool(detail["volume"])
        + w["sentiment"] * _score_bool(detail["sentiment"])
    )
    score = round(raw_score / total_weight, 3)

    return {
        "confirmation": confirmation,
        "confirms": int(confirms),
        "min_confirms": int(minc),
        "score": score,
        "detail": detail,
    }


__all__ = ["fuse", "DEFAULT_WEIGHTS", "DEFAULT_MIN_CONFIRMS"]
