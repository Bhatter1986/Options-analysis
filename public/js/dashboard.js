// ====== Config ======
const apiBase = window.location.origin; // e.g. https://options-analysis.onrender.com

// ====== Elements ======
const selInstrument = document.getElementById("instrument");
const selExpiry     = document.getElementById("expiry");
const inpWindow     = document.getElementById("window");
const chkFull       = document.getElementById("fullChain");
const btnRefresh    = document.getElementById("refreshBtn");
const bodyChain     = document.getElementById("chainBody");
const healthText    = document.getElementById("healthText");
const aiBadge       = document.getElementById("aiBadge");

const spotKpi  = document.getElementById("spotKpi");
const stepKpi  = document.getElementById("stepKpi");
const pcrKpi   = document.getElementById("pcrKpi");
const maxPainKpi = document.getElementById("maxPainKpi");
const tcoiKpi  = document.getElementById("tcoiKpi");
const tpoiKpi  = document.getElementById("tpoiKpi");
const pcrRight = document.getElementById("pcrRight");

const btnLoadMore = document.getElementById("loadMoreBtn");

const aiBtn    = document.getElementById("aiBtn");
const aiOut    = document.getElementById("aiOut");
const aiPrompt = document.getElementById("aiPrompt");

// ====== State ======
let instruments = []; // [{id,name,segment,step}]
let current = {
  under_security_id: null,
  under_exchange_segment: null,
  expiry: null,
  step: null,
  strikes_window: 5, // ATM ±5 => 11 rows
  lastChain: null,   // store last payload for AI
};

// ====== Helpers ======
const fmt = (n, d = 2) =>
  (n === null || n === undefined || Number.isNaN(Number(n))) ? "—" : Number(n).toFixed(d);
const intFmt = (n) =>
  (n === null || n === undefined || !Number.isFinite(Number(n))) ? "—" : Number(n).toLocaleString("en-IN");

function setHealth(msg, ok = true) {
  healthText.textContent = ok ? msg : `⚠︎ ${msg}`;
}

function centeredWindow(chain, spot, step, win) {
  if (!Array.isArray(chain) || chain.length === 0 || !Number.isFinite(spot) || !Number.isFinite(step)) return chain || [];
  const strikes = chain.map(r => r.strike);
  const atm = strikes.reduce((a, b) => Math.abs(b - spot) < Math.abs(a - spot) ? b : a, strikes[0]);
  const lo = atm - win * step;
  const hi = atm + win * step;
  return chain.filter(r => r.strike >= lo && r.strike <= hi);
}

// ====== API ======
async function fetchJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    const txt = await r.text().catch(() => "");
    throw new Error(`${r.status} ${r.statusText}${txt ? `: ${txt}` : ""}`);
  }
  return r.json();
}

async function loadInstruments() {
  setHealth("Loading instruments…");
  const data = await fetchJSON(`${apiBase}/instruments`);
  instruments = data?.data || [];
  // safety: only NIFTY & BANKNIFTY expected
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
  current.step = step || (id === 25 ? 100 : 50);

  const j = await fetchJSON(
    `${apiBase}/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${encodeURIComponent(seg)}`
  );
  const expiries = j?.data || [];
  selExpiry.innerHTML = expiries.map(e => `<option value="${e}">${e}</option>`).join("");
  current.expiry = selExpiry.value;
}

function renderKPIs(payload) {
  const spot = payload?.spot;
  const sum  = payload?.summary || {};
  spotKpi.textContent = fmt(spot, 2);
  stepKpi.textContent = String(current.step || "—");
  pcrKpi.textContent  = fmt(sum.pcr, 2);
  maxPainKpi.textContent = intFmt(sum.max_pain);
  tcoiKpi.textContent = intFmt(sum.total_call_oi);
  tpoiKpi.textContent = intFmt(sum.total_put_oi);
  pcrRight.textContent = fmt(sum.pcr, 2);
}

function sanitizeRow(r) {
  // never allow negative OI (ΔOI can be negative)
  r.call.oi = Math.max(0, Number(r.call.oi || 0));
  r.put.oi  = Math.max(0, Number(r.put.oi  || 0));
  return r;
}

