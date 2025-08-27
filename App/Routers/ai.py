import json, time
from fastapi import APIRouter, Body, Depends
from App.common import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL, verify_secret, logger

router = APIRouter(prefix="/ai", tags=["ai"])
_ai_client_cached = None

def _get_ai():
    global _ai_client_cached
    if _ai_client_cached is not None: return _ai_client_cached
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set; using mock AI.")
        return None
    try:
        from openai import OpenAI
        _ai_client_cached = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL or None)
    except Exception as e:
        logger.error(f"OpenAI init failed: {e}")
        _ai_client_cached = None
    return _ai_client_cached

def _complete(system_prompt: str, user_prompt: str) -> str:
    client = _get_ai()
    if client is None:
        return "AI (mock): Markets look range-bound; consider neutral spreads near ATM with tight risk."
    # Responses API
    try:
        t0 = time.time()
        resp = client.responses.create(
            model=OPENAI_MODEL,
            input=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],
            temperature=0.3,
        )
        txt = (resp.output_text or "").strip()
        logger.info(f"OpenAI responses in {(time.time()-t0)*1000:.0f}ms")
        if txt: return txt
    except Exception as e:
        logger.warning(f"responses API failed → fallback chat.completions: {e}")
    # Chat completions
    try:
        t0 = time.time()
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],
            temperature=0.3,
        )
        logger.info(f"OpenAI chat.completions in {(time.time()-t0)*1000:.0f}ms")
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"OpenAI completion failed: {e}")
        return "AI error. Please check OPENAI_API_KEY or model availability."

@router.post("/marketview")
def marketview(req: dict = Body(...), _ok: bool = Depends(verify_secret)):
    sys_p = "You are an options market analyst. Be concise and actionable."
    usr_p = "Analyze this context and give an intraday view in bullets:\n" + json.dumps(req)[:4000]
    return {"ai_reply": _complete(sys_p, usr_p)}

@router.post("/strategy")
def strategy(req: dict = Body(...), _ok: bool = Depends(verify_secret)):
    bias = req.get("bias","neutral"); risk=req.get("risk","moderate"); capital=req.get("capital",50000)
    sys_p = "You are an expert options strategist for Indian markets."
    usr_p = f"Give 1-2 structures for bias={bias}, risk={risk}, capital≈₹{capital}. Include entry, stop, target, payoff, risk/lot, adjustments."
    return {"ai_strategy": _complete(sys_p, usr_p)}

@router.post("/payoff")
def payoff(req: dict = Body(...), _ok: bool = Depends(verify_secret)):
    sys_p = "You compute payoff summaries and turning points for multi-leg option strategies."
    usr_p = "Summarize max profit/loss, breakevens and short commentary for legs:\n" + json.dumps(req)[:4000]
    return {"ai_payoff": _complete(sys_p, usr_p)}
