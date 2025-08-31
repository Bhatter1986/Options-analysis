/* Dashboard (vanilla JS) */
const selInstrument = document.getElementById("instrument");
const selExpiry = document.getElementById("expiry");
const inputWindow = document.getElementById("window");
const chkFull = document.getElementById("fullChain");
const btnRefresh = document.getElementById("refreshBtn");
const chainBody = document.getElementById("chainBody");

const meta = document.getElementById("meta");
const health = document.getElementById("health");
const pcrChip = document.getElementById("pcr");

const aiBtn = document.getElementById("aiBtn");
const aiPrompt = document.getElementById("aiPrompt");
const aiOut = document.getElementById("aiOut");

const BASE = ""; // same host

// Simple helpers
const fmt = {
  num: (n, d = 2) => (n === null || n === undefined ? "—" : Number(n).toFixed(d)),
  int: (n) => (n === null || n === undefined ? "—" : Number(n).toLocaleString("en-IN")),
};

function optEl(v, t) {
  const o = document.createElement("option");
  o.value = v; o.textContent = t ?? v;
  return o;
}

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}

// ------- Load instruments & expiry -------
async function loadInstruments() {
  // We’ll use indices endpoint (NIFTY, BANKNIFTY). If you have equities too, extend this.
  const r = await getJSON(`${BASE}/instruments/indices`);
  const list = r?.data || [];
  selInstrument.innerHTML = "";
  for (const it of list) {
    // it: { id, name, segment, step }
    selInstrument.appendChild(optEl(JSON.stringify({ id: it.id, seg: it.segment, step: it.step }), it.name));
  }
  if (list.length) {
    selInstrument.selectedIndex = 0;
    await loadExpiries();
  }
}

async function loadExpiries() {
  const { id, seg } = JSON.parse(selInstrument.value);
  selExpiry.innerHTML = "";
  const x = await getJSON(
    `${BASE}/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${encodeURIComponent(seg)}`
  );
  for (const dt of x?.data || []) selExpiry.appendChild(optEl(dt));
  if (selExpiry.options.length) selExpiry.selectedIndex = 0;
}

// ------- Render chain -------
function rowHTML(r) {
  const ce = r.call || {};
  const pe = r.put || {};
  return `
    <tr>
      <td class="num">${fmt.num(ce.price)}</td>
      <td class="num">${fmt.num(ce.iv)}</td>
      <td class="num">${fmt.num(ce.delta, 4)}</td>
      <td class="num">${fmt.num(ce.gamma, 6)}</td>
      <td class="num">${fmt.num(ce.theta, 2)}</td>
      <td class="num">${fmt.num(ce.vega, 2)}</td>
      <td class="num">${fmt.int(ce.oi)}</td>
      <td class="num ${ce.chgOi > 0 ? "good" : ce.chgOi < 0 ? "bad" : ""}">${fmt.int(ce.chgOi)}</td>

      <td class="num strike">${fmt.int(r.strike)}</td>

      <td class="num ${pe.chgOi > 0 ? "good" : pe.chgOi < 0 ? "bad" : ""}">${fmt.int(pe.chgOi)}</td>
      <td class="num">${fmt.int(pe.oi)}</td>
      <td class="num">${fmt.num(pe.vega, 2)}</td>
      <td class="num">${fmt.num(pe.theta, 2)}</td>
      <td class="num">${fmt.num(pe.gamma, 6)}</td>
      <td class="num">${fmt.num(pe.delta, 4)}</td>
      <td class="num">${fmt.num(pe.iv)}</td>
      <td class="num">${fmt.num(pe.price)}</td>
    </tr>
  `;
}

