from fastapi import APIRouter, Body, Depends, HTTPException, Request
import os

router = APIRouter(prefix="/ai", tags=["ai"])

def verify_webhook_secret(request: Request):
    secret = os.getenv("WEBHOOK_SECRET","")
    if not secret:
        return True
    got = request.headers.get("X-Webhook-Secret")
    if got != secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    return True

@router.post("/marketview")
def marketview(req: dict = Body(...), _ok: bool = Depends(verify_webhook_secret)):
    # placeholder (mock) — Pillar-2 में real OpenAI जोड़ेंगे
    return {"ai_reply": "AI (mock): Markets look range-bound; consider neutral spreads near ATM with tight risk."}
