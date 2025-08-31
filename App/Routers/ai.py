from fastapi import APIRouter, Request
from pydantic import BaseModel
import os
from openai import OpenAI

router = APIRouter(prefix="/ai", tags=["AI"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class AiRequest(BaseModel):
    question: str | None = None
    context: dict | None = None

@router.post("/analyze")
async def analyze(req: AiRequest, request: Request):
    """
    Analyze option chain data with AI
    """
    # Default prompt
    user_q = req.question or "Summarize the option chain and give key insights."

    # Context: option chain data if passed
    ctx = req.context or {}

    prompt = f"""
    You are Vishnu AI, an Options Analysis assistant.
    Question: {user_q}
    Context (option chain snapshot): {ctx}
    Give output in bullet points, short and clear.
    """

    try:
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
        )
        return {"status": "success", "answer": resp.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
