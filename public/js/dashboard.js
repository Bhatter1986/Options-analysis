/* Dashboard (vanilla JS) */
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
