# main.py
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

# OpenAI helper
def get_openai_analysis(prompt: str, context: Dict = None):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured")
    
    try:
        # This would be replaced with actual OpenAI API call
        # For now, we'll simulate a response
        import random
        analyses = [
            "Based on current market conditions, a bull call spread might be profitable with strikes at 18000 and 18200.",
            "The put-call ratio indicates bearish sentiment. Consider buying puts or implementing a bear put spread.",
            "IV is elevated suggesting potential for selling options. Iron condor strategy could capture premium.",
            "Technical analysis shows strong support at 17800. Consider buying calls or implementing a bull put spread."
        ]
        
        return {
            "analysis": random.choice(analyses),
            "confidence": round(random.uniform(0.6, 0.95), 2),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"OpenAI analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"OpenAI analysis failed: {str(e)}")

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
    if index_path.exists():
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

@app.get("/instruments")
async def get_instruments(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    exchange: Optional[str] = Query(None, description="Filter by exchange segment"),
    instrument_type: Optional[str] = Query(None, description="Filter by instrument type")
):
    filtered_instruments = INSTRUMENTS
    
    if symbol:
        filtered_instruments = [i for i in filtered_instruments if symbol.lower() in i["symbol"].lower()]
    
    if exchange:
        filtered_instruments = [i for i in filtered_instruments if i["exchange_segment"] == exchange]
    
    if instrument_type:
        filtered_instruments = [i for i in filtered_instruments if i["instrument"] == instrument_type]
    
    return {"count": len(filtered_instruments), "instruments": filtered_instruments}

@app.get("/market/quote")
async def get_market_quote(
    security_id: int = Query(..., description="Security ID"),
    exchange_segment: str = Query(..., description="Exchange segment")
):
    url = f"{DHAN_API_BASE}/market-quote"
    params = {
        "securityId": security_id,
        "exchangeSegment": exchange_segment
    }
    
    try:
        response = requests.get(url, headers=get_dhan_headers(), params=params)
        data = handle_dhan_response(response)
        return data
    except Exception as e:
        logger.error(f"Error fetching market quote: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch market quote: {str(e)}")

@app.get("/options/chain")
async def get_options_chain(
    underlying_security_id: int = Query(..., description="Underlying security ID"),
    exchange_segment: str = Query(..., description="Exchange segment"),
    expiry_date: Optional[str] = Query(None, description="Expiry date in YYYY-MM-DD format")
):
    url = f"{DHAN_API_BASE}/option-chain"
    
    payload = {
        "underlyingSecurityId": underlying_security_id,
        "underlyingExchangeSegment": exchange_segment
    }
    
    if expiry_date:
        payload["expiryDate"] = expiry_date
    
    try:
        response = requests.post(url, headers=get_dhan_headers(), json=payload)
        data = handle_dhan_response(response)
        return data
    except Exception as e:
        logger.error(f"Error fetching options chain: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch options chain: {str(e)}")

@app.get("/historical/data")
async def get_historical_data(
    security_id: int = Query(..., description="Security ID"),
    exchange_segment: str = Query(..., description="Exchange segment"),
    from_date: str = Query(..., description="From date in YYYY-MM-DD format"),
    to_date: str = Query(..., description="To date in YYYY-MM-DD format"),
    interval: str = Query("1d", description="Interval: 1d, 1w, 1m, etc.")
):
    url = f"{DHAN_API_BASE}/historical"
    
    params = {
        "securityId": security_id,
        "exchangeSegment": exchange_segment,
        "fromDate": from_date,
        "toDate": to_date,
        "interval": interval
    }
    
    try:
        response = requests.get(url, headers=get_dhan_headers(), params=params)
        data = handle_dhan_response(response)
        return data
    except Exception as e:
        logger.error(f"Error fetching historical data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch historical data: {str(e)}")

@app.post("/orders/place")
async def place_order(order_data: Dict[str, Any], auth: bool = Depends(verify_webhook_secret)):
    url = f"{DHAN_API_BASE}/orders"
    
    try:
        response = requests.post(url, headers=get_dhan_headers(), json=order_data)
        data = handle_dhan_response(response)
        return data
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to place order: {str(e)}")

@app.get("/orders")
async def get_orders():
    url = f"{DHAN_API_BASE}/orders"
    
    try:
        response = requests.get(url, headers=get_dhan_headers())
        data = handle_dhan_response(response)
        return data
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch orders: {str(e)}")

@app.get("/holdings")
async def get_holdings():
    url = f"{DHAN_API_BASE}/holdings"
    
    try:
        response = requests.get(url, headers=get_dhan_headers())
        data = handle_dhan_response(response)
        return data
    except Exception as e:
        logger.error(f"Error fetching holdings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch holdings: {str(e)}")

@app.get("/positions")
async def get_positions():
    url = f"{DHAN_API_BASE}/positions"
    
    try:
        response = requests.get(url, headers=get_dhan_headers())
        data = handle_dhan_response(response)
        return data
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch positions: {str(e)}")

@app.post("/ai/analysis/options")
async def analyze_options(
    analysis_request: Dict[str, Any],
    auth: bool = Depends(verify_webhook_secret)
):
    try:
        # Extract parameters from request
        symbol = analysis_request.get("symbol", "")
        security_id = analysis_request.get("security_id")
        exchange_segment = analysis_request.get("exchange_segment")
        strategy_type = analysis_request.get("strategy_type", "general")
        
        # Get market data for analysis
        quote_url = f"{DHAN_API_BASE}/market-quote"
        quote_params = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment
        }
        
        response = requests.get(quote_url, headers=get_dhan_headers(), params=quote_params)
        market_data = handle_dhan_response(response)
        
        # Get options chain if it's an options analysis
        options_chain = None
        if "OPT" in market_data.get("instrument", ""):
            chain_url = f"{DHAN_API_BASE}/option-chain"
            chain_payload = {
                "underlyingSecurityId": security_id,
                "underlyingExchangeSegment": exchange_segment
            }
            
            response = requests.post(chain_url, headers=get_dhan_headers(), json=chain_payload)
            options_chain = handle_dhan_response(response)
        
        # Prepare context for AI analysis
        context = {
            "symbol": symbol,
            "security_id": security_id,
            "market_data": market_data,
            "options_chain": options_chain,
            "strategy_type": strategy_type,
            "timestamp": datetime.now().isoformat()
        }
        
        # Create prompt for OpenAI
        prompt = f"""
        Perform options analysis for {symbol} (ID: {security_id}) with the following market data:
        {json.dumps(market_data, indent=2)}
        
        {"Also consider this options chain data: " + json.dumps(options_chain, indent=2) if options_chain else ""}
        
        Provide:
        1. Current market analysis
        2. Recommended options strategy based on {strategy_type} approach
        3. Key levels to watch (support/resistance)
        4. Risk assessment
        """
        
        # Get AI analysis
        analysis = get_openai_analysis(prompt, context)
        
        return {
            "symbol": symbol,
            "security_id": security_id,
            "analysis": analysis,
            "market_data": market_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in options analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Options analysis failed: {str(e)}")

@app.post("/ai/analysis/strategy")
async def analyze_strategy(
    strategy_request: Dict[str, Any],
    auth: bool = Depends(verify_webhook_secret)
):
    try:
        # Extract parameters
        strategy_type = strategy_request.get("strategy_type", "bullish")
        capital = strategy_request.get("capital", 100000)
        risk_tolerance = strategy_request.get("risk_tolerance", "medium")
        symbols = strategy_request.get("symbols", [])
        
        # Get market data for all symbols
        market_data = {}
        for symbol_info in symbols:
            security_id = symbol_info.get("security_id")
            exchange_segment = symbol_info.get("exchange_segment")
            
            if security_id and exchange_segment:
                quote_url = f"{DHAN_API_BASE}/market-quote"
                quote_params = {
                    "securityId": security_id,
                    "exchangeSegment": exchange_segment
                }
                
                response = requests.get(quote_url, headers=get_dhan_headers(), params=quote_params)
                market_data[symbol_info.get("symbol")] = handle_dhan_response(response)
        
        # Prepare context for AI analysis
        context = {
            "strategy_type": strategy_type,
            "capital": capital,
            "risk_tolerance": risk_tolerance,
            "symbols": symbols,
            "market_data": market_data,
            "timestamp": datetime.now().isoformat()
        }
        
        # Create prompt for OpenAI
        prompt = f"""
        Recommend options strategies based on the following parameters:
        - Strategy bias: {strategy_type}
        - Available capital: {capital}
        - Risk tolerance: {risk_tolerance}
        - Symbols to consider: {[s.get('symbol') for s in symbols]}
        
        Market data for symbols:
        {json.dumps(market_data, indent=2)}
        
        Provide:
        1. Recommended strategies for each symbol
        2. Position sizing based on capital and risk
        3. Entry and exit guidelines
        4. Risk management techniques
        """
        
        # Get AI analysis
        analysis = get_openai_analysis(prompt, context)
        
        return {
            "strategy_type": strategy_type,
            "capital": capital,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in strategy analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Strategy analysis failed: {str(e)}")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
