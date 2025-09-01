// ====== Config (auto-detect API base) ======
const origin = (window.location.origin || "").replace(/\/$/, "");
// If running on the Render domain, use same origin; otherwise hit deployed API directly.
const apiBase = origin.includes("options-analysis.onrender.com")
  ? origin
  : "https://options-analysis.onrender.com";

// ====== Elements ======
const selInstrument = document.getElementById("instrument");
const selExpiry     = document.getElementById("expiry");
const inpWindow     = document.getElementById("window");
const chkFull       = document.getElementById("fullChain");
const btnRefresh    = document.getElementById("refreshBtn");
const bodyChain     = document.getElementById("chainBody");
const metaLine      = document.getElementById("metaLine");
const healthText    = document.getElementById("healthText");
const pcrEl         = document.getElementById("pcr");
const pcrRightEl    = document.getElementById("pcrRight");
const btnLoadMore   = document.getElementById("loadMoreBtn");
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
  strikes_window: 5 // default = ATM ±5 (≈11 rows)
};

// ====== Utils ======
const fmt = (n, d = 2) => (n === null || n === undefined || Number.isNaN(n)) ? "—" : Number(n).toFixed(d);
const int = (n) => (n === null || n === undefined || Number.isNaN(n)) ? "—" : Number(n).toLocaleString("en-IN");

function setHealth(msg, ok = true) {
  healthText.textContent = ok ? msg : `⚠︎ ${msg}`;
}

async function fetchJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

// Keep exactly ATM-centered window (2*win+1 rows)
function centeredWindow(chain, spot, step, win) {
  if (!Array.isArray(chain) || chain.length === 0 || !spot || !step) return chain;
  const strikes = chain.map(r => r.strike);
  let atm = strikes[0];
  for (const s of strikes) if (Math.abs(s - spot) < Math.abs(atm - spot)) atm = s;
  const lo = atm - win * step;
  const hi = atm + win * step;
  return chain.filter(r => r.strike >= lo && r.strike <= hi);
}

// ====== Loaders ======
async function loadInstruments() {
  setHealth("Loading instruments…");
  const data = await fetchJSON(`${apiBase}/instruments`);
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
  const id = Number(selInstrument.value);
  const seg  = selInstrument.selectedOptions[0]?.dataset.seg || "";
  const step = Number(selInstrument.selectedOptions[0]?.dataset.step || 0);

  current.under_security_id = id || null;
  current.under_exchange_segment = seg || null;
  current.step = step || 100;

  if (!id || !seg) {
    selExpiry.innerHTML = `<option value="">—</option>`;
    return;
  }

  const data = await fetchJSON(
    `${apiBase}/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${encodeURIComponent(seg)}`
  );
  const expiries = data?.data || [];
  selExpiry.innerHTML = expiries.map(e => `<option value="${e}">${e}</option>`).join("");
  current.expiry = selExpiry.value || null;
}

async function loadChain() {
  if (!current.under_security_id || !current.expiry) {
    bodyChain.innerHTML = `<tr><td colspan="16" class="muted">Select instrument & expiry, then click Refresh</td></tr>`;
    return;
  }

  setHealth("Loading chain…");

  const qs = new URLSearchParams({
    under_security_id: String(current.under_security_id),
    under_exchange_segment: current.under_exchange_segment,
    expiry: current.expiry,
    strikes_window: String(current.strikes_window),
    step: String(current.step || 100),
    show_all: chkFull.checked ? "true" : "false"
  });

  const data = await fetchJSON(`${apiBase}/optionchain?${qs.toString()}`);

  const spot = data?.spot ?? null;
  const step = current.step || 100;
  const pcr  = data?.summary?.pcr ?? null;

  // If “Show full chain” not checked, strictly keep ATM ± window (constant rows)
  const rows = chkFull.checked
    ? (data?.chain || [])
    : centeredWindow((data?.chain || []), spot, step, current.strikes_window);

  // top meta
  pcrEl.textContent = fmt(pcr, 2);
  pcrRightEl.textContent = fmt(pcr, 2);
  metaLine.textContent = `Spot: ${fmt(spot, 2)} | Step: ${step} | PCR: ${fmt(pcr, 2)}`;

  // render rows
  if (!rows.length) {
    bodyChain.innerHTML = `<tr><td colspan="16" class="muted">No rows.</td></tr>`;
  } else {
    bodyChain.innerHTML = rows.map(r => `
      <tr>
        <td>${fmt(r.call.price)}</td>
        <td>${fmt(r.call.iv)}</td>
        <td>${fmt(r.call.delta, 4)}</td>
        <td>${fmt(r.call.gamma, 6)}</td>
        <td>${fmt(r.call.theta, 2)}</td>
        <td>${fmt(r.call.vega, 2)}</td>

        <td>${int(r.call.oi)}</td>
        <td>${int(r.call.chgOi)}</td>

        <td><strong>${int(r.strike)}</strong></td>

        <td>${int(r.put.chgOi)}</td>
        <td>${int(r.put.oi)}</td>

        <td>${fmt(r.put.vega, 2)}</td>
        <td>${fmt(r.put.gamma, 6)}</td>
        <td>${fmt(r.put.delta, 4)}</td>
        <td>${fmt(r.put.iv)}</td>
        <td>${fmt(r.put.price)}</td>
      </tr>
    `).join("");
  }

  setHealth(`Loaded ${rows.length} rows (window ±${current.strikes_window}).`);
}

// ====== AI (optional) ======
async function analyzeAI() {
  try {
    aiOut.textContent = "Thinking…";
    const payload = {
      prompt: aiPrompt.value?.trim() || "Give a brief summary of OI distribution and notable strikes.",
    };
    const r = await fetch(`${apiBase}/ai/analyze`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload)
    });
    const j = await r.json();
    if (j?.status === "success") {
      aiOut.textContent = j.answer || "(no answer)";
    } else {
      aiOut.textContent = j?.detail || "AI error.";
    }
  } catch (e) {
    aiOut.textContent = String(e.message || e);
  }
}

// ====== Events ======
selInstrument.addEventListener("change", async () => {
  try {
    await loadExpiries();
  } catch (e) {
    setHealth(e.message, false);
  }
});

selExpiry.addEventListener("change", () => {
  current.expiry = selExpiry.value || null;
});

inpWindow.addEventListener("change", () => {
  const v = Math.max(1, Math.min(50, Number(inpWindow.value) || 5));
  current.strikes_window = v;
});

chkFull.addEventListener("change", () => {
  /* re-render on next refresh */
});

btnRefresh.addEventListener("click", async () => {
  try {
    await loadChain();
  } catch (e) {
    setHealth(e.message, false);
  }
});

btnLoadMore.addEventListener("click", async () => {
  current.strikes_window += 5;
  inpWindow.value = String(current.strikes_window);
  try {
    await loadChain();
  } catch (e) {
    setHealth(e.message, false);
  }
});

aiBtn?.addEventListener("click", analyzeAI);

// ====== Init ======
(async function init() {
  try {
    await loadInstruments();
    // Auto-select first instrument to speed up first use (optional)
    if (selInstrument.options.length > 1) {
      selInstrument.selectedIndex = 1;
      await loadExpiries();
    }
    setHealth("Ready.");
  } catch (e) {
    setHealth(e.message, false);
  }
})();
