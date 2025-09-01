// ===== Config =====
const apiBase = 'https://options-analysis.onrender.com';

// ===== Elements =====
const selInstrument = document.getElementById("instrument");
const selExpiry     = document.getElementById("expiry");
const inpWindow     = document.getElementById("window");
const chkFull       = document.getElementById("fullChain");
const btnRefresh    = document.getElementById("refreshBtn");
const btnLoadMore   = document.getElementById("loadMoreBtn");
const bodyChain     = document.getElementById("chainBody");
const healthText    = document.getElementById("healthText");
const spotLiveEl    = document.getElementById("spotLive");

// Chips
const stepEl      = document.getElementById("step");
const pcrEl       = document.getElementById("pcr");
const pcrRightEl  = document.getElementById("pcrRight");
const maxPainEl   = document.getElementById("maxPain");
const totCeOiEl   = document.getElementById("totCeOi");
const totPeOiEl   = document.getElementById("totPeOi");

// AI
const aiBtn   = document.getElementById("aiBtn");
const aiPrompt= document.getElementById("aiPrompt");
const aiOut   = document.getElementById("aiOut");

// Market Depth
const depthBody = document.getElementById("depthBody");

// Historical Chart
const ctx = document.getElementById("histChart").getContext("2d");
let histChart;

// ===== State =====
let instruments = [];
let current = {
  under_security_id: null,
  under_exchange_segment: null,
  expiry: null,
  step: null,
  strikes_window: 5
};

// ===== Helpers =====
const fmt = (n, d = 2) =>
  (n === null || n === undefined || Number.isNaN(Number(n))) ? "—" : Number(n).toFixed(d);
const int = (n) =>
  (n === null || n === undefined || Number.isNaN(Number(n))) ? "—" : Number(n).toLocaleString("en-IN");
function setHealth(msg, ok = true){ healthText.textContent = ok ? msg : `⚠︎ ${msg}`; }

async function fetchJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return await r.json();
}

// ===== Instruments =====
async function loadInstruments() {
  const data = await fetchJSON(`${apiBase}/instruments`);
  instruments = data?.data || [];
  selInstrument.innerHTML =
    `<option value="">Select…</option>` +
    instruments.map(i =>
      `<option value="${i.id}" data-seg="${i.segment}" data-step="${i.step}">${i.name}</option>`
    ).join("");
}

// ===== Expiries =====
async function loadExpiries() {
  const id   = Number(selInstrument.value);
  const seg  = selInstrument.selectedOptions[0]?.dataset.seg;
  const step = Number(selInstrument.selectedOptions[0]?.dataset.step || 0);

  current.under_security_id = id;
  current.under_exchange_segment = seg;
  current.step = step;

  const data = await fetchJSON(
    `${apiBase}/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${encodeURIComponent(seg)}`
  );
  const expiries = data?.data || [];
  selExpiry.innerHTML = expiries.map(e => `<option value="${e}">${e}</option>`).join("");
  current.expiry = selExpiry.value;
}

// ===== Option Chain =====
function renderRows(rows){
  bodyChain.innerHTML = rows.map(r => `
    <tr>
      <td>${fmt(r.call?.price)}</td><td>${fmt(r.call?.iv)}</td><td>${fmt(r.call?.delta, 4)}</td>
      <td>${fmt(r.call?.gamma, 6)}</td><td>${fmt(r.call?.theta, 4)}</td><td>${fmt(r.call?.vega, 2)}</td>
      <td>${int(r.call?.oi)}</td><td>${int(r.call?.chgOi)}</td>
      <td><strong>${int(r.strike)}</strong></td>
      <td>${int(r.put?.chgOi)}</td><td>${int(r.put?.oi)}</td>
      <td>${fmt(r.put?.vega, 2)}</td><td>${fmt(r.put?.gamma, 6)}</td><td>${fmt(r.put?.delta, 4)}</td>
      <td>${fmt(r.put?.iv)}</td><td>${fmt(r.put?.price)}</td>
    </tr>
  `).join("");
}

