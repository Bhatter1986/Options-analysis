import os, json, time, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
import streamlit as st

# ---------- Config ----------
DEFAULT_API_BASE = os.getenv("API_BASE", "https://options-analysis.onrender.com")
HEADERS = {"Accept": "application/json"}
REQUEST_TIMEOUT = 30
MAX_WORKERS = 10

# ---------- Small helpers ----------
def normalize_base(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url):
        url = "https://" + url
    return url.rstrip("/")

def elapsed_ms(t0: float) -> int:
    return int((time.time() - t0) * 1000)

@st.cache_data(show_spinner=False, ttl=10)
def get_json_cached(base: str, path: str, params=None, method="GET", body=None, timeout=REQUEST_TIMEOUT):
    """Cache-aware wrapper; key includes base+path+params+method+body."""
    return _get_json(base, path, params=params, method=method, body=body, timeout=timeout)

def _get_json(base: str, path: str, params=None, method="GET", body=None, timeout=REQUEST_TIMEOUT):
    base = normalize_base(base)
    url = f"{base}{path}"
    t0 = time.time()
    try:
        if method == "GET":
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        else:
            r = requests.post(
                url,
                params=params,
                headers={**HEADERS, "Content-Type": "application/json"},
                data=json.dumps(body or {}),
                timeout=timeout,
            )
        ctype = r.headers.get("content-type", "")
        data = r.json() if ctype.startswith("application/json") else r.text
        return {
            "ok": r.ok,
            "status": r.status_code,
            "url": r.url,
            "time_ms": elapsed_ms(t0),
            "json": data,
        }
    except Exception as e:
        return {
            "ok": False,
            "status": None,
            "url": url,
            "time_ms": elapsed_ms(t0),
            "json": {"error": str(e)},
        }

def pretty_json(x):
    st.code(json.dumps(x, indent=2, ensure_ascii=False), language="json")

def pill(success: bool, text: str):
    color = "#16a34a" if success else "#ef4444"
    st.markdown(
        f"<span style='background:{color};color:white;padding:2px 8px;border-radius:999px;font-size:12px'>{text}</span>",
        unsafe_allow_html=True,
    )

def now_str():
    return datetime.now().strftime("%H:%M:%S")

# ---------- Sidebar (API base + quick checks) ----------
def sidebar():
    st.sidebar.header("Backend")

    # Presets for convenience
    colp1, colp2 = st.sidebar.columns(2)
    with colp1:
        if st.button("Use Render", use_container_width=True):
            st.session_state.api_base = normalize_base("https://options-analysis.onrender.com")
    with colp2:
        if st.button("Use Local 8000", use_container_width=True):
            st.session_state.api_base = normalize_base("http://127.0.0.1:8000")

    api = st.sidebar.text_input("API Base", st.session_state.get("api_base", DEFAULT_API_BASE))
    st.session_state.api_base = normalize_base(api)

    cols = st.sidebar.columns(2)
    if cols[0].button("Health", use_container_width=True):
        res = get_json_cached(st.session_state.api_base, "/data/health", method="GET", timeout=15)
        st.sidebar.write(res)

    if cols[1].button("Selftest", use_container_width=True):
        res = get_json_cached(st.session_state.api_base, "/__selftest")
        st.sidebar.write(res["json"])

# ---------- Tabs ----------
def tab_all_endpoints():
    st.subheader("DHAN • All Endpoints quick fetch")
    st.caption("Important endpoints par parallel requests; status + time + JSON dikhata hai.")

    # --- Endpoint matrix (name, path, method, params, body)
    # NOTE: Paths mapped to tumhare FastAPI routers.
    endpoints = [
        ("Health",               "/data/health",          "GET",  None,                    None),
        ("Snapshot • NIFTY",     "/data/snapshot",        "GET",  {"symbol": "NIFTY"},     None),
        ("Snapshot • BANKNIFTY", "/data/snapshot",        "GET",  {"symbol": "BANKNIFTY"}, None),

        ("Instruments",          "/instruments",          "GET",  None,                    None),
        ("OptionChain • NIFTY",  "/optionchain",          "GET",  {"symbol": "NIFTY"},     None),
        ("OptionChain Auto",     "/optionchain_auto",     "GET",  {"symbol": "NIFTY"},     None),
        ("MarketQuote • NIFTY",  "/marketquote",          "GET",  {"symbol": "NIFTY"},     None),
        ("MarketFeed",           "/marketfeed",           "GET",  None,                    None),
        ("Historical • NIFTY",   "/historical",           "GET",  {"symbol": "NIFTY"},     None),
        ("Annexure",             "/annexure",             "GET",  None,                    None),
        ("Live Feed",            "/live_feed",            "GET",  None,                    None),

        # UI & admin helpers
        ("UI • Selftest",        "/ui/selftest",          "GET",  None,                    None),
        ("Admin • Refresh",      "/admin/refresh",        "POST", None,                    {"what": "instruments"}),

        # Sudarshan sample POST (lightweight—real run Sudarshan tab me)
        ("Sudarshan • Dry",      "/sudarshan/analyze",    "POST", None, {
            "min_confirms": 3,
            "weights": {"price": 1.0, "oi": 1.0, "greeks": 0.8, "volume": 0.7, "sentiment": 0.5},
            "inputs": {
                "price": {"trend": "bullish"},
                "oi": {"signal": "bullish"},
                "greeks": {"delta_bias": "long"},
                "volume": {"volume_spike": True, "confirmation": True},
                "sentiment": {"sentiment": "neutral"}
            }
        }),
    ]

    run = st.button("Fetch all now", type="primary")
    if run:
        st.info(f"Fetching {len(endpoints)} endpoints @ {st.session_state.api_base} — {now_str()}")
        progress = st.progress(0)
        rows = []
        total = len(endpoints)
        done = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs = {
                ex.submit(
                    get_json_cached,
                    st.session_state.api_base,
                    ep[1], ep[3], ep[2], ep[4]
                ): ep for ep in endpoints
            }
            for fut in as_completed(futs):
                name, path, *_ = futs[fut]
                res = fut.result()
                rows.append((name, path, res))
                done += 1
                progress.progress(done / total)

        # sort by name for stable view
        rows.sort(key=lambda r: r[0])

        for name, path, res in rows:
            c1, c2 = st.columns([0.28, 0.72])
            with c1:
                st.write(f"**{name}**")
                pill(res["ok"], f"{res['status'] or 'ERR'}")
                st.caption(f"{res['time_ms']} ms")
                with st.expander("URL"):
                    st.code(res["url"])
            with c2:
                if isinstance(res["json"], (dict, list)):
                    pretty_json(res["json"])
                else:
                    st.code(str(res["json"])[:8000])

