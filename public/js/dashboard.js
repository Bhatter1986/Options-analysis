// ====== Config (pin stable API base) ======
const apiBase = 'https://options-analysis.onrender.com';

// ====== Elements ======
const selInstrument = document.getElementById("instrument");
const selExpiry     = document.getElementById("expiry");
const inpWindow     = document.getElementById("window");
const chkFull       = document.getElementById("fullChain");
const btnRefresh    = document.getElementById("refreshBtn");
const bodyChain     = document.getElementById("chainBody");

const healthText    = document.getElementById("healthText");
const spotEl        = document.getElementById("spot");
const stepEl        = document.getElementById("step");
const pcrEl         = document.getElementById("pcr");
const pcrRightEl    = document.getElementById("pcrRight");
const maxPainEl     = document.getElementById("maxPain");
const totCeOiEl     = document.getElementById("totCeOi");
const totPeOiEl     = document.getElementById("totPeOi");

const btnLoadMore   = document.getElementById("loadMoreBtn");
const aiBtn         = document.getElementById("aiBtn");
const aiPrompt      = document.getElementById("aiPrompt");
const aiOut         = document.getElementById("aiOut");

// ====== State ======
let instruments = [];     // [{id,name,segment,step}]
let current = {
  under_security_id: null,
  under_exchange_segment: null,
  expiry: null,
  step: null,
  strikes_window: 5
};

// ====== Helpers ======
const fmt = (n, d = 2) => (n === null || n === undefined || Number.isNaN(Number(n))) ? "—" : Number(n).toFixed(d);
const int = (n) => (n === null || n === undefined || Number.isNaN(Number(n))) ? "—" : Number(n).toLocaleString("en-IN");
function setHealth(msg, ok = true){ healthText.textContent = ok ? msg : `⚠︎ ${msg}`; }

// Keep window centered around ATM
function centeredWindow(chain, spot, step, win) {
  if (!Array.isArray(chain) || !chain.length || !spot || !step) return chain || [];
  const strikes = chain.map(r => r.strike);
  const atm = strikes.reduce((a,b)=> Math.abs(b-spot)<Math.abs(a-spot)?b:a, strikes[0]);
  const lo = atm - win * step;
  const hi = atm + win * step;
  return chain.filter(r => r.strike >= lo && r.strike <= hi);
}

// ====== API ======
async function fetchJSON(url) {
  try {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return await r.json();
  } catch (e) {
    console.error("fetchJSON error:", e);
    throw e;
  }
}

async function loadInstruments() {
  setHealth("Loading instruments…");
  const data = await fetchJSON(`${apiBase}/instruments`);
  instruments = data?.data || [];
  selInstrument.innerHTML = `<option value="">Select…</option>` +
    instruments.map(i => `<option value="${i.id}" data-seg="${i.segment}" data-step="${i.step}">${i.name}</option>`).join("");
  setHealth("Instruments ready.");
}

async function loadExpiries() {
  selExpiry.innerHTML = `<option>Loading…</option>`;
  const id  = Number(selInstrument.value);
  const seg = selInstrument.selectedOptions[0]?.dataset.seg;
  const step = Number(selInstrument.selectedOptions[0]?.dataset.step || 0);

  current.under_security_id = id;
  current.under_exchange_segment = seg;
  current.step = step;

  const data = await fetchJSON(
    `${apiBase}/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${encodeURIComponent(seg)}`
  );
  const expiries = data?.data || [];
  if (!expiries.length) {
    selExpiry.innerHTML = `<option value="">(no expiries)</option>`;
    return;
  }
  selExpiry.innerHTML = expiries.map(e => `<option value="${e}">${e}</option>`).join("");
  current.expiry = selExpiry.value;
}

