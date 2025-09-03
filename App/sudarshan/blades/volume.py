# App/sudarshan/blades/volume.py
async def analyze_volume(data: dict | None = None):
    d = data or {}
    spike = bool(d.get("volume_spike", False))
    confirm = bool(d.get("confirmation", False))
    score = 1.0 if (spike and confirm) else (0.4 if spike else 0.0)
    return {"volume_spike": spike, "confirmation": confirm, "score": score}
