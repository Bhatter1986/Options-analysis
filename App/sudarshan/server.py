from fastapi import FastAPI
from App.sudarshan.config import THETA_IV, FUSION

app = FastAPI(
    title="Sudarshan Chakra Engine",
    version="1.0.0"
)

@app.get("/health")
def health_check():
    return {"status": "ok", "engine": "Sudarshan Chakra v2.0"}

# Example route for config
@app.get("/config")
def get_config():
    return {
        "theta_iv": THETA_IV,
        "fusion": FUSION
    }
