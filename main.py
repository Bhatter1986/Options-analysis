import os
import csv
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends, Query, Body
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

# Configuration
MODE = os.getenv("MODE", "SANDBOX").upper()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Dhan API endpoints
DHAN_BASE_URL = "https://api.dhan.co" if MODE == "LIVE" else "https://api-sandbox.dhan.co"
DHAN_API_BASE = f"{DHAN_BASE_URL}/api/v2"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dhan-options-analysis")

# Initialize FastAPI app
app = FastAPI(
    title="Dhan Options Analysis API",
    description="API for Dhan trading platform integration with OpenAI analysis",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="public"), name="static")

# Security dependency
def verify_webhook_secret(request: Request):
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Webhook-Secret")
        if token != WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")
    return True

# Dhan API helpers
def get_dhan_headers():
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail="Dhan credentials not configured")
    
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }

def handle_dhan_response(response):
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Dhan API error: {e}")
        try:
            error_detail = response.json()
        except:
            error_detail = response.text
        raise HTTPException(status_code=response.status_code, detail=error_detail)
    except Exception as e:
        logger.error(f"Error processing Dhan response: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Load instruments data
def load_instruments():
    instruments = []
    csv_path = Path("data/instruments.csv")
    
    if csv_path.exists():
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    instruments.append({
                        "security_id": int(row.get("security_id", 0)),
                        "symbol": row.get("symbol", ""),
                        "name": row.get("name", ""),
                        "instrument": row.get("instrument", ""),
                        "exchange_segment": row.get("exchange_segment", ""),
                        "strike_price": float(row.get("strike_price", 0)),
                        "expiry_date": row.get("expiry_date", ""),
                        "lot_size": int(row.get("lot_size", 0))
                    })
            logger.info(f"Loaded {len(instruments)} instruments from CSV")
        except Exception as e:
            logger.error(f"Error loading instruments: {e}")
            # Fallback to some basic instruments
            instruments = [
                {
                    "security_id": 1333,
                    "symbol": "HDFCBANK",
                    "name": "HDFC Bank Limited",
                    "instrument": "EQUITY",
                    "exchange_segment": "NSE_EQ"
                },
                {
                    "security_id": 1660,
                    "symbol": "RELIANCE",
                    "name": "Reliance Industries Limited",
                    "instrument": "EQUITY",
                    "exchange_segment": "NSE_EQ"
                },
                {
                    "security_id": 25,
                    "symbol": "BANKNIFTY",
                    "name": "Nifty Bank",
                    "instrument": "INDEX",
                    "exchange_segment": "IDX_I"
                },
                {
                    "security_id": 13,
                    "symbol": "NIFTY",
                    "name": "Nifty 50",
                    "instrument": "INDEX",
                    "exchange_segment": "IDX_I"
                }
            ]
    else:
        logger.warning("Instruments CSV not found, using fallback data")
        instruments = [
            {
                "security_id": 1333,
                "symbol": "HDFCBANK",
                "name": "HDFC Bank Limited",
                "instrument": "EQUITY",
                "exchange_segment": "NSE_EQ"
            },
            {
                "security_id": 1660,
                "symbol": "RELIANCE",
                "name": "Reliance Industries Limited",
                "instrument": "EQUITY",
                "exchange_segment": "NSE_EQ"
            },
            {
                "security_id": 25,
                "symbol": "BANKNIFTY",
                "name": "Nifty Bank",
                "instrument": "INDEX",
                "exchange_segment": "IDX_I"
            },
            {
                "security_id": 13,
                "symbol": "NIFTY",
                "name": "Nifty 50",
                "instrument": "INDEX",
                "exchange_segment": "IDX_I"
            }
        ]
    
    return instruments

# Load instruments at startup
INSTRUMENTS = load_instruments()

# Routes
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = Path("public/index.html")
    if index.path.exists():
        return FileResponse(index_path)
    return JSONResponse(
        {"ok": True, "msg": "Place your UI at public/index.html or call the JSON APIs."}
    )

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    dashboard_path = Path("public/dashboard.html")
    if dashboard_path.exists():
        return FileResponse(dashboard_path)
    raise HTTPException(status_code=404, detail="Dashboard not found")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "dhan_configured": bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN),
        "openai_configured": bool(OPENAI_API_KEY)
    }

# Dhan API Integration Endpoints
@app.get("/api/market-data")
async def get_market_data():
    try:
        # For now, return mock data until Dhan API is properly configured
        import random
        return {
            "nifty": {
                "value": round(24800 + random.random() * 200, 2),
                "change": round(random.random() * 2 - 1, 2),
                "volume": round(100 + random.random() * 50, 1)
            },
            "banknifty": {
                "value": round(52000 + random.random() * 500, 2),
                "change": round(random.random() * 2 - 1, 2),
                "volume": round(80 + random.random() * 40, 1)
            }
        }
    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch market data: {str(e)}")

@app.get("/api/expiry-dates")
async def get_expiry_dates():
    try:
        # Mock expiry dates for now
        from datetime import datetime, timedelta
        dates = []
        today = datetime.now()
        for i in range(4):
            date = today + timedelta(days=7 * (i + 1))
            dates.append(date.strftime("%Y-%m-%d"))
        return dates
    except Exception as e:
        logger.error(f"Error fetching expiry dates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch expiry dates: {str(e)}")

@app.get("/api/option-chain")
async def get_option_chain(expiry: str):
    try:
        # Mock option chain data for now
        import random
        strikes = [24800, 24900, 25000, 25100, 25200]
        chain = []
        
        for strike in strikes:
            chain.append({
                "strike": strike,
                "call": {
                    "price": round(100 + random.random() * 50, 2),
                    "oi": random.randint(10000, 25000),
                    "changeOi": random.randint(-250, 250),
                    "iv": round(15 + random.random() * 5, 1)
                },
                "put": {
                    "price": round(100 + random.random() * 50, 2),
                    "oi": random.randint(10000, 25000),
                    "changeOi": random.randint(-250, 250),
                    "iv": round(15 + random.random() * 5, 1)
                }
            })
        
        return chain
    except Exception as e:
        logger.error(f"Error fetching option chain: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch option chain: {str(e)}")

# Keep your existing endpoints here (orders, holdings, positions, etc.)
# [Include all your existing endpoints]

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "An internal server error occurred"}
    )

# This should be the last line in your file
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
