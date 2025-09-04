from typing import Any, Dict, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from ..engine.orchestrator import analyze_market
from ..config import VERSION

router = APIRouter(prefix="/sudarshan", tags=["sudarshan"])

class AnalyzeRequest(BaseModel):
    weights: Optional[Dict[str, float]] = None
    min_confirms: int = 3
    inputs: Dict[str, Any] = Field(default_factory=dict)

@router.get("/health")
def health():
    return {"ok": True, "name": "Sudarshan", "version": VERSION}

@router.post("/analyze")
async def analyze(req: AnalyzeRequest):
    return await analyze_market(req.model_dump())
