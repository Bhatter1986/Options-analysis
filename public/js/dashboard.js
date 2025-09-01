// ====== Config ======
const apiBase = window.location.origin; // e.g. https://options-analysis.onrender.com

// ====== Elements ======
const selInstrument = document.getElementById("instrument");
const selExpiry     = document.getElementById("expiry");
const inpWindow     = document.getElementById("window");
const chkFull       = document.getElementById("fullChain");
const btnRefresh    = document.getElementById("refreshBtn");
const bodyChain     = document.getElementById("chainBody");
const metaLine      = document.getElementById("metaLine");
const healthText    = document.getElementById("healthText");
const pcrEl         = document.getElementById("pcr");
const pcrRightEl    = document.getElementById("pcrRight");
const btnLoadMore   = document.getElementById("loadMoreBtn");

// ====== State ======
let instruments = [];     // [{id,name,segment,step}]
let current = {
  under_security_id: null,
  under_exchange_segment: null,
  expiry: null,
  step: null,
  strikes_window: 5       // default ATM ±5 (total ~11 rows)
};

// ====== Helpers ======
const fmt = (n, d = 2) => (n === null || n === undefined) ? "—" : Number(n).toFixed(d);
const int = (n) => (n === null || n === undefined) ? "—" : Number(n).toLocaleString("en-IN");

// Centered window: make sure ATM ± window (total rows = 2*window + 1)
function centeredWindow(chain, spot, step, win) {
  if (!Array.isArray(chain) || chain.length === 0 || !spot || !step) return chain;
  const strikes = chain.map(r => r.strike);
  const atm = strikes.reduce((a,b)=> Math.abs(b-spot)<Math.abs(a-spot)?b:a, strikes[0]);
  const lo = atm - win * step;
  const hi = atm + win * step;
  return chain.filter(r => r.strike >= lo && r.strike <= hi);
}

function setHealth(msg, ok=true) {
  healthText.textContent = ok ? msg : `⚠︎ ${msg}`;
}

// ====== API ======
async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function loadInstruments() {
  setHealth("Loading instruments…");
  const data = await fetchJSON(`${apiBase}/instruments`);
  instruments = data.data || [];
  selInstrument.innerHTML = `<option value="">Select…</option>` +
    instruments.map(i => `<option value="${i.id}" data-seg="${i.segment}" data-step="${i.step}">${i.name}</option>`).join("");
  setHealth("Instruments ready.");
}

async function loadExpiries() {
  selExpiry.innerHTML = `<option>Loading…</option>`;
  const id  = Number(selInstrument.value);
  const seg = selInstrument.selectedOptions[0]?.dataset.seg;
  const step= Number(selInstrument.selectedOptions[0]?.dataset.step || 0);
  current.under_security_id = id;
  current.under_exchange_segment = seg;
  current.step = step;

  const data = await fetchJSON(
    `${apiBase}/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${encodeURIComponent(seg)}`
  );
  const expiries = data.data || [];
  selExpiry.innerHTML = expiries.map(e => `<option value="${e}">${e}</option>`).join("");
  current.expiry = selExpiry.value;
}

async function loadChain() {
  if (!current.under_security_id || !current.expiry) return;
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
  const spot = data.spot;
  const step = current.step || 100;
  const pcr  = data.summary?.pcr;

  // if full not checked, ensure strictly ATM ± window (11 rows for window=5)
  const rows = chkFull.checked ? (data.chain || []) : centeredWindow(data.chain || [], spot, step, current.strikes_window);

  // meta lines
  pcrEl.textContent = fmt(pcr, 2);
  pcrRightEl.textContent = fmt(pcr, 2);
  metaLine.textContent = `Spot: ${fmt(spot,2)} | Step: ${step} | PCR: ${fmt(pcr,2)}`;

  // render table
  bodyChain.innerHTML = rows.map(r => `
    <tr>
      <td>${fmt(r.call.price)}</td>
      <td>${fmt(r.call.iv)}</td>
      <td>${fmt(r.call.delta, 4)}</td>
      <td>${fmt(r.call.gamma, 6)}</td>
      <td>${fmt(r.call.theta, 2)}</td>
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

  setHealth(`Loaded ${rows.length} rows (window ±${current.strikes_window}).`);
}

// ====== Events ======
selInstrument.addEventListener("change", async () => {
  try {
    await loadExpiries();
    await loadChain();
  } catch (e) {
    setHealth(e.message, false);
  }
});

selExpiry.addEventListener("change", () => {
  current.expiry = selExpiry.value;
});

inpWindow.addEventListener("change", () => {
  const v = Math.max(1, Math.min(50, Number(inpWindow.value) || 5));
  current.strikes_window = v;      // this keeps “11 rows” default (±5)
});

chkFull.addEventListener("change", () => {
  // just triggers re-render on next refresh
});

btnRefresh.addEventListener("click", async () => {
  try { await loadChain(); } catch (e) { setHealth(e.message, false); }
});

btnLoadMore.addEventListener("click", async () => {
  current.strikes_window += 5;     // +5 on each click ⇒ more rows around ATM
  inpWindow.value = String(current.strikes_window);
  try { await loadChain(); } catch (e) { setHealth(e.message, false); }
});

// ====== Init ======
(async function init() {
  try {
    await loadInstruments();
    // Optionally preselect first instrument if you want
    if (selInstrument.options.length > 1) {
      selInstrument.selectedIndex = 1;
      await loadExpiries();
      await loadChain();
    }
  } catch (e) {
    setHealth(e.message, false);
  }
})();
