import os, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import streamlit as st

# ---------- Config ----------
DEFAULT_API_BASE = os.getenv("API_BASE", "https://options-analysis.onrender.com").rstrip("/")
HEADERS = {"Accept": "application/json"}

# ---------- Small helpers ----------
@st.cache_data(show_spinner=False, ttl=10)
def get_json(path: str, params=None, method="GET", body=None, timeout=30):
    url = f"{st.session_state.api_base}{path}"
    try:
        if method == "GET":
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        else:
            r = requests.post(url, params=params, headers={**HEADERS, "Content-Type": "application/json"}, data=json.dumps(body or {}), timeout=timeout)
        return {"ok": r.ok, "status": r.status_code, "url": r.url, "json": (r.json() if r.headers.get("content-type","").startswith("application/json") else r.text)}
    except Exception as e:
        return {"ok": False, "status": None, "url": url, "json": {"error": str(e)}}

def pretty_json(x):
    st.code(json.dumps(x, indent=2, ensure_ascii=False), language="json")

def pill(success: bool, text: str):
    color = "#16a34a" if success else "#ef4444"
    st.markdown(f"<span style='background:{color};color:white;padding:2px 8px;border-radius:999px;font-size:12px'>{text}</span>", unsafe_allow_html=True)

# ---------- Sidebar (API base + quick checks) ----------
def sidebar():
    st.sidebar.header("Backend")
    api = st.sidebar.text_input("API Base", st.session_state.get("api_base", DEFAULT_API_BASE))
    st.session_state.api_base = api.rstrip("/")
    cols = st.sidebar.columns(2)
    if cols[0].button("Health", use_container_width=True):
        res = get_json("/data/health", method="GET", timeout=15)
        st.sidebar.success("Health OK!" if res["ok"] else "Health FAIL")
        st.sidebar.write(res)
    if cols[1].button("Selftest", use_container_width=True):
        res = get_json("/ui/selftest")
        st.sidebar.write(res["json"])

# ---------- Tabs ----------
def tab_all_endpoints():
    st.subheader("DHAN • All Endpoints quick fetch")
    st.caption("Ye section sab important endpoints ko hit karke status + JSON dikhata hai.")

    # commonly used endpoints (adjust to your backend)
    endpoints = [
        ("Health", "/data/health", "GET", None, None),
        ("Snapshot (NIFTY)", "/data/snapshot", "GET", {"symbol": "NIFTY"}, None),
        ("Snapshot (BANKNIFTY)", "/data/snapshot", "GET", {"symbol": "BANKNIFTY"}, None),
        ("Instruments", "/instruments", "GET", None, None),
        ("OptionChain (NIFTY)", "/optionchain", "GET", {"symbol": "NIFTY"}, None),
        ("MarketQuote (NIFTY)", "/marketquote", "GET", {"symbol": "NIFTY"}, None),
        ("MarketFeed", "/marketfeed", "GET", None, None),
        ("Historical (NIFTY)", "/historical", "GET", {"symbol": "NIFTY"}, None),
        ("Annexure", "/annexure", "GET", None, None),
        ("Live Feed", "/live_feed", "GET", None, None),
        # add more as your API supports
    ]

    run = st.button("Fetch all now", type="primary")
    if run:
        st.info(f"Hitting {len(endpoints)} endpoints …")
        rows = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(get_json, ep[1], ep[3], ep[2], ep[4]): ep for ep in endpoints}
            for fut in as_completed(futs):
                name, path, *_ = futs[fut]
                res = fut.result()
                rows.append((name, path, res))

        # show results
        for name, path, res in rows:
            c1, c2 = st.columns([0.25, 0.75])
            with c1:
                st.write(f"**{name}**")
                pill(res["ok"], f"{res['status'] or 'ERR'}")
                st.caption(res["url"])
            with c2:
                if isinstance(res["json"], (dict, list)):
                    pretty_json(res["json"])
                else:
                    st.code(str(res["json"])[:4000])

def tab_sudarshan():
    st.subheader("Sudarshan Analysis")
    st.caption("Symbol + weights choose karke /sudarshan/analyze call hota hai.")

    c0, c1 = st.columns([0.5, 0.5])
    with c0:
        symbol = st.selectbox("Symbol", ["NIFTY", "BANKNIFTY"])
        min_confirms = st.number_input("Min Confirms", 1, 5, 3, 1)
    with c1:
        auto = st.toggle("Auto-refresh (10s)", value=False)

    st.markdown("**Weights**")
    wc = st.columns(5)
    w_price = wc[0].number_input("Price", 0.0, 2.0, 1.0, 0.05)
    w_oi    = wc[1].number_input("OI", 0.0, 2.0, 1.0, 0.05)
    w_greeks= wc[2].number_input("Greeks", 0.0, 2.0, 0.8, 0.05)
    w_vol   = wc[3].number_input("Volume", 0.0, 2.0, 0.7, 0.05)
    w_sent  = wc[4].number_input("Sentiment", 0.0, 2.0, 0.5, 0.05)

    def analyze_once():
        # get sudarshan inputs from backend snapshot helper first (optional)
        snap = get_json("/data/snapshot", params={"symbol": symbol})
        inputs = snap["json"].get("sudarshan_inputs") if isinstance(snap["json"], dict) else None
        body = {
            "min_confirms": int(min_confirms),
            "weights": {"price": w_price, "oi": w_oi, "greeks": w_greeks, "volume": w_vol, "sentiment": w_sent},
            "inputs": inputs or {
                "price": {"trend": "bullish"},
                "oi": {"signal": "bullish"},
                "greeks": {"delta_bias": "long"},
                "volume": {"volume_spike": True, "confirmation": True},
                "sentiment": {"sentiment": "neutral"}
            }
        }
        res = get_json("/sudarshan/analyze", method="POST", body=body)
        st.write("**Request body**"); pretty_json(body)
        st.write("**Response**")
        if res["ok"] and isinstance(res["json"], dict):
            pretty_json(res["json"])
            fusion = res["json"].get("fusion", {})
            score = fusion.get("score")
            verdict = fusion.get("verdict")
            if score is not None:
                st.metric("Fusion score", f"{score:.3f}", verdict)
        else:
            st.error("Analyze failed"); st.write(res)

    col = st.columns([0.4,0.2,0.4])
    run = col[1].button("🚀 Analyze now", type="primary")
    if run: analyze_once()

    if auto:
        st.info("Auto refresh enabled (every ~10s). Stop by toggling off.")
        holder = st.empty()
        while st.session_state.get("api_base") == st.session_state.api_base and st.session_state.get("_auto", True):
            with holder.container():
                analyze_once()
            time.sleep(10)
        st.session_state["_auto"] = False

def tab_admin():
    st.subheader("Admin / Health")
    h = get_json("/data/health")
    st.write("**/data/health**"); pretty_json(h["json"])
    st.divider()
    st.caption("Instruments TTL, URLs, etc.")
    instr_url = get_json("/instruments")
    pretty_json(instr_url["json"])

# ---------- App ----------
st.set_page_config(page_title="Options Analysis • Head UI", page_icon="🛡️", layout="wide")
if "api_base" not in st.session_state:
    st.session_state.api_base = DEFAULT_API_BASE

sidebar()
st.title("Options Analysis – Head UI")

tabs = st.tabs(["🧩 All Endpoints (DHAN)", "🧠 Sudarshan", "🩺 Admin/Health"])
with tabs[0]: tab_all_endpoints()
with tabs[1]: tab_sudarshan()
with tabs[2]: tab_admin()