function renderRows(rows){
  bodyChain.innerHTML = rows.map(r => `
    <tr>
      <td>${fmt(r.call.price)}</td>
      <td>${fmt(r.call.iv)}</td>
      <td>${fmt(r.call.delta, 4)}</td>
      <td>${fmt(r.call.gamma, 6)}</td>
      <td>${fmt(r.call.theta, 4)}</td>
      <td>${fmt(r.call.vega, 2)}</td>

      <td>${int(r.call.oi)}</td>
      <td>${int(r.call.chgOi)}</td>

      <td><strong>${int(r.strike)}</strong></td>

      <td>${int(r.put.chgOi)}</td>
      <td>${int(r.put.oi)}</td>

      <td>${fmt(r.put.vega, 2)}</td>
      <td>${fmt(r.put.gamma, 6)}</td>
      <td>${fmt(r.put.delta, 4)}</td>
      <td>${fmt(r.put.iv)}</td>
      <td>${fmt(r.put.price)}</td>
    </tr>
  `).join("");
}

async function loadChain() {
  if (!current.under_security_id || !current.expiry) {
    setHealth("Select instrument & expiry, then Refresh.", false);
    return;
  }
  setHealth("Loading chain…");

  const qs = new URLSearchParams({
    under_security_id: String(current.under_security_id),
    under_exchange_segment: current.under_exchange_segment,
    expiry: current.expiry,
    strikes_window: String(current.strikes_window),
    step: String(current.step || 100),
    show_all: chkFull.checked ? "true" : "false",
  });

  const data = await fetchJSON(`${apiBase}/optionchain?${qs.toString()}`);
  const spot = data?.spot || null;
  const step = current.step || 100;
  const pcr  = data?.summary?.pcr ?? null;
  const maxPain = data?.summary?.max_pain ?? null;
  const totCeOi = data?.summary?.total_call_oi ?? null;
  const totPeOi = data?.summary?.total_put_oi ?? null;

  // rows: enforce ATM window if full not checked
  let rows = Array.isArray(data?.chain) ? data.chain : [];
  if (!chkFull.checked) rows = centeredWindow(rows, spot, step, current.strikes_window);

  // Fill summary chips
  spotEl.textContent    = fmt(spot, 2);
  stepEl.textContent    = step ? int(step) : "—";
  pcrEl.textContent     = fmt(pcr, 2);
  pcrRightEl.textContent= fmt(pcr, 2);
  maxPainEl.textContent = maxPain ? int(maxPain) : "—";
  totCeOiEl.textContent = int(totCeOi);
  totPeOiEl.textContent = int(totPeOi);

  renderRows(rows);
  setHealth(`Loaded ${rows.length} rows (window ±${current.strikes_window}).`);
}

// ====== Events ======
selInstrument.addEventListener("change", async () => {
  try {
    await loadExpiries();
    // User will hit Refresh explicitly to load chain
  } catch (e) {
    setHealth(e.message || "Failed to load expiries", false);
  }
});

selExpiry.addEventListener("change", () => {
  current.expiry = selExpiry.value;
});

inpWindow.addEventListener("change", () => {
  const v = Math.max(1, Math.min(50, Number(inpWindow.value) || 5));
  current.strikes_window = v;
});

btnRefresh.addEventListener("click", async () => {
  try { await loadChain(); } catch (e) { setHealth(e.message || "Failed to load chain", false); }
});

btnLoadMore.addEventListener("click", async () => {
  current.strikes_window += 5;
  inpWindow.value = String(current.strikes_window);
  try { await loadChain(); } catch (e) { setHealth(e.message || "Failed to load more", false); }
});

// (Optional) AI button – safe error print only
aiBtn?.addEventListener("click", async () => {
  aiOut.textContent = "Calling AI…";
  try {
    const payload = {
      prompt: aiPrompt.value?.trim() || "Analyze supports/resistances from OI & Greeks and propose a trade idea.",
    };
    const r = await fetch(`${apiBase}/ai/analyze`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload)
    });
    const j = await r.json();
    aiOut.textContent = j?.answer || JSON.stringify(j);
  } catch (e) {
    aiOut.textContent = `AI error: ${e?.message || e}`;
  }
});

// ====== Init ======
(async function init(){
  try {
    await loadInstruments();
    // (Optional) preselect first instrument to speed flow
    if (selInstrument.options.length > 1) {
      selInstrument.selectedIndex = 1; // e.g., NIFTY 50
      await loadExpiries();
    }
    setHealth("Ready.");
  } catch (e) {
    setHealth(e.message || "Init failed", false);
  }
})();
