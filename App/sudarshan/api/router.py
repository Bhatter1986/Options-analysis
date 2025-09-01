from fastapi import APIRouter, Query
from datetime import datetime, timedelta

from App.sudarshan.infra.datasources import BrokerData, ExternalNews
from App.sudarshan.blades import price_action, option_chain, greeks, volume_flow, sentiment, theta_iv_filters
from App.sudarshan.engine import signal_fusion

BACKEND_URL = "https://options-analysis.onrender.com"

api = APIRouter()
broker = BrokerData(BACKEND_URL)
news   = ExternalNews()

@api.get("/health")
async def health():
    return {"status":"ok","backend":BACKEND_URL}

@api.get("/blades/price")
async def blade_price(seg: str, security_id: int):
    to_dt = datetime.utcnow()
    fr_dt = to_dt - timedelta(days=5)
    fmt = "%Y-%m-%dT%H:%M:%S"
    c5  = await broker.historical(seg, security_id, "5MIN",  fr_dt.strftime(fmt), to_dt.strftime(fmt))
    c15 = await broker.historical(seg, security_id, "15MIN", fr_dt.strftime(fmt), to_dt.strftime(fmt))
    c1  = await broker.historical(seg, security_id, "1H",    fr_dt.strftime(fmt), to_dt.strftime(fmt))
    return price_action.analyze_price(c5.get("data",[]), c15.get("data",[]), c1.get("data",[]))

@api.get("/blades/oi")
async def blade_oi(under_security_id: int, seg: str, expiry: str, step: int = 50, window: int = 10):
    chain = await broker.option_chain(under_security_id, expiry, seg, step, window)
    return option_chain.analyze_chain(chain)

@api.get("/analyze")
async def analyze(
    under_security_id: int = Query(...),
    under_exchange_segment: str = Query("NSE_FNO"),
    expiry: str = Query(...),
    step: int = Query(50),
    window: int = Query(10),
):
    chain = await broker.option_chain(under_security_id, expiry, under_exchange_segment, step, window)
    oi    = option_chain.analyze_chain(chain)

    to_dt = datetime.utcnow()
    fr_dt = to_dt - timedelta(days=5)
    fmt = "%Y-%m-%dT%H:%M:%S"
    c5  = await broker.historical(under_exchange_segment, under_security_id, "5MIN",  fr_dt.strftime(fmt), to_dt.strftime(fmt))
    c15 = await broker.historical(under_exchange_segment, under_security_id, "15MIN", fr_dt.strftime(fmt), to_dt.strftime(fmt))
    c1  = await broker.historical(under_exchange_segment, under_security_id, "1H",    fr_dt.strftime(fmt), to_dt.strftime(fmt))

    price = price_action.analyze_price(c5.get("data",[]), c15.get("data",[]), c1.get("data",[]))
    grk   = greeks.greek_summary(chain)
    vol   = volume_flow.volume_spikes(c5.get("data",[]))
    senti = sentiment.daily_sentiment(await news.fii_dii(), await news.global_indices(), await news.macro())

    blades = {"price": price, "oi": oi, "greeks": grk, "volume": vol, "sentiment": senti}
    score  = round(signal_fusion.fuse_scores(blades), 1)
    side   = signal_fusion.direction(blades)

    return {"ok": True, "hint": {"side": side, "score": score}, "blades": blades}