async function refreshChain() {
  try {
    btnRefresh.disabled = true;
    chainBody.innerHTML = "";

    const { id, seg, step } = JSON.parse(selInstrument.value);
    const expiry = selExpiry.value;
    const windowN = Number(inputWindow.value) || 15;
    const showAll = chkFull.checked ? "true" : "false";

    const url =
      `${BASE}/optionchain?under_security_id=${id}` +
      `&under_exchange_segment=${encodeURIComponent(seg)}` +
      `&expiry=${encodeURIComponent(expiry)}` +
      `&strikes_window=${windowN}&step=${step}&show_all=${showAll}`;

    const data = await getJSON(url);

    // header/meta
    const spot = data.spot ?? null;
    const pcr = data.summary?.pcr ?? null;
    meta.textContent = `Spot: ${fmt.num(spot)} | Step: ${step} `;
    pcrChip.textContent = `PCR: ${fmt.num(pcr, 2)}`;

    // rows
    const rows = data.chain || [];
    chainBody.innerHTML = rows.map(rowHTML).join("");

    // health line
    health.textContent =
      `Health: ok • window rows: ${data.meta?.count_window ?? rows.length} • total strikes: ${data.meta?.count_full ?? "?"}`;
  } catch (e) {
    console.error(e);
    health.textContent = `Health: error — ${e.message ?? e}`;
  } finally {
    btnRefresh.disabled = false;
  }
}

