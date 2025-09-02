<<<<<<< HEAD
async def analyze_volume(data: dict | None = None):
    """
    Input shape (example): {"volume_spike": bool, "confirmation": bool}
    """
    data = data or {}
    return {
        "volume_spike": bool(data.get("volume_spike", False)),
        "confirmation": bool(data.get("confirmation", False)),
    }
=======
async def analyze_sentiment(data):
    """
    Sentiment Analysis:
    - Input: FII/DII, global indices, news sentiment
    - Output: dict with bullish/bearish/neutral
    """
    return {"sentiment": "neutral"}
>>>>>>> d0cdbbc (Add Sudarshan blade modules (price/oi/greeks/volume/sentiment))
