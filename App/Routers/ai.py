# App/Routers/ai.py
from fastapi import APIRouter, HTTPException
from App.Services.ai_client import get_ai_client, get_model

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/analyze")
def analyze(payload: dict):
    try:
        client = get_ai_client()
        model = get_model()
        prompt = payload.get("prompt") or "Explain the option chain in plain language."
        # minimal test call; adjust to your use
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return {"status": "success", "answer": resp.choices[0].message.content}
    except Exception as e:
        raise HTTPException(500, f"AI error: {e}")