def tab_sudarshan():
    st.subheader("Sudarshan Analysis")
    st.caption("Symbol + weights choose karke `/sudarshan/analyze` POST hota hai.")

    c0, c1 = st.columns([0.6, 0.4])
    with c0:
        symbol = st.selectbox("Symbol", ["NIFTY", "BANKNIFTY"])
        min_confirms = st.number_input("Min Confirms", 1, 5, 3, 1)
    with c1:
        auto = st.toggle("Auto-refresh (10s)", value=False)
        show_raw = st.toggle("Show raw JSON", value=True)

    st.markdown("**Weights**")
    wc = st.columns(5)
    w_price = wc[0].number_input("Price", 0.0, 2.0, 1.0, 0.05)
    w_oi    = wc[1].number_input("OI", 0.0, 2.0, 1.0, 0.05)
    w_greeks= wc[2].number_input("Greeks", 0.0, 2.0, 0.8, 0.05)
    w_vol   = wc[3].number_input("Volume", 0.0, 2.0, 0.7, 0.05)
    w_sent  = wc[4].number_input("Sentiment", 0.0, 2.0, 0.5, 0.05)

    def analyze_once():
        # optional: snapshot se backend-provided inputs
        snap = get_json_cached(st.session_state.api_base, "/data/snapshot", params={"symbol": symbol})
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
        res = _get_json(st.session_state.api_base, "/sudarshan/analyze", method="POST", body=body)

        st.write("**Request body**")
        pretty_json(body)

        st.write("**Response**")
        if res["ok"] and isinstance(res["json"], dict):
            fusion = res["json"].get("fusion", {})
            score = fusion.get("score")
            verdict = fusion.get("verdict")
            cols = st.columns(3)
            cols[0].metric("Fusion score", f"{(score or 0):.3f}")
            cols[1].metric("Verdict", str(verdict or "-"))
            cols[2].metric("Confirms", str(fusion.get("confirms", "-")))
            if show_raw:
                pretty_json(res["json"])
        else:
            st.error("Analyze failed")
            st.write(res)

    col = st.columns([0.4, 0.2, 0.4])
    run = col[1].button("🚀 Analyze now", type="primary")
    if run:
        analyze_once()

    if auto:
        st.info("Auto refresh enabled (every ~10s). Stop by toggling off.")
        holder = st.empty()
        st.session_state["_auto"] = True
        while st.session_state.get("_auto", False):
            with holder.container():
                analyze_once()
            time.sleep(10)

def tab_admin():
    st.subheader("Admin / Health")
    cols = st.columns(2)
    with cols[0]:
        h = get_json_cached(st.session_state.api_base, "/data/health")
        st.write("**/data/health**")
        pretty_json(h["json"])
    with cols[1]:
        st.write("**/__selftest**")
        t = get_json_cached(st.session_state.api_base, "/__selftest")
        pretty_json(t["json"])

    st.divider()
    st.caption("Instruments (meta)")
    instr = get_json_cached(st.session_state.api_base, "/instruments")
    pretty_json(instr["json"])

# ---------- App ----------
st.set_page_config(page_title="Options Analysis • Head UI", page_icon="🛡️", layout="wide")

if "api_base" not in st.session_state:
    st.session_state.api_base = normalize_base(DEFAULT_API_BASE)

sidebar()
st.title("Options Analysis – Head UI")

tabs = st.tabs(["🧩 All Endpoints (DHAN)", "🧠 Sudarshan", "🩺 Admin/Health"])
with tabs[0]:
    tab_all_endpoints()
with tabs[1]:
    tab_sudarshan()
with tabs[2]:
    tab_admin()
