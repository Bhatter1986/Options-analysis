# App/sudarshan/blades/volume.py
async def analyze_volume(data: dict | None = None):
    data = data or {}
    spike = bool(data.get("volume_spike", False))
    confirm = bool(data.get("confirmation", False))
    score = 1.0 if (spike and confirm) else (0.5 if spike else 0.0)
    return {"volume_spike": spike, "confirmation": confirm, "score": score}
