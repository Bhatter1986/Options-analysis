/* Dashboard JS (no framework) */
const selInstrument = document.getElementById('instrument');
const selExpiry     = document.getElementById('expiry');
const inpWindow     = document.getElementById('window');
const chkFull       = document.getElementById('fullChain');
const btnRefresh    = document.getElementById('refreshBtn');
const spotMeta      = document.getElementById('spotMeta');
const bodyChain     = document.getElementById('chainBody');
const pcrEl         = document.getElementById('pcr');
const healthText    = document.getElementById('healthText');
const aiBtn         = document.getElementById('aiBtn');
const aiPrompt      = document.getElementById('aiPrompt');
const aiOut         = document.getElementById('aiOut');

const qs = s => document.querySelector(s);
const API = (path) => path.startsWith('http') ? path : `${location.origin}${path}`;

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

function option(el, val, text) {
  const o = document.createElement('option');
  o.value = val; o.textContent = text; el.appendChild(o);
}

/* ---- Health ---- */
async function checkHealth() {
  try {
    const j = await getJSON(API('/__selftest'));
    const ai = j.status?.ai_present ? 'AI:ok' : 'AI:off';
    healthText.textContent = `Health: OK • mode:${j.status?.mode} • ${ai}`;
    healthText.className = 'health ok';
  } catch(e) {
    healthText.textContent = `Health: FAIL — ${e.message}`;
    healthText.className = 'health bad';
  }
}

/* ---- Instruments + Expiries ---- */
async function loadInstruments() {
  selInstrument.innerHTML = '';
  const j = await getJSON(API('/instruments'));
  j.data.forEach(x => option(selInstrument, `${x.id}|${x.segment}|${x.step}|${x.name}`, x.name));
}

async function loadExpiries() {
  selExpiry.innerHTML = '';
  const [id,segment, step] = selInstrument.value.split('|');
  const j = await getJSON(API(`/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${segment}`));
  j.data.forEach(d => option(selExpiry, d, d));
  // small meta show
  spotMeta.textContent = `Spot: — | Step: ${step}`;
}

/* ---- Chain ---- */
function fmt(n, digits=2) {
  if (n === null || n === undefined) return '—';
  return Number(n).toLocaleString(undefined, {maximumFractionDigits:digits});
}

function rowHTML(s) {
  const ce = s.call || {};
  const pe = s.put || {};
  const dCe = (ce.chgOi || 0);
  const dPe = (pe.chgOi || 0);
  return `
    <tr>
      <td class="number">${fmt(ce.price)}</td>
      <td class="number">${fmt(ce.iv)}</td>
      <td class="number">${fmt(ce.oi,0)}</td>
      <td class="number ${dCe>=0?'pos':'neg'}">${fmt(dCe,0)}</td>
      <td class="number"><b>${fmt(s.strike,0)}</b></td>
      <td class="number ${dPe>=0?'pos':'neg'}">${fmt(dPe,0)}</td>
      <td class="number">${fmt(pe.oi,0)}</td>
      <td class="number">${fmt(pe.iv)}</td>
      <td class="number">${fmt(pe.price)}</td>
    </tr>`;
}

function pickWindow(rows, spot, step, win, full) {
  if (full) return rows;
  if (!spot || !step) return rows;
  const center = Math.round(spot / step) * step;
  const lo = center - win*step, hi = center + win*step;
  return rows.filter(r => r.strike >= lo && r.strike <= hi);
}

async function loadChain() {
  btnRefresh.disabled = true;
  bodyChain.innerHTML = `<tr><td class="muted" colspan="9">Loading…</td></tr>`;
  try {
    const [id,segment, step, name] = selInstrument.value.split('|');
    const expiry = selExpiry.value;
    const j = await getJSON(API(`/optionchain?under_security_id=${id}&under_exchange_segment=${segment}&expiry=${expiry}`));
    const rows = pickWindow(j.data || [], j.spot, Number(step), Number(inpWindow.value||15), chkFull.checked);

    // header meta
    spotMeta.textContent = `Spot: ${fmt(j.spot)} | Step: ${step}`;
    pcrEl.textContent = j.summary?.pcr != null ? fmt(j.summary.pcr,2) : '—';

    if (!rows.length) {
      bodyChain.innerHTML = `<tr><td class="muted" colspan="9">No rows.</td></tr>`;
      return;
    }
    bodyChain.innerHTML = rows.map(rowHTML).join('');
  } catch(e) {
    bodyChain.innerHTML = `<tr><td class="neg" colspan="9">Error: ${e.message}</td></tr>`;
  } finally {
    btnRefresh.disabled = false;
  }
}

/* ---- AI ---- */
async function runAI() {
  aiBtn.disabled = true; aiOut.textContent = 'Thinking…';
  try {
    const prompt = aiPrompt.value?.trim() || 'Explain this options chain briefly and suggest one idea with strike & SL.';
    const payload = { prompt };
    const r = await fetch(API('/ai/analyze'), {
      method:'POST', headers:{'content-type':'application/json'},
      body: JSON.stringify(payload)
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || 'AI error');
    aiOut.textContent = j.answer || JSON.stringify(j, null, 2);
  } catch(e) {
    aiOut.textContent = `AI error: ${e.message}`;
  } finally {
    aiBtn.disabled = false;
  }
}

/* ---- Wireup ---- */
(async function init(){
  await checkHealth();
  await loadInstruments();
  await loadExpiries();
  await loadChain();

  selInstrument.addEventListener('change', async ()=>{ await loadExpiries(); await loadChain(); });
  selExpiry.addEventListener('change', loadChain);
  inpWindow.addEventListener('change', loadChain);
  chkFull.addEventListener('change', loadChain);
  btnRefresh.addEventListener('click', loadChain);
  aiBtn.addEventListener('click', runAI);
})();
