// public/js/dashboard.js
// Works with your existing backend:
//   GET  /instruments
//   GET  /optionchain/expirylist?under_security_id=&under_exchange_segment=
//   GET  /optionchain?under_security_id=&under_exchange_segment=&expiry=YYYY-MM-DD
//   POST /ai/analyze  { prompt }
// Assumes the dashboard.html has elements with these IDs:
//   #instrumentSel #expirySel #winSel #fullChainChk #refreshBtn
//   #chainBody (tbody)  #pcrVal  #spotVal  #stepVal
//   #aiPrompt  #analyzeBtn

(() => {
  const $ = (q) => document.querySelector(q);
  const api = (path, opts={}) =>
    fetch(path, { headers: { "accept": "application/json" }, ...opts });

  // DOM refs
  const dom = {
    instrument: $('#instrumentSel'),
    expiry: $('#expirySel'),
    win: $('#winSel'),
    full: $('#fullChainChk'),
    refresh: $('#refreshBtn'),
    body: $('#chainBody'),
    pcr: $('#pcrVal'),
    spot: $('#spotVal'),
    step: $('#stepVal'),
    prompt: $('#aiPrompt'),
    analyze: $('#analyzeBtn'),
  };

  // Helpers
  const setLoading = (on) => {
    if (on) dom.refresh.disabled = true;
    else dom.refresh.disabled = false;
  };

  const safeNum = (v) => (v === null || v === undefined || Number.isNaN(v)) ? '' : v;

  const rowHTML = (r) => {
    // r = { strike, call:{oi,iv,price}, put:{oi,iv,price} }
    const c = r.call || {};
    const p = r.put || {};
    return `
      <tr>
        <td class="num">${safeNum(c.price)}</td>
        <td class="num">${safeNum(c.iv)}</td>
        <td class="num">${safeNum(c.oi)}</td>
        <td class="num">${safeNum(c.delta_oi || c.chgOi || '')}</td>
        <td class="num strong">${safeNum(r.strike)}</td>
        <td class="num">${safeNum(p.delta_oi || p.chgOi || '')}</td>
        <td class="num">${safeNum(p.oi)}</td>
        <td class="num">${safeNum(p.iv)}</td>
        <td class="num">${safeNum(p.price)}</td>
      </tr>
    `;
  };

  // Populate instruments
  async function loadInstruments() {
    const res = await api('/instruments');
    const js = await res.json();
    const items = (js && js.data) || [];
    // Keep only IDX_I and a few equities (the API already returns clean data)
    dom.instrument.innerHTML = '';
    for (const it of items) {
      const opt = document.createElement('option');
      opt.value = JSON.stringify({ id: it.id, seg: it.segment, step: it.step, name: it.name });
      opt.textContent = it.name;
      dom.instrument.appendChild(opt);
    }
  }

  // Populate expiries for current instrument
  async function loadExpiries() {
    const chosen = JSON.parse(dom.instrument.value);
    const url = `/optionchain/expirylist?under_security_id=${chosen.id}&under_exchange_segment=${encodeURIComponent(chosen.seg)}`;
    const res = await api(url);
    const js = await res.json();
    const exps = (js && js.data) || [];
    dom.expiry.innerHTML = '';
    for (const e of exps) {
      const opt = document.createElement('option');
      opt.value = e;
      opt.textContent = e;
      dom.expiry.appendChild(opt);
    }
  }

  // Render chain
  async function refreshChain() {
    setLoading(true);
    dom.body.innerHTML = '';
    try {
      const chosen = JSON.parse(dom.instrument.value);
      const expiry = dom.expiry.value;
      const url = `/optionchain?under_security_id=${chosen.id}&under_exchange_segment=${encodeURIComponent(chosen.seg)}&expiry=${expiry}`;
      const res = await api(url);
      const js = await res.json();

      // Header stats (spot/step/PCR)
      if (js && js.spot !== undefined) dom.spot.textContent = Number(js.spot).toFixed(2);
      if (chosen && chosen.step !== undefined) dom.step.textContent = String(chosen.step);
      if (js && js.summary && js.summary.pcr !== undefined) dom.pcr.textContent = js.summary.pcr;

      let rows = (js && js.rows) || (js && js.data) || [];
      // Windowing logic
      if (!dom.full.checked && rows.length > 0) {
        // Try to center around ATM (min |strike-spot|)
        let atmIdx = 0;
        if (js.spot && rows[0].strike !== undefined) {
          let best = Infinity;
          rows.forEach((r, i) => {
            const d = Math.abs(r.strike - js.spot);
            if (d < best) { best = d; atmIdx = i; }
          });
        }
        const w = parseInt(dom.win.value || '15', 10);
        const half = Math.max(1, Math.floor(w / 2));
        const start = Math.max(0, atmIdx - half);
        const end = Math.min(rows.length, start + w);
        rows = rows.slice(start, end);
      }

      // Paint
      const html = rows.map(rowHTML).join('');
      dom.body.innerHTML = html || `<tr><td colspan="9" class="muted">No rows.</td></tr>`;
    } catch (e) {
      console.error(e);
      dom.body.innerHTML = `<tr><td colspan="9" class="error">Failed to load data.</td></tr>`;
    } finally {
      setLoading(false);
    }
  }

  // AI analyze
  async function analyzeChain() {
    const promptUser = (dom.prompt.value || '').trim();
    const chosen = JSON.parse(dom.instrument.value || '{}');
    const expiry = dom.expiry.value || '';
    const context = `Instrument: ${chosen.name || ''} (${chosen.id}, ${chosen.seg}), Expiry: ${expiry}. Provide supports/resistances from OI and 2–3 trade ideas with strikes & SL.`;
    const payload = { prompt: (promptUser ? `${context}\n\nUser note: ${promptUser}` : context) };

    try {
      dom.analyze.disabled = true;
      const res = await api('/ai/analyze', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const js = await res.json();
      if (js && js.status === 'success') {
        alert(js.answer);
      } else {
        alert(js.detail || 'AI failed.');
      }
    } catch (e) {
      console.error(e);
      alert('AI request failed.');
    } finally {
      dom.analyze.disabled = false;
    }
  }

  // Event bindings
  dom.instrument.addEventListener('change', async () => {
    await loadExpiries();
    await refreshChain();
  });
  dom.expiry.addEventListener('change', refreshChain);
  dom.full.addEventListener('change', refreshChain);
  dom.win.addEventListener('change', refreshChain);
  dom.refresh.addEventListener('click', refreshChain);
  dom.analyze.addEventListener('click', analyzeChain);

  // Boot
  (async function init() {
    await loadInstruments();
    await loadExpiries();
    await refreshChain();
  })();
})();
