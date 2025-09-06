import os
import time
import json
from typing import Any, Dict, Tuple

import requests
import streamlit as st

# -----------------------------
# Config & theming
# -----------------------------
st.set_page_config(
    page_title="Options Analysis – Sudarshan (Head UI)",
    page_icon="🛡️",
    layout="wide",
)

PRIMARY = "#3B82F6"  # Tailwind blue-500
GOOD = "#22C55E"     # green-500
BAD = "#EF4444"      # red-500
NEUTRAL = "#A3A3A3"  # gray-400

CUSTOM_CSS = f"""
<style>
/* tighter paddings & pretty cards */
.block-container {{ padding-top: 1rem; padding-bottom: 2rem; }}
.small-badge {{
  display:inline-block; padding:.2rem .5rem; border-radius:.5rem; font-size:.8rem;
  color:white; background:{PRIMARY}; font-weight:600;
}}
.badge-good  {{ background:{GOOD}; }}
.badge-bad   {{ background:{BAD};  }}
.badge-neutral {{ background:{NEUTRAL}; }}
.score-bar {{
  height: 10px; width:100%; background:#1F2937; border-radius:999px; overflow:hidden;
}}
.score-fill {{ height:100%; background:{PRIMARY}; }}
.mini-card {{
  background:#0B1220; border:1px solid #1f2937; border-radius:1rem; padding:.9rem;
}}
.hero-title {{
  font-size: 2.0rem; font-weight: 800; letter-spacing:.2px;
}}
.subtle {{ color:#94a3b8; font-size:.9rem; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -----------------------------
# Helpers
# -----------------------------
def api_base_default() -> str:
    # 1) environment → 2) sidebar text default
    return os.getenv("API_BASE", "http://127.0.0.1:8000").rstrip("/")

def get_json(url: str, timeout=10) -> Tuple[bool, Dict[str, Any] | str]:
    try:
        r = requests.get(url, timeout=timeout)
        if r.headers.get("content-type", "").startswith("application/json"):
            return True, r.json()
        return False, r.text
    except Exception as e:
        return False, str(e)

def post_json(url: str, payload: Dict[str, Any], timeout=15) -> Tuple[bool, Dict[str, Any] | str]:
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        if r.headers.get("content-type", "").startswith("application/json"):
            return True, r.json()
        return False, r.text
    except Exception as e:
        return False, str(e)

def verdict_badge(verdict: str) -> str:
    v = (verdict or "").lower()
    cls = "badge-neutral"
    text = "Neutral"
    if v == "bullish":
        cls, text = "badge-good", "Bullish"
    elif v == "bearish":
        cls, text = "badge-bad", "Bearish"
    return f'<span class="small-badge {cls}">{text}</span>'

def score_meter(score: float):
    score = max(0.0, min(1.0, float(score or 0)))
    pct = int(score*100)
    st.markdown(
        f"""
        <div class="score-bar">
          <div class="score-fill" style="width:{pct}%"></div>
        </div>
        <div class="subtle" style="margin-top:.25rem">Score: {score:.3f}</div>
        """,
        unsafe_allow_html=True
    )

def mini_signal(col, title: str, content: str):
    with col:
        st.markdown(f'<div class="mini-card"><div class="subtle">{title}</div><div style="font-weight:700;margin-top:.25rem">{content}</div></div>', unsafe_allow_html=True)

# -----------------------------
# Sidebar (Backend)
# -----------------------------
with st.sidebar:
    st.markdown("### Backend")
    api_base = st.text_input("API Base", api_base_default(), help="Render ka URL ya local FastAPI.")
    api_base = api_base.rstrip("/")

    c1, c2 = st.columns(2)
    if c1.button("Health", use_container_width=True):
        ok, data = get_json(f"{api_base}/data/health")
        st.session_state["health"] = (ok, data)
    if c2.button("Selftest", use_container_width=True):
        # Self-test = /data/snapshot + env flags combine
        ok, snap = get_json(f"{api_base}/data/snapshot?symbol=NIFTY")
        st.session_state["selftest"] = (ok, snap)

    # health flash
    if "health" in st.session_state:
        ok, data = st.session_state["health"]
        color = GOOD if ok else BAD
        st.markdown(
            f"<div class='mini-card' style='border-color:{color}'>"
            f"<div class='subtle'>Health</div>"
            f"<div style='font-weight:700;margin-top:.25rem;color:{color}'>{'OK' if ok else 'ERROR'}</div>"
            f"<pre style='white-space:pre-wrap'>{json.dumps(data, indent=2) if isinstance(data, dict) else data}</pre>"
            f"</div>",
            unsafe_allow_html=True
        )

    if "selftest" in st.session_state:
        ok, data = st.session_state["selftest"]
        color = GOOD if ok else BAD
        st.markdown(
            f"<div class='mini-card' style='border-color:{color}'>"
            f"<div class='subtle'>Selftest</div>"
            f"<div style='font-weight:700;margin-top:.25rem;color:{color}'>{'OK' if ok else 'ERROR'}</div>"
            f"<pre style='white-space:pre-wrap'>{json.dumps(data, indent=2) if isinstance(data, dict) else data}</pre>"
            f"</div>",
            unsafe_allow_html=True
        )

# -----------------------------
# Hero
# -----------------------------
left, right = st.columns([0.65, 0.35])
with left:
    st.markdown('<div class="hero-title">🛡️ Options Analysis – Sudarshan</div>', unsafe_allow_html=True)
    st.caption("Head UI for snapshot + fused verdict")

with right:
    t1, t2 = st.columns(2)
    auto_refresh = t1.toggle("Auto-refresh (10s)", value=False)
    show_raw = t2.toggle("Show raw JSON", value=True)

# -----------------------------
# Controls
# -----------------------------
st.divider()
ctl1, ctl2 = st.columns([0.45, 0.55])
with ctl1:
    symbol = st.selectbox("Symbol", ["NIFTY", "BANKNIFTY"], index=0)
with ctl2:
    cols = st.columns([1, 2, 1])
    with cols[0]:
        st.write("Min Confirms")
    with cols[1]:
        min_confirms = st.slider(" ", 1, 5, 3, label_visibility="collapsed")
    with cols[2]:
        st.write("")

w1, w2, w3, w4, w5 = st.columns(5)
with w1:
    wt_price = st.number_input("Weight • Price", min_value=0.0, max_value=2.0, value=1.00, step=0.05)
with w2:
    wt_oi = st.number_input("Weight • OI", min_value=0.0, max_value=2.0, value=1.00, step=0.05)
with w3:
    wt_greeks = st.number_input("Weight • Greeks", min_value=0.0, max_value=2.0, value=0.80, step=0.05)
with w4:
    wt_volume = st.number_input("Weight • Volume", min_value=0.0, max_value=2.0, value=0.70, step=0.05)
with w5:
    wt_sentiment = st.number_input("Weight • Sentiment", min_value=0.0, max_value=2.0, value=0.50, step=0.05)

_, cta, _ = st.columns([1, 2, 1])
go = cta.button("🚀 Analyze now", use_container_width=True)

# -----------------------------
# Data fetch loop (auto refresh)
# -----------------------------
def fetch_snapshot(sym: str) -> Tuple[bool, Dict[str, Any] | str]:
    return get_json(f"{api_base}/data/snapshot?symbol={sym}")

def analyze(payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any] | str]:
    return post_json(f"{api_base}/sudarshan/analyze", payload)

def ui_once():
    ok_s, snap = fetch_snapshot(symbol)
    if not ok_s:
        st.error(f"Snapshot failed: {snap}")
        return

    # Show snapshot raw (optional)
    if show_raw:
        with st.expander("Raw snapshot", expanded=False):
            st.code(json.dumps(snap, indent=2))

    payload = {
        "min_confirms": int(min_confirms),
        "weights": {
            "price": float(wt_price),
            "oi": float(wt_oi),
            "greeks": float(wt_greeks),
            "volume": float(wt_volume),
            "sentiment": float(wt_sentiment),
        },
        "inputs": {
            "price": snap.get("sudarshan_inputs", {}).get("price", {"trend": "neutral"}),
            "oi": snap.get("sudarshan_inputs", {}).get("oi", {"signal": "neutral"}),
            "greeks": snap.get("sudarshan_inputs", {}).get("greeks", {"delta_bias": "neutral"}),
            "volume": snap.get("sudarshan_inputs", {}).get("volume", {"volume_spike": False, "confirmation": False}),
            "sentiment": snap.get("sudarshan_inputs", {}).get("sentiment", {"sentiment": "neutral"}),
        }
    }

    ok_a, out = analyze(payload)
    st.divider()
    if not ok_a:
        st.error(f"Analyze failed: {out}")
        return

    # ------------------ Results band
    topL, topR = st.columns([0.35, 0.65])
    with topL:
        verdict = (out.get("fusion", {}) or {}).get("verdict", "neutral")
        score = (out.get("fusion", {}) or {}).get("score", 0.0)
        st.markdown(verdict_badge(verdict), unsafe_allow_html=True)
        score_meter(score)

    with topR:
        cols = st.columns(5)
        sinp = out.get("sudarshan_inputs", {}) or payload["inputs"]
        mini_signal(cols[0], "Price", f"trend: {sinp.get('price',{}).get('trend','-')}")
        mini_signal(cols[1], "OI", f"signal: {sinp.get('oi',{}).get('signal','-')}")
        mini_signal(cols[2], "Greeks", f"delta_bias: {sinp.get('greeks',{}).get('delta_bias','-')}")
        v = sinp.get("volume",{})
        mini_signal(cols[3], "Volume", f"spike: {v.get('volume_spike',False)}, conf: {v.get('confirmation',False)}")
        s = sinp.get("sentiment",{})
        mini_signal(cols[4], "Sentiment", f"{s.get('sentiment','-')}")

    if show_raw:
        with st.expander("Raw analyze", expanded=False):
            st.code(json.dumps(out, indent=2))

# Run once on press OR loop for auto-refresh
if go:
    ui_once()

if auto_refresh:
    placeholder = st.empty()
    while True:
        with placeholder.container():
            ui_once()
        time.sleep(10)
        # Stop loop if user toggles off
        if not st.session_state.get("_auto_on", True) and not auto_refresh:
            break
        # persist toggle state
        st.session_state["_auto_on"] = auto_refresh
