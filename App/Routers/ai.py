from fastapi import APIRouter, HTTPException
from App.Services.ai_client import ask_ai

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/ask")
def ai_ask(body: dict):
    try:
        q = (body or {}).get("q") or "Hello"
        ans = ask_ai(q)
        return {"status": "success", "answer": ans}
    except Exception as e:
        raise HTTPException(500, f"AI error: {e}")
