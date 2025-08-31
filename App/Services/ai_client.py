import os
from typing import Optional
from openai import OpenAI

_client: Optional[OpenAI] = None

def get_ai_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY missing")
        # No proxies arg -> compatible with httpx 0.27.2
        _client = OpenAI(api_key=api_key, base_url=base_url)
    return _client

def get_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
