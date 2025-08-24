import os
import logging
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from openai import OpenAI
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# ====== CONFIG ======
MODE = os.getenv("MODE", "SANDBOX")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_LIVE_ACCESS_TOKEN") if MODE == "LIVE" else os.getenv("DHAN_SANDBOX_ACCESS_TOKEN")

# OpenAI Client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# ====== APP ======
app = FastAPI(title="Options-analysis (Dhan v2 + AI)")

# Static file serve (public/index.html)
app.mount("/static", StaticFiles(directory="public"), name="static")

@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("public/index.html")

@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    return FileResponse("public/dashboard.html")

# ====== CORS ======
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # frontend ko backend call karne ki full freedom
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== LOGGER ======
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("options-analysis")

# ====== SECURITY CHECK (middleware style) ======
def verify_secret(req: Request):
    token = req.headers.get("X-Webhook-Secret")
    if WEBHOOK_SECRET and token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid Webhook Secret")
    return True

# ====== BASIC ENDPOINTS ======
@app.get("/health")
def health():
    return {"status": "ok", "mode": MODE}

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "token_present": bool(DHAN_ACCESS_TOKEN),
        "client_id_present": bool(os.getenv("DHAN_LIVE_CLIENT_ID" if MODE == "LIVE" else "DHAN_SANDBOX_CLIENT_ID"))
    }

# ====== AI ENDPOINTS ======
@app.post("/ai/marketview")
async def ai_marketview(req: dict, auth: bool = Depends(verify_secret)):
    """Market analysis AI response"""
    try:
        prompt = f"Analyze the market data and give insights: {req}"
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return {"ai_reply": res.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail="AI marketview failed")

@app.post("/ai/strategy")
async def ai_strategy(req: dict, auth: bool = Depends(verify_secret)):
    """Suggest option trading strategy"""
    try:
        prompt = f"Suggest an options trading strategy given this data: {req}"
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return {"ai_strategy": res.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail="AI strategy failed")

@app.post("/ai/payoff")
async def ai_payoff(req: dict, auth: bool = Depends(verify_secret)):
    """AI-based payoff analysis"""
    try:
        prompt = f"Generate payoff analysis for this option strategy: {req}"
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return {"ai_payoff": res.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail="AI payoff failed")

@app.post("/ai/test")
async def ai_test(req: dict):
    """Simple AI test"""
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello, test response"}]
    )
    return {"ai_test_reply": res.choices[0].message.content}

# ====== ERROR HANDLER ======
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"error": str(exc)})
