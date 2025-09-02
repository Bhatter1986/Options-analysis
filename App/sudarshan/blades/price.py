# App/sudarshan/blades/price.py
from typing import Dict, Any, Optional

async def analyze_price(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Input: {"trend": "bullish" | "bearish" | "neutral"}
    Robust to None input.
    """
    data = data or {}
    trend = str(data.get("trend", "neutral")).lower()
    return {"trend": trend}
