# App/Routers/live_feed.py
from __future__ import annotations
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from App.Services.feed_client import (
    ensure_running,
    add_subscription,
    current_subscriptions,
    sse_generator,
)

router = APIRouter(prefix="/live", tags=["Live Feed"])

@router.post("/subscribe")
async def subscribe(payload: dict):
    """
    Body example:
    {
      "instruments": [
        {"segment": "NSE_FNO", "id": "49081"},
        {"segment": "NSE_EQ",  "id": "11536"}
      ]
    }
    """
    arr = payload.get("instruments", [])
    if not isinstance(arr, list) or not arr:
        raise HTTPException(400, "instruments[] required")

    for it in arr:
        seg = str(it.get("segment", "")).strip()
        sid = str(it.get("id", "")).strip()
        if not seg or not sid:
            raise HTTPException(400, "segment and id required")
        add_subscription(seg, sid)

    # make sure WS loop is running
    await ensure_running()
    return {"status": "ok", "count": len(current_subscriptions())}

@router.get("/subs")
async def subs():
    return {"status": "ok", "data": current_subscriptions()}

@router.get("/stream")
async def stream():
    """
    SSE stream for browser:
      const es = new EventSource('/live/stream');
      es.onmessage = (e)=> { const tick = JSON.parse(e.data); ... }
    """
    await ensure_running()
    return StreamingResponse(sse_generator(), media_type="text/event-stream")