// ------- AI panel -------
async function runAI() {
  try {
    aiBtn.disabled = true;
    aiOut.textContent = "Thinking…";

    // Build a light prompt using current window rows (strikes + OI deltas)
    const { id, seg, step } = JSON.parse(selInstrument.value);
    const expiry = selExpiry.value;
    const url = `${BASE}/optionchain?under_security_id=${id}&under_exchange_segment=${encodeURIComponent(seg)}&expiry=${encodeURIComponent(expiry)}&strikes_window=${Number(inputWindow.value)||15}&step=${step}`;
    const data = await getJSON(url);
    const rows = data.chain || [];

    const brief = rows.slice(0, 25).map(r =>
      `${r.strike}: CE dOI=${r.call?.chgOi ?? 0}, PE dOI=${r.put?.chgOi ?? 0}`
    ).join("\n");

    const userPrompt = (aiPrompt.value || "").trim();
    const prompt =
      `${userPrompt ? userPrompt + "\n\n" : ""}` +
      `Instrument: ${selInstrument.options[selInstrument.selectedIndex].text} | ` +
      `Expiry: ${expiry} | PCR: ${data.summary?.pcr}\n` +
      `ATM±${Number(inputWindow.value)||15}, step=${step}\n` +
      `dOI snapshot (top ${Math.min(rows.length, 25)}):\n${brief}\n\n` +
      `Give short, practical observations (supports/resistances, bias) and 1-2 trade ideas (with entry, SL, target).`;

    const resp = await fetch(`${BASE}/ai/analyze`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    const j = await resp.json();
    if (!resp.ok) throw new Error(j?.detail || "AI error");
    aiOut.textContent = j.answer || JSON.stringify(j, null, 2);
  } catch (e) {
    aiOut.textContent = `AI error: ${e.message ?? e}`;
  } finally {
    aiBtn.disabled = false;
  }
}

// ------- Wire up -------
btnRefresh.addEventListener("click", refreshChain);
chkFull.addEventListener("change", refreshChain);
selInstrument.addEventListener("change", async () => { await loadExpiries(); await refreshChain(); });
selExpiry.addEventListener("change", refreshChain);
aiBtn.addEventListener("click", runAI);

// boot
(async function init() {
  // quick health ping
  try {
    const h = await getJSON(`${BASE}/health`);
    const ai = h?.openai_configured ? "on" : "off";
    document.getElementById("aiBadge").textContent = `AI: ${ai}`;
  } catch { /* ignore */ }

  await loadInstruments();
  await refreshChain();
})();/* Dashboard (vanilla JS) */
const selInstrument = document.getElementById('instrument');
const selExpiry     = document.getElementById('expiry');
const selWindow     = document.getElementById('window');
const chkFull       = document.getElementById('fullChain');
const btnRefresh    = document.getElementById('refreshBtn');
const spotMeta      = document.getElementById('spotMeta');
const pcrEl         = document.getElementById('pcr');
const bodyChain     = document.getElementById('chainBody');
const healthText    = document.getElementById('healthText');

const aiBtn    = document.getElementById('aiBtn');
const aiPrompt = document.getElementById('aiPrompt');
const aiOut    = document.getElementById('aiOut');

const API = location.origin;

const fmt = (n, d=2) => {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return Number(n).toFixed(d);
};
const fmt0 = (n) => fmt(n,0);

/* 1) load instruments (only indices needed for OC) */
async function loadInstruments() {
  try {
    const r = await fetch(`${API}/instruments/dhan-live`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    // Expect: {status:'success', data:[{id,name,segment,step}, ...]}
    const data = (j.data || []).filter(x => x.segment === 'IDX_I'); // Index options
    selInstrument.innerHTML = data.map(d =>
      `<option value="${d.id}|${d.segment}|${d.step}">${d.name}</option>`).join('');
  } catch (e) {
    console.error(e);
    healthText.textContent = `Health: Failed to load instruments (${e.message})`;
  }
}

/* 2) load expiries for selected instrument */
async function loadExpiries() {
  const [id, seg] = selInstrument.value.split('|');
  try {
    const r = await fetch(`${API}/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${seg}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    const exps = j.data || [];
    selExpiry.innerHTML = exps.map(x => `<option>${x}</option>`).join('');
  } catch (e) {
    console.error(e);
    healthText.textContent = `Health: Failed to load expiries (${e.message})`;
  }
}

/* 3) pull chain (with Greeks already computed by backend) */
async function refreshChain() {
  const [id, seg, step] = selInstrument.value.split('|');
  const expiry = selExpiry.value;
  const win = parseInt(selWindow.value || '15', 10);
  const showAll = chkFull.checked;

  btnRefresh.disabled = true;
  bodyChain.innerHTML = '';
  aiOut.textContent = '';

  try {
    const url = new URL(`${API}/optionchain`);
    url.searchParams.set('under_security_id', id);
    url.searchParams.set('under_exchange_segment', seg);
    url.searchParams.set('expiry', expiry);
    url.searchParams.set('show_all', showAll ? 'true' : 'false');
    url.searchParams.set('strikes_window', String(win));
    url.searchParams.set('step', step);

    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();

    const spot = j.spot ?? null;
    const pcr  = j.summary?.pcr ?? null;
    spotMeta.textContent = `Spot: ${fmt(spot,2)} | Step: ${step}`;
    pcrEl.textContent = fmt(pcr, 2);

    const rows = j.chain || [];
    const frag = document.createDocumentFragment();

    for (const it of rows) {
      const ce = it.call || {};
      const pe = it.put  || {};
      const tr = document.createElement('tr');

      const cells = [
        fmt(ce.price,2),  fmt(ce.iv,2),
        fmt(ce.delta,2),  fmt(ce.gamma,4),
        fmt(ce.theta,2),  fmt(ce.vega,2),
        fmt0(ce.oi),      fmt0(ce.chgOi),
        fmt0(it.strike),  fmt0(pe.chgOi),
        fmt0(pe.oi),      fmt(pe.vega,2),
        fmt(pe.theta,2),  fmt(pe.gamma,4),
        fmt(pe.delta,2),  fmt(pe.iv,2),
        fmt(pe.price,2),
      ];

      for (const v of cells) {
        const td = document.createElement('td');
        td.className = 'num';
        td.textContent = v;
        tr.appendChild(td);
      }
      frag.appendChild(tr);
    }
    bodyChain.appendChild(frag);
    healthText.textContent = `Health: ok · ${rows.length} rows (window: ±${win}${showAll ? ', full' : ''})`;
  } catch (e) {
    console.error(e);
    healthText.textContent = `Health: error · ${e.message}`;
  } finally {
    btnRefresh.disabled = false;
  }
}

/* 4) simple AI helper (uses /ai/analyze) */
async function runAI() {
  aiOut.textContent = 'Analyzing…';
  try {
    const req = { prompt: aiPrompt.value?.trim() || 'Summarize supports/resistances from current chain.' };
    const r = await fetch(`${API}/ai/analyze`, {
      method:'POST',
      headers:{'content-type':'application/json'},
      body: JSON.stringify(req)
    });
    const j = await r.json();
    aiOut.textContent = j.answer || JSON.stringify(j);
  } catch (e) {
    aiOut.textContent = `AI error: ${e.message}`;
  }
}

/* wire up */
selInstrument.addEventListener('change', async () => { await loadExpiries(); await refreshChain(); });
selExpiry.addEventListener('change', refreshChain);
selWindow.addEventListener('change', refreshChain);
chkFull.addEventListener('change', refreshChain);
btnRefresh.addEventListener('click', refreshChain);
aiBtn.addEventListener('click', runAI);

/* boot */
(async function init(){
  await loadInstruments();
  await loadExpiries();
  await refreshChain();
})();
