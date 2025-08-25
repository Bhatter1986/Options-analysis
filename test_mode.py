# test_mode.py
import os
import sys
sys.path.append('.')

from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "active"

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert "dhan_configured" in response.json()

def test_instruments():
    response = client.get("/instruments")
    assert response.status_code == 200
    assert "instruments" in response.json()

if __name__ == "__main__":
    test_root()
    test_health()
    test_instruments()
    print("All tests passed!")
