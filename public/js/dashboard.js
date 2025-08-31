/* Dashboard JS (no framework) */
const selInstrument = document.getElementById('instrument');
const selExpiry     = document.getElementById('expiry');
const inpWindow     = document.getElementById('window');
const chkFull       = document.getElementById('fullChain');
const btnRefresh    = document.getElementById('refreshBtn');
const spotMeta      = document.getElementById('spotMeta');
const stepMeta      = document.getElementById('stepMeta');
const bodyChain     = document.getElementById('chainBody');
const pcrEl         = document.getElementById('pcr');
const healthText    = document.getElementById('healthText');
const aiBtn         = document.getElementById('aiBtn');
const aiPrompt      = document.getElementById('aiPrompt');
const aiOut         = document.getElementById('aiOut');
const aiBadge       = document.getElementById('aiBadge');

function setHealth(msg, ok=true){ healthText.textContent = msg; healthText.className = ok? 'ok' : 'err'; }

async function selftest() {
  try {
    const r = await fetch('/__selftest');
    const j = await r.json();
    const aiOn = !!j?.status?.ai_present && !!j?.status?.base_url;
    aiBadge.textContent = `AI: ${aiOn ? 'on' : 'off'}`;
    setHealth(`${j?.status?.mode ?? '-'} · OpenAI:${aiOn?'ok':'off'}`, true);
  } catch (e) {
    setHealth('health: failed', false);
  }
}

function parseInstrumentValue() {
  try { return JSON.parse(selInstrument.value); } catch { return null; }
}

async function loadInstruments() {
  selInstrument.innerHTML = `<option>Loading…</option>`;
  try {
    const r = await fetch('/instruments');
    const j = await r.json();
    const items = j?.data || [];
    selInstrument.innerHTML = "";
    for (const it of items) {
      const opt = document.createElement('option');
      opt.value = JSON.stringify({ id: it.id, segment: it.segment, step: it.step });
      opt.textContent = it.name;
      selInstrument.appendChild(opt);
    }
    if (items.length) {
      stepMeta.textContent = items[0].step ?? '—';
      await loadExpiries();
    }
  } catch (e) {
    selInstrument.innerHTML = `<option>Error loading instruments</option>`;
    console.error(e);
  }
}

async function loadExpiries() {
  const sel = parseInstrumentValue();
  if (!sel) return;
  selExpiry.innerHTML = `<option>Loading…</option>`;
  try {
    const url = `/optionchain/expirylist?under_security_id=${sel.id}&under_exchange_segment=${sel.segment}`;
    const r = await fetch(url);
    const j = await r.json();
    const arr = j?.data || [];
    selExpiry.innerHTML = "";
    for (const d of arr) {
      const opt = document.createElement('option');
      opt.value = d; opt.textContent = d;
      selExpiry.appendChild(opt);
    }
  } catch (e) {
    selExpiry.innerHTML = `<option>Error loading expiries</option>`;
    console.error(e);
  }
}

function clearTable(msg='No rows.') {
  bodyChain.innerHTML = `<tr><td colspan="9" class="muted" style="text-align:center">${msg}</td></tr>`;
  pcrEl.textContent = '—';
  spotMeta.textContent = '—';
}

function fmt(x, d=2) { if (x===null || x===undefined || Number.isNaN(+x)) return '—'; return (+x).toFixed(d); }
function rowHtml(o){
  const ce = o.call || o.ce || {};
  const pe = o.put  || o.pe || {};
  return `<tr>
    <td>${fmt(ce.price)}</td>
    <td>${fmt(ce.iv)}</td>
    <td>${fmt(ce.oi,0)}</td>
    <td>${fmt(ce.chgOi,0)}</td>
    <td class="strike">${fmt(o.strike,0)}</td>
    <td>${fmt(pe.chgOi,0)}</td>
    <td>${fmt(pe.oi,0)}</td>
    <td>${fmt(pe.iv)}</td>
    <td>${fmt(pe.price)}</td>
  </tr>`;
}

async function refreshChain() {
  const sel = parseInstrumentValue();
  if (!sel) return;
  const exp = selExpiry.value;
  const full = chkFull.checked;
  const win = Math.max(1, Math.min(200, +inpWindow.value || 15));

  clearTable('Loading…'); btnRefresh.disabled = true;

  try {
    const url = `/optionchain?under_security_id=${sel.id}&under_exchange_segment=${sel.segment}&expiry=${encodeURIComponent(exp)}${full?'&full=true':''}&window=${win}`;
    const r = await fetch(url);
    const j = await r.json();

    // spot/step/pcr
    spotMeta.textContent = j?.spot ? fmt(j.spot,2) : '—';
    stepMeta.textContent = sel.step ?? '—';
    const pcr = j?.summary?.pcr ?? j?.pcr;
    pcrEl.textContent = pcr!==undefined ? fmt(pcr,2) : '—';

    // rows list — support multiple shapes: j.rows | j.data | j.chain
    const rows = j?.rows || j?.data || j?.chain || [];
    if (!rows.length) { clearTable('No data.'); return; }

    // window trim if server sent full
    let out = rows;
    if (!full && win && rows.length>1) {
      const atmIdx = Math.floor(rows.length/2);
      const lo = Math.max(0, atmIdx - win);
      const hi = Math.min(rows.length, atmIdx + win + 1);
      out = rows.slice(lo, hi);
    }

    bodyChain.innerHTML = out.map(rowHtml).join('');
  } catch (e) {
    console.error(e);
    clearTable('Failed to load.');
  } finally {
    btnRefresh.disabled = false;
  }
}

async function analyzeAI() {
  aiBtn.disabled = true; aiOut.textContent = 'Thinking…';
  try {
    const sel = parseInstrumentValue();
    const exp = selExpiry.value;
    const url = `/optionchain?under_security_id=${sel.id}&under_exchange_segment=${sel.segment}&expiry=${encodeURIComponent(exp)}&full=true`;
    const r = await fetch(url); const j = await r.json();
    const prompt = aiPrompt.value?.trim() || 'Analyze OI for supports/resistances and suggest one trade idea with strike and stoploss.';
    const payload = { prompt: `${prompt}\n\nData:\n${JSON.stringify(j).slice(0, 5000)}` };

    const a = await fetch('/ai/analyze', { method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(payload) });
    const aj = await a.json();
    aiOut.textContent = aj?.answer || aj?.detail || JSON.stringify(aj, null, 2);
  } catch (e) {
    aiOut.textContent = 'AI call failed.';
  } finally {
    aiBtn.disabled = false;
  }
}

// events
selInstrument.addEventListener('change', async () => { 
  const obj = parseInstrumentValue(); stepMeta.textContent = obj?.step ?? '—'; 
  await loadExpiries(); 
});
btnRefresh.addEventListener('click', refreshChain);
aiBtn.addEventListener('click', analyzeAI);

// boot
(async function init(){
  await selftest();
  await loadInstruments();
  // auto initial refresh after expiries load (small delay)
  setTimeout(()=>btnRefresh.click(), 300);
})();
