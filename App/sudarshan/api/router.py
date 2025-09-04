from typing import Any, Dict, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..engine.orchestrator import analyze_market

router = APIRouter(prefix="/sudarshan", tags=["sudarshan"])

# ---------- Schemas ----------
class AnalyzeRequest(BaseModel):
    weights: Optional[Dict[str, float]] = None
    min_confirms: int = 3
    inputs: Dict[str, Any] = Field(default_factory=dict)

class AnalyzeResponse(BaseModel):
    version: str
    weights: Dict[str, float]
    min_confirms: int
    per_blade: Dict[str, Dict[str, Any]]
    fusion: Dict[str, Any]

@router.get("/health")
def health():
    return {"ok": True, "name": "Sudarshan", "version": "0.1.0"}

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    result = await analyze_market(req.model_dump())
    return result
