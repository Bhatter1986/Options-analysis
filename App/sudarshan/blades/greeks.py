# App/sudarshan/blades/greeks.py
from typing import Dict, Any, Optional

async def analyze_greeks(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Input: {"delta_bias": "long" | "short" | "neutral"}
    """
    data = data or {}
    delta_bias = str(data.get("delta_bias", "neutral")).lower()
    return {"delta_bias": delta_bias}
