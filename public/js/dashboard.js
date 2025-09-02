// ====== Config ======
const apiBase = ''; // same-origin (public/ + API). If you host API elsewhere, set absolute base.

// ====== Elements ======
const selInstrument = document.getElementById("instrument");
const selExpiry     = document.getElementById("expiry");
const inpWindow     = document.getElementById("window");
const chkFull       = document.getElementById("fullChain");
const btnRefresh    = document.getElementById("refreshBtn");
const bodyChain     = document.getElementById("chainBody");

const healthText = document.getElementById("healthText");
const spotEl     = document.getElementById("spot");
const stepEl     = document.getElementById("step");
const pcrEl      = document.getElementById("pcr");
const pcrRightEl = document.getElementById("pcrRight");
const maxPainEl  = document.getElementById("maxPain");
const totCeOiEl  = document.getElementById("totCeOi");
const totPeOiEl  = document.getElementById("totPeOi");

const btnLoadMore = document.getElementById("loadMoreBtn");
const aiBtn   = document.getElementById("aiBtn");
const aiPrompt= document.getElementById("aiPrompt");
const aiOut   = document.getElementById("aiOut");

// ====== State ======
let instruments = []; // {id,name,segment,step}
let current = {
  under_security_id: null,
  under_exchange_segment: null,
  expiry: null,
  step: null,
  strikes_window: 5
};
window.__chainCache = { summary: null, spot: null, step: null };

// ====== Helpers ======
const fmt = (n, d = 2) =>
  (n === null || n === undefined || Number.isNaN(Number(n))) ? "—" : Number(n).toFixed(d);
const int = (n) =>
  (n === null || n === undefined || Number.isNaN(Number(n))) ? "—" : Number(n).toLocaleString("en-IN");
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

// Build Sudarshan input from chain summary
function buildSudarshanInputs({summary, spot, step}) {
  const priceTrend = (() => {
    const mp = summary?.max_pain;
    if (!spot || !mp || !step) return "neutral";
    if (spot > mp + step)  return "bullish";
    if (spot < mp - step)  return "bearish";
    return "neutral";
  })();

  const oiSignal = (() => {
    const pcr = Number(summary?.pcr ?? 1);
    if (pcr < 0.95) return "long_buildup";     // calls tilt
    if (pcr > 1.05) return "short_buildup";    // puts tilt
    return "neutral";
  })();

  const greeksBias = (() => {
    const mp = summary?.max_pain;
    if (!spot || !mp) return "neutral";
    return spot > mp ? "long" : "short";
  })();

  return {
    price:     { trend: priceTrend },
    oi:        { signal: oiSignal },
    greeks:    { delta_bias: greeksBias },
    volume:    { volume_spike: !!summary?.volume_spike, confirmation: true },
    sentiment: { sentiment: "neutral" }
  };
}

// ====== API ======
async function fetchJSON(url, init) {
  const r = await fetch(url, { cache: "no-store", ...(init||{}) });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return await r.json();
}

async function loadInstruments() {
  setHealth("Loading instruments…");
  const data = await fetchJSON(`/instruments`);
  instruments = data?.data || [];
  selInstrument.innerHTML =
    `<option value="">Select…</option>` +
    instruments.map(i =>
      `<option value="${i.id}" data-seg="${i.segment}" data-step="${i.step}">${i.name}</option>`
    ).join("");
  setHealth("Instruments ready.");
}

