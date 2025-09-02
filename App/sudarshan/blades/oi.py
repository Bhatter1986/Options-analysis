# App/sudarshan/blades/oi.py
from typing import Dict, Any, Optional

async def analyze_oi(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Input: {"signal": "long_buildup" | "short_buildup" | "long_unwinding" | "short_covering" | "neutral"}
    """
    data = data or {}
    signal = str(data.get("signal", "neutral")).lower()
    return {"signal": signal}
