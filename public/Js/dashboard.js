/* public/js/dashboard.js */

(() => {
  // ---------- DOM ----------
  const els = {
    instrument: document.getElementById("instrument"),
    expiry: document.getElementById("expiry"),
    window: document.getElementById("window"),
    showFull: document.getElementById("show-full"),
    refresh: document.getElementById("refresh"),
    tbody: document.getElementById("chain-body"),
    table: document.querySelector("table"),
    aiPrompt: document.getElementById("ai-prompt"),
    aiAnalyze: document.getElementById("ai-analyze"),
    aiOutput: document.getElementById("ai-output"),
  };

  // Summary badge strip
  let badgeStrip = document.getElementById("oa-badges");
  if (!badgeStrip) {
    badgeStrip = document.createElement("div");
    badgeStrip.id = "oa-badges";
    badgeStrip.className = "d-flex gap-2 flex-wrap mb-2";
    els.table.parentElement.insertBefore(badgeStrip, els.table);
  }

  // ---------- Utilities ----------
  const DEFAULT_STEPS = { IDX_I: 50, NSE_I: 50, IDX_FO: 50, NSE_E: 10, BSE_E: 10 };
  const ID_STEPS = { 13: 50, 25: 100 }; // NIFTY, BANKNIFTY

  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const setSelectLoading = (s, msg="Loading...") => (s.innerHTML = `<option>${msg}</option>`);
  const setSelectError   = (s, msg="Error")   => (s.innerHTML = `<option>${msg}</option>`);
  const clearSelect      = (s) => (s.innerHTML = "");
  const addOption = (s, value, label, extra={}) => {
    const opt = document.createElement("option");
    opt.value = value; opt.textContent = label;
    Object.entries(extra).forEach(([k,v]) => (opt.dataset[k]=v));
    s.appendChild(opt);
  };
  const fmtNum = (n) => {
    if (n == null || Number.isNaN(n)) return "—";
    const abs = Math.abs(n);
    if (abs >= 1e7) return (n/1e7).toFixed(2) + " Cr";
    if (abs >= 1e5) return (n/1e5).toFixed(2) + " L";
    if (abs >= 1e3) return (n/1e3).toFixed(2) + " K";
    return typeof n === "number" ? n.toLocaleString("en-IN") : String(n);
  };
  const fmt2 = (n) => (n == null || Number.isNaN(n)) ? "—" : Number(n).toFixed(2);
  const field = (obj, path, d=null) => {
    try { return path.split(".").reduce((o,k)=>(o && k in o ? o[k] : undefined), obj) ?? d; }
    catch { return d; }
  };
  const badge = (title, value) => {
    const span = document.createElement("span");
    span.className = "badge rounded-pill text-bg-secondary";
    span.style.fontSize = "0.9rem";
    span.textContent = `${title}: ${value}`;
    return span;
  };
  const showBadges = ({ spot, pcr, maxPain, rows }) => {
    badgeStrip.innerHTML = "";
    badgeStrip.appendChild(badge("LTP", fmt2(spot)));
    badgeStrip.appendChild(badge("PCR", fmt2(pcr)));
    badgeStrip.appendChild(badge("Max Pain", fmtNum(maxPain)));
    badgeStrip.appendChild(badge("rows", fmtNum(rows)));
  };
  const showChainError = (msg) => {
    els.tbody.innerHTML = `<tr><td colspan="9">Error loading chain: ${msg}</td></tr>`;
  };

  // ---------- Network ----------
  async function fetchJSON(url, opts = {}) {
    const res = await fetch(url, opts);
    if (!res.ok) {
      const text = await res.text().catch(()=> "");
      throw new Error(`${res.status} ${res.statusText}: ${text || "request failed"}`);
    }
    return res.json();
  }

  // ---------- State ----------
  let lastChainData = null; // keep latest chain payload for AI

  // ---------- Loaders ----------
  async function loadInstruments() {
    setSelectLoading(els.instrument, "Loading instruments...");
    const list = [];

    // 1) local watchlist
    try {
      const w = await fetchJSON("/data/watchlist.json");
      const items = field(w, "items", []);
      for (const it of items) {
        list.push({
          id: Number(it.id),
          name: String(it.name || "").trim(),
          segment: String(it.segment || "").trim(),
          step: Number(it.step ?? ID_STEPS[it.id] ?? DEFAULT_STEPS[it.segment] ?? 50),
        });
      }
    } catch { /* ignore */ }

    // 2) backend fallback
    if (list.length === 0) {
      try {
        const j = await fetchJSON("/instruments");
        const items = field(j, "data", []);
        for (const it of items) {
          const id = Number(it.id);
          const seg = String(it.segment || "").trim();
          list.push({
            id,
            name: String(it.name || "").trim(),
            segment: seg,
            step: Number(ID_STEPS[id] ?? DEFAULT_STEPS[seg] ?? 50),
          });
        }
      } catch (e) {
        console.error("Instruments load failed:", e);
        setSelectError(els.instrument, "Error loading instruments");
        return [];
      }
    }

    clearSelect(els.instrument);
    for (const it of list) {
      addOption(els.instrument, it.id, it.name, { seg: it.segment, step: it.step });
    }
    return list;
  }

  async function loadExpiriesForSelected() {
    setSelectLoading(els.expiry, "Loading expiries...");
    const opt = els.instrument.selectedOptions[0];
    if (!opt) { setSelectError(els.expiry, "Select instrument first"); return []; }
    const id  = Number(opt.value);
    const seg = opt.dataset.seg;

    const url = `/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${seg}`;
    try {
      const j = await fetchJSON(url);
      const arr = field(j, "data", []);
      clearSelect(els.expiry);
      for (const d of arr) addOption(els.expiry, d, d);
      return arr;
    } catch (e) {
      console.error("Expiry list failed:", e);
      setSelectError(els.expiry, "Error loading exp");
      return [];
    }
  }

  // ---------- Chain ----------
  const computeATM = (strikes, spot) => {
    if (!Array.isArray(strikes) || strikes.length === 0 || typeof spot !== "number") return null;
    let best = strikes[0], bestDiff = Math.abs(strikes[0] - spot);
    for (let i = 1; i < strikes.length; i++) {
      const d = Math.abs(strikes[i] - spot);
      if (d < bestDiff) { best = strikes[i]; bestDiff = d; }
    }
    return best;
  };

  function renderChain(data, showAll, win, stepGuess) {
    lastChainData = data; // save for AI

    const spot    = Number(field(data, "spot", NaN));
    const summary = field(data, "summary", {});
    const rows    = field(data, "chain", []);

    const strikes = rows.map(r => Number(r.strike)).filter(x => !Number.isNaN(x));
    const atm     = computeATM(strikes, spot);
    const step    = Number(stepGuess || 50);

    let view = rows;
    if (!showAll && atm != null && Number.isFinite(step)) {
      const lo = atm - win * step, hi = atm + win * step;
      view = rows.filter(r => r.strike >= lo && r.strike <= hi);
    }

    showBadges({ spot, pcr: summary.pcr, maxPain: summary.max_pain, rows: rows.length });

    if (!Array.isArray(view) || view.length === 0) {
      els.tbody.innerHTML = `<tr><td colspan="9">No rows to display.</td></tr>`;
      return;
    }

    els.tbody.innerHTML = view.map(r => {
      const ce = r.call || {}, pe = r.put || {};
      return `<tr>
        <td>${fmt2(ce.price)}</td>
        <td>${fmt2(ce.iv)}</td>
        <td>${fmtNum(ce.oi)}</td>
        <td>${fmtNum(ce.chgOi)}</td>
        <td>${fmtNum(r.strike)}</td>
        <td>${fmtNum(pe.chgOi)}</td>
        <td>${fmtNum(pe.oi)}</td>
        <td>${fmt2(pe.iv)}</td>
        <td>${fmt2(pe.price)}</td>
      </tr>`;
    }).join("");
  }

  async function fetchAndRenderChain() {
    const instOpt = els.instrument.selectedOptions[0];
    const expOpt  = els.expiry.selectedOptions[0];

    if (!instOpt || !expOpt) {
      els.tbody.innerHTML = `<tr><td colspan="9">Select instrument and expiry, then click Refresh</td></tr>`;
      return;
    }

    const id    = Number(instOpt.value);
    const seg   = instOpt.dataset.seg;
    const step  = Number(instOpt.dataset.step || ID_STEPS[id] || DEFAULT_STEPS[seg] || 50);
    const expiry = expOpt.value;

    const url = `/optionchain?under_security_id=${id}&under_exchange_segment=${seg}&expiry=${expiry}&show_all=${els.showFull.checked}`;
    els.tbody.innerHTML = `<tr><td colspan="9">Loading chain...</td></tr>`;
    try {
      const j = await fetchJSON(url);
      if (j.status && j.status !== "success") {
        throw new Error(j.detail || "backend status != success");
      }
      const win = Number(els.window.value || 15);
      renderChain(j, els.showFull.checked, isFinite(win) ? win : 15, step);
    } catch (e) {
      console.error("Chain load failed:", e);
      showChainError(e.message);
    }
  }

  // ---------- Vishnu AI ----------
  async function runAIAnalysis() {
    els.aiOutput.textContent = "Analyzing with Vishnu…";

    const instOpt = els.instrument.selectedOptions[0];
    const expOpt  = els.expiry.selectedOptions[0];
    if (!instOpt || !expOpt) {
      els.aiOutput.textContent = "Select instrument & expiry first.";
      return;
    }
    const id     = Number(instOpt.value);
    const seg    = instOpt.dataset.seg;
    const expiry = expOpt.value;

    // Prefer sending the chain we already have; backend may also fetch if missing
    const payload = {
      under_security_id: id,
      under_exchange_segment: seg,
      expiry,
      prompt: (els.aiPrompt.value || "").trim(),
      // Optional: pass the chain so AI has exactly what user sees
      option_chain: lastChainData || null
    };

    try {
      const res = await fetch("/ai/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const t = await res.text().catch(()=> "");
        throw new Error(`${res.status} ${res.statusText}: ${t || "AI request failed"}`);
      }
      const j = await res.json();
      // Expect j = { status:"success", data:{ text: "...", bullets?: [...] } } OR {text:"..."}
      const data = j.data || j;
      const text = data.text || "No analysis text.";
      const bullets = Array.isArray(data.bullets) ? data.bullets : [];
      const extra = data.metrics ? `\n\nMetrics: ${JSON.stringify(data.metrics)}` : "";

      const bulTxt = bullets.length ? ("\n\n• " + bullets.join("\n• ")) : "";
      els.aiOutput.textContent = text + bulTxt + extra;
    } catch (e) {
      console.error("AI analyze failed:", e);
      els.aiOutput.textContent = `AI error: ${e.message}`;
    }
  }

  // ---------- Events ----------
  els.instrument.addEventListener("change", async () => {
    await loadExpiriesForSelected();
    await sleep(50);
  });
  els.refresh.addEventListener("click", fetchAndRenderChain);
  els.showFull.addEventListener("change", fetchAndRenderChain);
  if (els.aiAnalyze) els.aiAnalyze.addEventListener("click", runAIAnalysis);

  // ---------- Init ----------
  (async function init() {
    try {
      await loadInstruments();
      await loadExpiriesForSelected();
    } catch (e) {
      console.error(e);
    }
  })();
})();
