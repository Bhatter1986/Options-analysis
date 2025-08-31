from fastapi import APIRouter, HTTPException
from App.Services.ai_client import get_ai_client, get_model

router = APIRouter(prefix="/ai", tags=["ai"])

@router.get("/__health")
def ai_health():
    try:
        client = get_ai_client()
        model = get_model()
        return {"ok": True, "model": model, "base_url": client.base_url}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.post("/analyze")
def analyze(payload: dict):
    try:
        client = get_ai_client()
        model = get_model()
        prompt = (payload.get("prompt") or "Say hello in one sentence").strip()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return {"status": "success", "answer": resp.choices[0].message.content}
    except Exception as e:
        raise HTTPException(500, f"AI error: {e}")
