from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import httpx

router = APIRouter(prefix="/ai", tags=["AI"])

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "30"))

if not OPENAI_API_KEY:
    print("⚠️ WARNING: OPENAI_API_KEY not set. AI endpoints will fail.")

class AIRequest(BaseModel):
    prompt: str

@router.post("/ask")
async def ask_ai(req: AIRequest):
    """
    Ask AI a question. Example:
    POST /ai/ask { "prompt": "What is PCR in options?" }
    """
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY missing")

    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "You are an AI assistant for Options Analysis."},
                {"role": "user", "content": req.prompt},
            ],
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
            resp = await client.post(f"{OPENAI_BASE_URL}/chat/completions",
                                     headers=headers, json=payload)

        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        data = resp.json()
        answer = data["choices"][0]["message"]["content"]

        return {"status": "success", "answer": answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI request failed: {str(e)}")