async function loadExpiries() {
  selExpiry.innerHTML = `<option>Loading…</option>`;

  const id   = Number(selInstrument.value);
  const seg  = selInstrument.selectedOptions[0]?.dataset.seg;
  const step = Number(selInstrument.selectedOptions[0]?.dataset.step || 0);

  current.under_security_id       = id;
  current.under_exchange_segment  = seg;
  current.step                    = step;

  const data = await fetchJSON(
    `/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${encodeURIComponent(seg)}`
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
      <td>${fmt(r.call?.price)}</td>
      <td>${fmt(r.call?.iv)}</td>
      <td>${fmt(r.call?.delta, 4)}</td>
      <td>${fmt(r.call?.gamma, 6)}</td>
      <td>${fmt(r.call?.theta, 4)}</td>
      <td>${fmt(r.call?.vega, 2)}</td>

      <td>${int(r.call?.oi)}</td>
      <td>${int(r.call?.chgOi)}</td>

      <td><strong>${int(r.strike)}</strong></td>

      <td>${int(r.put?.chgOi)}</td>
      <td>${int(r.put?.oi)}</td>

      <td>${fmt(r.put?.vega, 2)}</td>
      <td>${fmt(r.put?.gamma, 6)}</td>
      <td>${fmt(r.put?.delta, 4)}</td>
      <td>${fmt(r.put?.iv)}</td>
      <td>${fmt(r.put?.price)}</td>
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

  const data = await fetchJSON(`/optionchain?${qs.toString()}`);

  const spot    = data?.spot ?? null;
  const step    = current.step || 100;
  const pcr     = data?.summary?.pcr ?? null;
  const maxPain = data?.summary?.max_pain ?? null;
  const totCeOi = data?.summary?.total_call_oi ?? null;
  const totPeOi = data?.summary?.total_put_oi ?? null;

  let rows = Array.isArray(data?.chain) ? data.chain : [];
  if (!chkFull.checked) rows = centeredWindow(rows, spot, step, current.strikes_window);

  // Summary chips
  spotEl.textContent      = fmt(spot, 2);
  stepEl.textContent      = step ? int(step) : "—";
  pcrEl.textContent       = fmt(pcr, 2);
  pcrRightEl.textContent  = fmt(pcr, 2);
  maxPainEl.textContent   = maxPain ? int(maxPain) : "—";
  totCeOiEl.textContent   = int(totCeOi);
  totPeOiEl.textContent   = int(totPeOi);

  renderRows(rows);
  setHealth(`Loaded ${rows.length} rows (window ±${current.strikes_window}).`);

  // cache for Sudarshan
  window.__chainCache = { summary: data?.summary || {}, spot, step };
}

// ====== Sudarshan Analyze (engine) ======
async function sudarshanAnalyze(payload) {
  return await fetchJSON(`/sudarshan/analyze`, {
    method: "POST",
    headers: {"content-type":"application/json"},
    body: JSON.stringify(payload)
  });
}

function buildPayloadForSudarshan() {
  const inputs = buildSudarshanInputs(window.__chainCache || {});
  return {
    min_confirms: 3,
    weights: { price:1, oi:1, greeks:0.8, volume:0.7, sentiment:0.5 },
    inputs
  };
}

// ====== Events ======
selInstrument.addEventListener("change", async () => {
  try {
    await loadExpiries();
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

// Reuse the AI button to trigger Sudarshan
aiBtn?.addEventListener("click", async () => {
  aiOut.textContent = "Analyzing with Sudarshan…";
  try {
    const payload = buildPayloadForSudarshan();
    const res = await sudarshanAnalyze(payload);

    // normalize some common keys across variants
    const verdict = (res.verdict?.decision || res.verdict || res.decision || "WAIT").toString().toUpperCase();
    const score   = Number(res.verdict?.score ?? res.score ?? 0);

    aiOut.textContent =
      `Verdict: ${verdict}\n` +
      `Score: ${score.toFixed(2)} | Confirms: ${res.verdict?.confirmations ?? res.confirmations ?? "—"}\n` +
      (Array.isArray(res.verdict?.reasons) ? res.verdict.reasons.map(s => `• ${s}`).join('\n') : '');

    setHealth(`Sudarshan: ${verdict} (score ${score.toFixed(2)})`);
  } catch (e) {
    aiOut.textContent = `Sudarshan error: ${e?.message || e}`;
    setHealth("Sudarshan analyze failed.", false);
  }
});

// ====== Init ======
(async function init(){
  try {
    await loadInstruments();
    if (selInstrument.options.length > 1) {
      selInstrument.selectedIndex = 1;
      await loadExpiries();
    }
    setHealth("Ready.");
  } catch (e) {
    setHealth(e.message || "Init failed", false);
  }
})();
