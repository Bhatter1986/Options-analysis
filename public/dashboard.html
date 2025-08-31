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
  };

  // Create / reuse a small badge strip above the table for summary
  let badgeStrip = document.getElementById("oa-badges");
  if (!badgeStrip) {
    badgeStrip = document.createElement("div");
    badgeStrip.id = "oa-badges";
    badgeStrip.className = "d-flex gap-2 flex-wrap mb-2";
    els.table.parentElement.insertBefore(badgeStrip, els.table);
  }

  // ---------- Utilities ----------
  const DEFAULT_STEPS = {
    // sensible defaults per segment
    IDX_I: 50,    // NIFTY style
    NSE_I: 50,
    IDX_FO: 50,
    NSE_E: 10,    // equities common
    BSE_E: 10,
  };
  // known specific IDs (from your watchlist examples)
  const ID_STEPS = {
    13: 50,  // NIFTY 50 (ID)
    25: 100, // BANKNIFTY (ID)
  };

  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  function setSelectLoading(select, msg = "Loading...") {
    select.innerHTML = `<option>${msg}</option>`;
  }
  function setSelectError(select, msg = "Error") {
    select.innerHTML = `<option>${msg}</option>`;
  }
  function clearSelect(select) {
    select.innerHTML = "";
  }
  function addOption(select, value, label, extra = {}) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    Object.entries(extra).forEach(([k, v]) => opt.dataset[k] = v);
    select.appendChild(opt);
  }
  function fmtNum(n) {
    if (n === null || n === undefined || Number.isNaN(n)) return "—";
    const abs = Math.abs(n);
    if (abs >= 1e7) return (n / 1e7).toFixed(2) + " Cr";
    if (abs >= 1e5) return (n / 1e5).toFixed(2) + " L";
    if (abs >= 1e3) return (n / 1e3).toFixed(2) + " K";
    return typeof n === "number" ? n.toLocaleString("en-IN") : String(n);
  }
  function fmt2(n) {
    return (n === null || n === undefined || Number.isNaN(n)) ? "—" : Number(n).toFixed(2);
  }
  function field(obj, path, d = null) {
    try {
      return path.split(".").reduce((o, k) => (o && k in o ? o[k] : undefined), obj) ?? d;
    } catch {
      return d;
    }
  }
  function badge(title, value) {
    const span = document.createElement("span");
    span.className = "badge rounded-pill text-bg-secondary";
    span.style.fontSize = "0.9rem";
    span.textContent = `${title}: ${value}`;
    return span;
  }
  function showBadges({ spot, pcr, maxPain, rows }) {
    badgeStrip.innerHTML = "";
    badgeStrip.appendChild(badge("LTP", fmt2(spot)));
    badgeStrip.appendChild(badge("PCR", fmt2(pcr)));
    badgeStrip.appendChild(badge("Max Pain", fmtNum(maxPain)));
    badgeStrip.appendChild(badge("rows", fmtNum(rows)));
  }
  function showChainError(msg) {
    els.tbody.innerHTML = `<tr><td colspan="9">Error loading chain: ${msg}</td></tr>`;
  }

  // ---------- Data loads ----------
  async function fetchJSON(url, opts = {}) {
    const res = await fetch(url, opts);
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}: ${text || "request failed"}`);
    }
    return res.json();
  }

  // Try watchlist.json first; else fallback to backend /instruments
  async function loadInstruments() {
    setSelectLoading(els.instrument, "Loading instruments...");
    const list = [];

    // 1) watchlist file
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
    } catch {
      // ignore; we'll try backend
    }

    // 2) fallback to backend if nothing
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

    // Populate select
    clearSelect(els.instrument);
    for (const it of list) {
      addOption(els.instrument, it.id, it.name, { seg: it.segment, step: it.step });
    }

    return list;
  }

  async function loadExpiriesForSelected() {
    setSelectLoading(els.expiry, "Loading expiries...");
    const opt = els.instrument.selectedOptions[0];
    if (!opt) {
      setSelectError(els.expiry, "Select instrument first");
      return [];
    }
    const id = Number(opt.value);
    const seg = opt.dataset.seg;

    // Use GET with query params (your backend supports this)
    const qs = new URLSearchParams({
      under_security_id: String(id),
      under_exchange_segment: String(seg),
    });
    const url = `/optionchain/expirylist?${qs.toString()}`;

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

  // ---------- Chain render ----------
  function computeATM(strikes, spot) {
    if (!Array.isArray(strikes) || strikes.length === 0 || typeof spot !== "number") return null;
    let best = strikes[0], bestDiff = Math.abs(strikes[0] - spot);
    for (let i = 1; i < strikes.length; i++) {
      const d = Math.abs(strikes[i] - spot);
      if (d < bestDiff) { best = strikes[i]; bestDiff = d; }
    }
    return best;
  }

  function renderChain(data, showAll, win, stepGuess) {
    const spot = Number(field(data, "spot", NaN));
    const summary = field(data, "summary", {});
    const rows = field(data, "chain", []);

    const strikes = rows.map(r => Number(r.strike)).filter(x => !Number.isNaN(x));
    const atm = computeATM(strikes, spot);
    const step = Number(stepGuess || 50);

    // filter/windowing
    let view = rows;
    if (!showAll && atm != null && Number.isFinite(step)) {
      const lo = atm - win * step;
      const hi = atm + win * step;
      view = rows.filter(r => r.strike >= lo && r.strike <= hi);
    }

    // badges
    showBadges({
      spot,
      pcr: summary.pcr,
      maxPain: summary.max_pain,
      rows: rows.length,
    });

    // table
    if (!Array.isArray(view) || view.length === 0) {
      els.tbody.innerHTML = `<tr><td colspan="9">No rows to display.</td></tr>`;
      return;
    }

    const trHtml = view.map(r => {
      const ce = r.call || {};
      const pe = r.put || {};
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

    els.tbody.innerHTML = trHtml;
  }

  async function fetchAndRenderChain() {
    const instOpt = els.instrument.selectedOptions[0];
    const expOpt = els.expiry.selectedOptions[0];

    if (!instOpt || !expOpt) {
      els.tbody.innerHTML = `<tr><td colspan="9">Select instrument and expiry, then click Refresh</td></tr>`;
      return;
    }

    const id = Number(instOpt.value);
    const seg = instOpt.dataset.seg;
    const step = Number(instOpt.dataset.step || ID_STEPS[id] || DEFAULT_STEPS[seg] || 50);
    const expiry = expOpt.value;

    const qs = new URLSearchParams({
      under_security_id: String(id),
      under_exchange_segment: String(seg),
      expiry: String(expiry),
      show_all: String(els.showFull.checked),
    });
    const url = `/optionchain?${qs.toString()}`;

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

  // ---------- Events ----------
  els.instrument.addEventListener("change", async () => {
    await loadExpiriesForSelected();
    // Small debounce for nicer UX on mobile
    await sleep(50);
  });
  els.refresh.addEventListener("click", fetchAndRenderChain);
  els.showFull.addEventListener("change", fetchAndRenderChain);

  // ---------- Bootstrap ----------
  (async function init() {
    try {
      await loadInstruments();
      await loadExpiriesForSelected();
    } catch (e) {
      console.error(e);
      // fall through; selects already show an error state
    }
  })();
})();
