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
const pcrRightEl    = document.getElementById("pcrRight");
const btnLoadMore   = document.getElementById("loadMoreBtn");
// AI (optional)
const aiBtn         = document.getElementById("aiBtn");
const aiPrompt      = document.getElementById("aiPrompt");
const aiOut         = document.getElementById("aiOut");

// ====== State ======
let instruments = []; // [{id,name,segment,step}]
let current = {
  under_security_id: null,
  under_exchange_segment: null,
  expiry: null,
  step: null,
  strikes_window: 5 // default ATM ±5 (=> 11 rows)
};
let lastChainCache = null; // keep last response for AI

// ====== Helpers ======
const fmt  = (n, d = 2) => (n === null || n === undefined || Number.isNaN(n)) ? "—" : Number(n).toFixed(d);
const fint = (n) => (n === null || n === undefined || Number.isNaN(n)) ? "—" : Number(n).toLocaleString("en-IN");
const safe = (obj, path, d = null) => {
  try { return path.split(".").reduce((o,k)=> (o && k in o ? o[k] : undefined), obj) ?? d; }
  catch { return d; }
};

function setHealth(msg, ok=true) {
  healthText.textContent = ok ? msg : `⚠︎ ${msg}`;
}

function centeredWindow(rows, spot, step, win) {
  if (!Array.isArray(rows) || rows.length === 0 || !Number.isFinite(spot) || !step) return rows || [];
  const strikes = rows.map(r => r.strike);
  let atm = strikes[0], best = Math.abs(atm - spot);
  for (let i=1;i<strikes.length;i++){
    const diff = Math.abs(strikes[i]-spot);
    if (diff < best) { best = diff; atm = strikes[i]; }
  }
  const lo = atm - win * step;
  const hi = atm + win * step;
  return rows.filter(r => r.strike >= lo && r.strike <= hi);
}

// ====== API ======
async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function loadInstruments() {
  setHealth("Loading instruments…");
  const j = await fetchJSON(`${apiBase}/instruments`);
  instruments = j.data || [];
  selInstrument.innerHTML =
    `<option value="">Select…</option>` +
    instruments.map(i => `<option value="${i.id}" data-seg="${i.segment}" data-step="${i.step}">${i.name}</option>`).join("");
  setHealth("Instruments ready.");
}

async function loadExpiries() {
  selExpiry.innerHTML = `<option>Loading…</option>`;
  const id  = Number(selInstrument.value);
  const seg = selInstrument.selectedOptions[0]?.dataset.seg || "";
  const step= Number(selInstrument.selectedOptions[0]?.dataset.step || 0);

  current.under_security_id = id;
  current.under_exchange_segment = seg;
  current.step = step;

  const j = await fetchJSON(
    `${apiBase}/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${encodeURIComponent(seg)}`
  );
  const expiries = j.data || [];
  selExpiry.innerHTML = expiries.map(e => `<option value="${e}">${e}</option>`).join("");
  current.expiry = selExpiry.value || null;
}

function renderRows(rows) {
  if (!rows || rows.length === 0) {
    bodyChain.innerHTML = `<tr><td colspan="16" class="muted">No rows.</td></tr>`;
    return;
  }
  bodyChain.innerHTML = rows.map(r => `
    <tr>
      <td>${fmt(safe(r,"call.price"))}</td>
      <td>${fmt(safe(r,"call.iv"))}</td>
      <td>${fmt(safe(r,"call.delta"),4)}</td>
      <td>${fmt(safe(r,"call.gamma"),6)}</td>
      <td>${fmt(safe(r,"call.theta"),2)}</td>
      <td>${fmt(safe(r,"call.vega"),2)}</td>

      <td>${fint(safe(r,"call.oi"))}</td>
      <td>${fint(safe(r,"call.chgOi"))}</td>

      <td><strong>${fint(r.strike)}</strong></td>

      <td>${fint(safe(r,"put.chgOi"))}</td>
      <td>${fint(safe(r,"put.oi"))}</td>

      <td>${fmt(safe(r,"put.vega"),2)}</td>
      <td>${fmt(safe(r,"put.gamma"),6)}</td>
      <td>${fmt(safe(r,"put.delta"),4)}</td>
      <td>${fmt(safe(r,"put.iv"))}</td>
      <td>${fmt(safe(r,"put.price"))}</td>
    </tr>
  `).join("");
}

async function loadChain() {
  if (!current.under_security_id || !current.expiry) {
    bodyChain.innerHTML = `<tr><td colspan="16" class="muted">Select instrument & expiry, then Refresh.</td></tr>`;
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

  const j = await fetchJSON(`${apiBase}/optionchain?${qs.toString()}`);
  lastChainCache = j;

  const spot = j.spot;
  const step = current.step || 100;
  const pcr  = safe(j,"summary.pcr");

  // window rows (ATM ± window) unless full chain checked
  const rows = chkFull.checked ? (j.chain || []) : centeredWindow(j.chain || [], spot, step, current.strikes_window);

  // meta
  metaLine.textContent = `Spot: ${fmt(spot,2)} | Step: ${step} | PCR: ${fmt(pcr,2)}`;
  pcrRightEl.textContent = fmt(pcr,2);

  // render
  renderRows(rows);
  setHealth(`Loaded ${rows.length} rows (${chkFull.checked ? "full" : `±${current.strikes_window}`} window).`);
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

selExpiry.addEventListener("change", () => { current.expiry = selExpiry.value; });

inpWindow.addEventListener("change", () => {
  const v = Math.max(1, Math.min(50, Number(inpWindow.value) || 5));
  current.strikes_window = v;
});

chkFull.addEventListener("change", () => {/* re-render on next refresh */});

btnRefresh.addEventListener("click", async () => {
  try { await loadChain(); } catch (e) { setHealth(e.message, false); }
});

btnLoadMore.addEventListener("click", async () => {
  current.strikes_window += 5;
  inpWindow.value = String(current.strikes_window);
  try { await loadChain(); } catch (e) { setHealth(e.message, false); }
});

// AI analyze (optional; safe if backend missing)
aiBtn?.addEventListener("click", async () => {
  if (!lastChainCache) {
    aiOut.textContent = "Load chain first.";
    return;
  }
  const basePrompt = (aiPrompt?.value || "").trim();
  const payload = {
    prompt:
`You are a trading assistant. Analyze the following option chain JSON and give a concise summary with 3 bullets:
- Key OI concentrations & likely support/resistance
- PCR & directional bias
- 1 simple trade idea with strike, SL, exit logic

Chain (trimmed):
${JSON.stringify({
  spot: lastChainCache.spot,
  summary: lastChainCache.summary,
  chain: (lastChainCache.chain||[]).slice(0, 31) // keep small
}, null, 2)}

User notes: ${basePrompt}`
  };
  aiOut.textContent = "Analyzing…";
  try {
    const r = await fetch(`${apiBase}/ai/analyze`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    const j = await r.json();
    aiOut.textContent = j.answer || JSON.stringify(j, null, 2);
  } catch (e) {
    aiOut.textContent = `AI error: ${e.message}`;
  }
});

// ====== Init ======
(async function init(){
  try {
    await loadInstruments();
    // auto pick first item if available
    if (selInstrument.options.length > 1) {
      selInstrument.selectedIndex = 1;
      await loadExpiries();
      await loadChain();
    } else {
      setHealth("Add items to /data/watchlist.json or ensure /instruments endpoint returns data.", false);
    }
  } catch (e) {
    setHealth(e.message, false);
  }
})();