async function loadChain() {
  const qs = new URLSearchParams({
    under_security_id: String(current.under_security_id),
    under_exchange_segment: current.under_exchange_segment,
    expiry: current.expiry,
    strikes_window: String(current.strikes_window),
    step: String(current.step || 100),
    show_all: chkFull.checked ? "true" : "false",
  });
  const data = await fetchJSON(`${apiBase}/optionchain?${qs}`);
  const spot    = data?.spot ?? null;
  const pcr     = data?.summary?.pcr ?? null;
  const maxPain = data?.summary?.max_pain ?? null;
  const totCeOi = data?.summary?.total_call_oi ?? null;
  const totPeOi = data?.summary?.total_put_oi ?? null;
  renderRows(data?.chain || []);
  spotLiveEl.textContent = fmt(spot, 2);
  stepEl.textContent = int(current.step);
  pcrEl.textContent = fmt(pcr, 2);
  pcrRightEl.textContent = fmt(pcr, 2);
  maxPainEl.textContent = maxPain ? int(maxPain) : "—";
  totCeOiEl.textContent = int(totCeOi);
  totPeOiEl.textContent = int(totPeOi);
  setHealth(`Loaded ${data?.chain?.length || 0} rows.`);
}

// ===== Market Quote (Spot LTP refresh) =====
async function updateSpot() {
  if (!current.under_security_id) return;
  try {
    const data = await fetchJSON(`${apiBase}/marketquote/${current.under_security_id}?mode=ltp`);
    spotLiveEl.textContent = fmt(data?.ltp, 2);
  } catch { spotLiveEl.textContent = "—"; }
}
setInterval(updateSpot, 5000);

// ===== Market Depth =====
async function updateDepth() {
  if (!current.under_security_id) return;
  try {
    const data = await fetchJSON(`${apiBase}/depth20/${current.under_security_id}`);
    depthBody.innerHTML = "";
    const bids = data?.bids || [], asks = data?.asks || [];
    for (let i=0;i<Math.max(bids.length, asks.length);i++) {
      const b = bids[i]||{}, a = asks[i]||{};
      depthBody.innerHTML += `<tr>
        <td>${int(b.quantity)}</td><td>${fmt(b.price)}</td>
        <td>${fmt(a.price)}</td><td>${int(a.quantity)}</td></tr>`;
    }
  } catch(e){ console.error("Depth error", e); }
}
setInterval(updateDepth, 3000);

// ===== Historical Chart =====
async function loadHistorical() {
  if (!current.under_security_id) return;
  try {
    const url = `${apiBase}/historical/ohlc?ExchangeSegment=${current.under_exchange_segment}&SecurityId=${current.under_security_id}&Interval=5MIN&FromDate=2025-08-25T09:15:00&ToDate=2025-09-01T15:30:00`;
    const data = await fetchJSON(url);
    const labels = data.map(c => c.timestamp);
    const prices = data.map(c => ({o:c.open,h:c.high,l:c.low,c:c.close}));
    if (histChart) histChart.destroy();
    histChart = new Chart(ctx, {
      type: "candlestick",
      data: { labels, datasets:[{label:"OHLC", data:prices}] },
      options:{ responsive:true }
    });
  } catch(e){ console.error("Hist error", e); }
}

// ===== AI =====
aiBtn.addEventListener("click", async () => {
  aiOut.textContent = "Calling AI…";
  try {
    const payload = { prompt: aiPrompt.value.trim() || "Analyze chain" };
    const r = await fetch(`${apiBase}/ai/analyze`, {
      method:"POST", headers:{"content-type":"application/json"},
      body: JSON.stringify(payload)
    });
    const j = await r.json();
    aiOut.textContent = j?.answer || JSON.stringify(j);
  } catch(e){ aiOut.textContent=`AI error: ${e}`; }
});

// ===== Events =====
selInstrument.addEventListener("change", loadExpiries);
selExpiry.addEventListener("change", ()=> current.expiry=selExpiry.value);
inpWindow.addEventListener("change", ()=> current.strikes_window=Number(inpWindow.value)||5);
btnRefresh.addEventListener("click", loadChain);
btnLoadMore.addEventListener("click", ()=>{ current.strikes_window+=5; inpWindow.value=current.strikes_window; loadChain(); });

// ===== Init =====
(async function init(){
  await loadInstruments();
  if (selInstrument.options.length>1) {
    selInstrument.selectedIndex=1;
    await loadExpiries();
  }
  setHealth("Ready.");
})();
