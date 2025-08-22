from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello India Market 🚀"}

@app.get("/health")
def health():
    return {"ok": True}
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello India Market 🚀"}

@app.get("/health")
def health():
    return {"ok": True}

# 🔽 New Endpoint: Options Analysis (dummy for now)
@app.get("/options")
def options_analysis():
    data = {
        "symbol": "NIFTY",
        "strike": 25000,
        "trend": "Bullish",
        "iv": 12.5,
        "delta": 0.62
    }
    return {"options_data": data}
