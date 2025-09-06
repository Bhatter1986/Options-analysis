import os
import requests
import streamlit as st

# Backend ka base URL (Codespaces/Render backend)
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="Options Analysis Dashboard", layout="wide")

st.sidebar.title("📊 Sudarshan Chakra Dashboard")
choice = st.sidebar.radio("Select Endpoint", ["Health", "Snapshot", "Analyze"])

if choice == "Health":
    st.header("✅ Health Check")
    url = f"{API_BASE}/data/health"
    try:
        resp = requests.get(url)
        st.json(resp.json())
    except Exception as e:
        st.error(f"Error: {e}")

elif choice == "Snapshot":
    st.header("📈 Market Snapshot")
    symbol = st.text_input("Enter Symbol", value="NIFTY")
    if st.button("Get Snapshot"):
        url = f"{API_BASE}/data/snapshot?symbol={symbol}"
        try:
            resp = requests.get(url)
            st.json(resp.json())
        except Exception as e:
            st.error(f"Error: {e}")

elif choice == "Analyze":
    st.header("🤖 Sudarshan Analyze")
    if st.button("Run Analysis"):
        payload = {
            "min_confirms": 3,
            "weights": {"price": 1, "oi": 1, "greeks": 0.8, "volume": 0.7, "sentiment": 0.5},
            "inputs": {
                "price": {"trend": "bullish"},
                "oi": {"signal": "bullish"},
                "greeks": {"delta_bias": "long"},
                "volume": {"volume_spike": True, "confirmation": True},
                "sentiment": {"sentiment": "neutral"},
            },
        }
        url = f"{API_BASE}/sudarshan/analyze"
        try:
            resp = requests.post(url, json=payload)
            st.json(resp.json())
        except Exception as e:
            st.error(f"Error: {e}")
