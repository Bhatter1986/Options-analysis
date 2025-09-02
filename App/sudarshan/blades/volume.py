# App/sudarshan/blades/volume.py
from typing import Dict, Any, Optional

async def analyze_volume(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Input: {"volume_spike": bool, "confirmation": bool}
    """
    data = data or {}
    return {
        "volume_spike": bool(data.get("volume_spike", False)),
        "confirmation": bool(data.get("confirmation", False)),
    }
