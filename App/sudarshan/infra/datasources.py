from typing import Dict, Any
import httpx

class BrokerData:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    async def option_chain(self, under_security_id: int, expiry: str, seg: str,
                           step: int = 50, window: int = 10, show_all: bool = False) -> Dict[str, Any]:
        url = f"{self.base}/optionchain"
        params = dict(
            under_security_id=under_security_id,
            under_exchange_segment=seg,
            expiry=expiry,
            strikes_window=window,
            step=step,
            withGreeks=True,
            show_all=str(show_all).lower()
        )
        async with httpx.AsyncClient(timeout=30) as cx:
            r = await cx.get(url, params=params)
            r.raise_for_status()
            return r.json()

    async def historical(self, seg: str, security_id: int, interval: str,
                         from_dt: str, to_dt: str) -> Dict[str, Any]:
        url = f"{self.base}/historical/ohlc"
        params = dict(
            ExchangeSegment=seg,
            SecurityId=str(security_id),
            Interval=interval,
            FromDate=from_dt,
            ToDate=to_dt
        )
        async with httpx.AsyncClient(timeout=30) as cx:
            r = await cx.get(url, params=params)
            r.raise_for_status()
            return r.json()

    async def depth20(self, seg: str, security_id: int) -> Dict[str, Any]:
        url = f"{self.base}/depth20/{seg}/{security_id}"
        async with httpx.AsyncClient(timeout=15) as cx:
            r = await cx.get(url)
            r.raise_for_status()
            return r.json()

class ExternalNews:
    async def fii_dii(self): return {"fii": 0.0, "dii": 0.0}
    async def global_indices(self): return {"dow": 0.0, "dxy": 0.0}
    async def macro(self): return {"usdinr": 0.0}
