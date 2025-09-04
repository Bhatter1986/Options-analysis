from __future__ import annotations
from typing import Any, Dict

class DhanDataSource:
    """Placeholder: abhi request ke 'inputs' ko hi pass-through karta hai.
    Baad me yahin DhanHQ / DB / cache se real data laayenge."""
    def __init__(self, ctx: Dict[str, Any] | None = None) -> None:
        self.ctx = ctx or {}
        self.inputs: Dict[str, Any] = (self.ctx.get("inputs") or {})

    async def get_price_signals(self) -> Dict[str, Any]:
        return self.inputs.get("price") or {}

    async def get_oi_signals(self) -> Dict[str, Any]:
        return self.inputs.get("oi") or {}

    async def get_greeks_signals(self) -> Dict[str, Any]:
        return self.inputs.get("greeks") or {}

    async def get_volume_signals(self) -> Dict[str, Any]:
        return self.inputs.get("volume") or {}

    async def get_sentiment_signals(self) -> Dict[str, Any]:
        return self.inputs.get("sentiment") or {}
