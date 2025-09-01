# App/Routers/depth20_ws.py
from __future__ import annotations
import os
import asyncio
import urllib.parse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from websockets.client import connect as ws_connect  # pip install websockets

router = APIRouter(prefix="/ws", tags=["20-Depth WS"])

DHAN_DEPTH_WS = "wss://depth-api-feed.dhan.co/twentydepth"

def _dhan_ws_url(token: str, client_id: str) -> str:
    qs = urllib.parse.urlencode({"token": token, "clientId": client_id, "authType": "2"})
    return f"{DHAN_DEPTH_WS}?{qs}"

@router.websocket("/depth20")
async def depth20_proxy(
    ws: WebSocket,
    token: str | None = Query(None, description="Optional override; otherwise env is used"),
    client_id: str | None = Query(None, description="Optional override; otherwise env is used"),
):
    """
    Transparent proxy for Dhan 20-level depth WS.
    - Client sends the same JSON subscribe payload Dhan expects (RequestCode=23).
    - We forward frames to Dhan and relay binary responses back to the browser.
    """
    await ws.accept()

    # Use env by default (do NOT expose secret to the browser)
    token = token or os.getenv("DHAN_ACCESS_TOKEN", "")
    client_id = client_id or os.getenv("DHAN_CLIENT_ID", "")
    if not token or not client_id:
        await ws.close(code=4000, reason="Missing Dhan credentials on server")
        return

    upstream_url = _dhan_ws_url(token, client_id)

    try:
        async with ws_connect(upstream_url, ping_interval=20, ping_timeout=20) as upstream:
            # 2 coroutines: client->upstream and upstream->client
            async def c2u():
                try:
                    while True:
                        # Browser may send text (JSON subscribe) or binary
                        msg = await ws.receive()
                        if "text" in msg and msg["text"] is not None:
                            await upstream.send(msg["text"])
                        elif "bytes" in msg and msg["bytes"] is not None:
                            await upstream.send(msg["bytes"])
                        else:
                            break
                except WebSocketDisconnect:
                    try:
                        await upstream.close()
                    finally:
                        return

            async def u2c():
                try:
                    async for frame in upstream:
                        if isinstance(frame, (bytes, bytearray)):
                            await ws.send_bytes(frame)
                        else:
                            # Dhan depth feed is binary, but if text ever appears, forward it
                            await ws.send_text(str(frame))
                except Exception:
                    try:
                        await ws.close()
                    finally:
                        return

            await asyncio.gather(c2u(), u2c())

    except Exception as e:
        # If connect fails or drops early
        try:
            await ws.close(code=1011, reason=f"Upstream error: {e}")
        except Exception:
            pass
