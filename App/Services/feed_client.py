# App/Services/feed_client.py
from __future__ import annotations
import os
import asyncio
import json
import logging
import struct
from typing import Dict, List, Tuple
import websockets

log = logging.getLogger("uvicorn.error")

DHAN_FEED_URL   = "wss://api-feed.dhan.co"
DHAN_TOKEN      = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
DHAN_CLIENT_ID  = os.getenv("DHAN_CLIENT_ID", "").strip()

# ---- in-memory state ----
_subscriptions: List[Tuple[str, str]] = []  # list of (segment, securityId)
_broadcast_queue: "asyncio.Queue[dict]" = asyncio.Queue()
_ws_task: asyncio.Task | None = None
_stop_event = asyncio.Event()

# ---- wire helpers ----
def _ws_url() -> str:
    if not DHAN_TOKEN or not DHAN_CLIENT_ID:
        raise RuntimeError("DHAN_ACCESS_TOKEN / DHAN_CLIENT_ID missing")
    return f"{DHAN_FEED_URL}?version=2&token={DHAN_TOKEN}&clientId={DHAN_CLIENT_ID}&authType=2"

def add_subscription(segment: str, security_id: str) -> None:
    pair = (segment, str(security_id))
    if pair not in _subscriptions:
        _subscriptions.append(pair)

def current_subscriptions() -> List[Tuple[str, str]]:
    return list(_subscriptions)

async def push_to_clients(obj: dict):
    """Put parsed tick on SSE queue."""
    try:
        await _broadcast_queue.put(obj)
    except Exception as e:
        log.warning(f"[feed] queue push failed: {e}")

async def sse_generator():
    """Async generator for SSE endpoint."""
    while True:
        item = await _broadcast_queue.get()
        yield f"data: {json.dumps(item, separators=(',',':'))}\n\n"

# ---- parsing Dhan binary packets ----
# Header: 8 bytes
# 0:1   -> response code (unsigned byte)
# 1:3   -> int16 message length (we do not use it here)
# 3:4   -> segment (unsigned byte)
# 4:8   -> int32 security id
def parse_header(buf: bytes) -> Tuple[int, int, int]:
    if len(buf) < 8:
        raise ValueError("header too short")
    code = buf[0]
    # message_len = struct.unpack_from(">H", buf, 1)[0]  # big-endian int16
    seg = buf[3]
    secid = struct.unpack_from(">I", buf, 4)[0]
    return code, seg, secid

SEG_ENUM = {
    1: "NSE_EQ",
    2: "BSE_EQ",
    3: "NSE_FNO",
    4: "BSE_FNO",
    5: "MCX_COMM",
}

def parse_ticker(buf: bytes) -> dict:
    # code=2, payload starts at byte 8:
    # 9-12 float32 LTP; 13-16 int32 LTT
    if len(buf) < 16:
        return {}
    code, seg_code, secid = parse_header(buf)
    ltp = struct.unpack_from(">f", buf, 8+1)[0]  # note: after header byte 8, spec index shows 9-12
    ltt = struct.unpack_from(">I", buf, 8+5)[0]
    return {
        "type": "ticker",
        "segment": SEG_ENUM.get(seg_code, str(seg_code)),
        "security_id": str(secid),
        "ltp": float(ltp),
        "last_trade_time": int(ltt),
    }

def parse_quote(buf: bytes) -> dict:
    # code=4 (see doc table)
    if len(buf) < 50:
        return {}
    code, seg_code, secid = parse_header(buf)
    off = 8
    ltp       = struct.unpack_from(">f", buf, off+1)[0]   # 9-12
    last_qty  = struct.unpack_from(">h", buf, off+5)[0]   # 13-14 int16
    ltt       = struct.unpack_from(">I", buf, off+7)[0]   # 15-18
    atp       = struct.unpack_from(">f", buf, off+11)[0]  # 19-22
    vol       = struct.unpack_from(">I", buf, off+15)[0]  # 23-26
    sell_qty  = struct.unpack_from(">I", buf, off+19)[0]  # 27-30
    buy_qty   = struct.unpack_from(">I", buf, off+23)[0]  # 31-34
    day_open  = struct.unpack_from(">f", buf, off+27)[0]  # 35-38
    day_close = struct.unpack_from(">f", buf, off+31)[0]  # 39-42
    day_high  = struct.unpack_from(">f", buf, off+35)[0]  # 43-46
    day_low   = struct.unpack_from(">f", buf, off+39)[0]  # 47-50

    return {
        "type": "quote",
        "segment": SEG_ENUM.get(seg_code, str(seg_code)),
        "security_id": str(secid),
        "ltp": float(ltp),
        "last_quantity": int(last_qty),
        "last_trade_time": int(ltt),
        "atp": float(atp),
        "volume": int(vol),
        "sell_quantity": int(sell_qty),
        "buy_quantity": int(buy_qty),
        "open": float(day_open),
        "close": float(day_close),
        "high": float(day_high),
        "low": float(day_low),
    }

# You can add parse_full() later if you need market depth in a single packet.

# ---- WS background loop ----
async def _send_subscribe(ws):
    if not _subscriptions:
        return
    # Dhan allows up to 100 instruments per message
    chunk = 100
    for i in range(0, len(_subscriptions), chunk):
        batch = _subscriptions[i:i+chunk]
        msg = {
            "RequestCode": 15,  # choose appropriate data mode; 15=subscribe quote (ref Annexure)
            "InstrumentCount": len(batch),
            "InstrumentList": [
                {"ExchangeSegment": seg, "SecurityId": sid} for seg, sid in batch
            ],
        }
        await ws.send(json.dumps(msg))
        await asyncio.sleep(0.05)

async def _ws_loop():
    url = _ws_url()
    log.info(f"[feed] connecting WS: {url}")
    while not _stop_event.is_set():
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                log.info("[feed] websocket connected")
                # subscribe current instruments
                await _send_subscribe(ws)

                while True:
                    msg = await ws.recv()
                    if isinstance(msg, bytes):
                        # parse header to find code
                        if len(msg) < 9:
                            continue
                        code = msg[0]
                        if code == 2:     # Ticker
                            obj = parse_ticker(msg)
                            if obj: await push_to_clients(obj)
                        elif code == 4:   # Quote
                            obj = parse_quote(msg)
                            if obj: await push_to_clients(obj)
                        elif code == 5:   # OI packet (optional)
                            # 9-12 int32 OI
                            _, seg_code, secid = parse_header(msg)
                            oi = struct.unpack_from(">I", msg, 8+1)[0]
                            await push_to_clients({
                                "type": "oi",
                                "segment": SEG_ENUM.get(seg_code, str(seg_code)),
                                "security_id": str(secid),
                                "oi": int(oi),
                            })
                        else:
                            # ignore other packet types for now
                            pass
                    else:
                        # sometimes server can send text json (errors etc.)
                        log.debug(f"[feed] text: {msg}")
        except Exception as e:
            log.warning(f"[feed] ws error: {e}; retrying in 3s")
            await asyncio.sleep(3)

async def ensure_running():
    global _ws_task
    if _ws_task is None or _ws_task.done():
        _ws_task = asyncio.create_task(_ws_loop())

async def stop():
    _stop_event.set()
    if _ws_task and not _ws_task.done():
        _ws_task.cancel()
