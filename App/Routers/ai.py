# App/Routers/ai.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError
from typing import Any, Dict, List, Optional

# Centralized client/model loaders (you already have these)
from App.Services.ai_client import get_ai_client, get_model

router = APIRouter(prefix="/ai", tags=["ai"])


# ---------- Schemas ----------
class AnalyzeReq(BaseModel):
    prompt: str = Field(
        default="Explain the option chain in plain language.",
        description="User instruction for the model.",
    )
    system: Optional[str] = Field(
        default="You are Vishnu, an options-analysis assistant. Be concise and clear.",
        description="Optional system instruction.",
    )
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(
        default=None, ge=1, description="Optional cap on output tokens."
    )
    # You can pass extra key/values if needed; we ignore unknowns gracefully.


# ---------- Helpers ----------
def _extract_text_from_response(resp: Any) -> str:
    """
    Supports both:
      - Responses API: client.responses.create(...)
      - Chat Completions: client.chat.completions.create(...)
    Returns the first text segment found.
    """
    # New Responses API shape
    try:
        if hasattr(resp, "output") and isinstance(resp.output, list):
            parts = []
            for item in resp.output:
                if getattr(item, "type", None) == "message":
                    msg = getattr(item, "content", [])
                    for seg in msg:
                        if getattr(seg, "type", None) == "text":
                            txt = getattr(seg, "text", None)
                            if txt:
                                parts.append(txt)
            if parts:
                return "\n".join(parts).strip()
    except Exception:
        pass

    # Chat Completions shape
    try:
        choices = getattr(resp, "choices", None) or resp.get("choices")  # dict fallback
        if choices:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else choices[0].message
            if isinstance(msg, dict):
                return (msg.get("content") or "").strip()
            return (getattr(msg, "content", "") or "").strip()
    except Exception:
        pass

    return ""


def _call_ai(client: Any, model: str, req: AnalyzeReq) -> str:
    """
    Prefer the new Responses API if available; otherwise fallback to chat.completions.
    We *never* pass unsupported kwargs (e.g., proxies) – only safe fields.
    """
    # Try Responses API
    try:
        if hasattr(client, "responses"):
            resp = client.responses.create(
                model=model,
                input=[{
                    "role": "system",
                    "content": req.system or "",
                }, {
                    "role": "user",
                    "content": req.prompt,
                }],
                temperature=req.temperature,
                max_output_tokens=req.max_tokens,   # Responses API name
            )
            text = _extract_text_from_response(resp)
            if text:
                return text
    except Exception:
        # Silent fallback below
        pass

    # Fallback to Chat Completions (older)
    try:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": req.system or ""},
                {"role": "user", "content": req.prompt},
            ],
            "temperature": req.temperature,
        }
        if req.max_tokens is not None:
            payload["max_tokens"] = req.max_tokens  # legacy kw name

        resp = client.chat.completions.create(**payload)
        text = _extract_text_from_response(resp)
        if text:
            return text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI call failed: {e}")

    # If both paths returned empty
    raise HTTPException(status_code=502, detail="AI returned no content.")


# ---------- Routes ----------
@router.get("/__health")
def ai_health() -> Dict[str, Any]:
    """
    Quick check: confirms client/model are resolvable.
    Useful to verify env: OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL.
    """
    try:
        client = get_ai_client()
        model = get_model()
        # minimal attribute sniff
        using_responses = bool(hasattr(client, "responses"))
        using_chat = bool(hasattr(client, "chat"))
        return {
            "ok": True,
            "model": model,
            "client_has_responses_api": using_responses,
            "client_has_chat_api": using_chat,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI health failed: {e}")


@router.post("/analyze")
def analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Primary AI endpoint.
    Body example:
    {
      "prompt": "Identify supports/resistances for BANKNIFTY options chain.",
      "system": "You are Vishnu...",
      "temperature": 0.2,
      "max_tokens": 400
    }
    """
    try:
        req = AnalyzeReq.model_validate(payload)  # robust parsing
    except ValidationError as ve:
        raise HTTPException(status_code=422, detail=ve.errors())

    try:
        client = get_ai_client()
        model = get_model()
        answer = _call_ai(client, model, req)
        return {"status": "success", "answer": answer}
    except HTTPException:
        # bubble up our clean errors
        raise
    except Exception as e:
        # Catch-all to avoid leaking stack traces
        raise HTTPException(status_code=500, detail=f"AI error: {e}")