function renderChain(payload) {
  const spot = Number(payload.spot);
  const rowsAll = (payload?.chain || []).map(sanitizeRow);

  // centered window unless "full" toggled
  let rows = chkFull.checked ? rowsAll : centeredWindow(rowsAll, spot, current.step, current.strikes_window);

  if (rows.length === 0) {
    bodyChain.innerHTML = `<tr><td colspan="16" class="muted">No rows.</td></tr>`;
    return;
  }

  bodyChain.innerHTML = rows.map(r => `
    <tr>
      <td>${fmt(r.call.price)}</td>
      <td>${fmt(r.call.iv)}</td>
      <td>${fmt(r.call.delta, 4)}</td>
      <td>${fmt(r.call.gamma, 6)}</td>
      <td>${fmt(r.call.theta, 2)}</td>
      <td>${fmt(r.call.vega, 2)}</td>
      <td>${intFmt(r.call.oi)}</td>
      <td>${intFmt(r.call.chgOi)}</td>

      <td><strong>${intFmt(r.strike)}</strong></td>

      <td>${intFmt(r.put.chgOi)}</td>
      <td>${intFmt(r.put.oi)}</td>
      <td>${fmt(r.put.vega, 2)}</td>
      <td>${fmt(r.put.gamma, 6)}</td>
      <td>${fmt(r.put.delta, 4)}</td>
      <td>${fmt(r.put.iv)}</td>
      <td>${fmt(r.put.price)}</td>
    </tr>
  `).join("");
}

async function loadChain() {
  if (!current.under_security_id || !current.expiry) return;
  setHealth("Loading chain…");

  const qs = new URLSearchParams({
    under_security_id: String(current.under_security_id),
    under_exchange_segment: current.under_exchange_segment,
    expiry: current.expiry,
    strikes_window: String(current.strikes_window),
    step: String(current.step || 50),
    show_all: chkFull.checked ? "true" : "false",
  });

  const data = await fetchJSON(`${apiBase}/optionchain?${qs.toString()}`);
  current.lastChain = data;

  renderKPIs(data);
  renderChain(data);

  const totalRows = (data?.chain || []).length;
  setHealth(`Loaded ${chkFull.checked ? totalRows : (2*current.strikes_window + 1)} rows (${chkFull.checked ? "full" : `ATM ±${current.strikes_window}`}).`);
}

// ====== AI (soft fail if quota) ======
async function analyzeAI() {
  try {
    aiOut.textContent = "Analyzing…";
    const payload = {
      prompt: aiPrompt.value?.trim() || "Explain this option chain and highlight support/resistance by OI, plus one trade idea.",
      context: current.lastChain
    };
    const r = await fetchJSON(`${apiBase}/ai/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    aiOut.textContent = r?.answer || "No answer.";
  } catch (e) {
    // 429 or any error
    aiOut.textContent = "AI unavailable (quota / config). You can continue using the chain normally.";
    aiBadge.textContent = "AI: off";
  }
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
  current.strikes_window = v; // ATM ± v ⇒ 2v+1 rows
});

chkFull.addEventListener("change", () => {
  // re-render on next refresh
});

btnRefresh.addEventListener("click", async () => {
  try { await loadChain(); } catch (e) { setHealth(e.message, false); }
});

btnLoadMore.addEventListener("click", async () => {
  current.strikes_window += 5;
  inpWindow.value = String(current.strikes_window);
  try { await loadChain(); } catch (e) { setHealth(e.message, false); }
});

aiBtn.addEventListener("click", analyzeAI);

// ====== Init ======
(async function init() {
  try {
    // if AI is configured, show badge
    try {
      const self = await fetchJSON(`${apiBase}/__selftest`);
      if (self?.status?.ai_present) aiBadge.textContent = "AI: on";
    } catch { /* ignore */ }

    await loadInstruments();

    // preselect first item for speed
    if (selInstrument.options.length > 1) {
      selInstrument.selectedIndex = 1;
      await loadExpiries();
      await loadChain();
    }
  } catch (e) {
    setHealth(e.message, false);
  }
})();
