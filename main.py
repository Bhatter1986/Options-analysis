from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello India Market 🚀"}

@app.get("/health")
def health():
    return {"ok": True}
