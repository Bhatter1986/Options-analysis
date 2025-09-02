async def analyze_volume(data: dict | None = None):
    """
    Input shape (example): {"volume_spike": bool, "confirmation": bool}
    """
    data = data or {}
    return {
        "volume_spike": bool(data.get("volume_spike", False)),
        "confirmation": bool(data.get("confirmation", False)),
    }
