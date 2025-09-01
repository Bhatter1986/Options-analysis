// ====== Config ======
const origin = (window.location.origin || "").replace(/\/$/, "");
// If running on Render domain, use same origin; otherwise hit deployed API directly.
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
let instruments = [];
let current = {
  under_security_id: null,
  under_exchange_segment: null,
  expiry: null,
  step: null,
  strikes_window: 5, // default ATM ±5 (total 11 rows)
};

// ====== Helpers ======
const fmt = (n, d = 2) =>
  (n === null || n === undefined || Number.isNaN(Number(n))) ? "—" : Number(n).toFixed(d);

const int = (n) =>
  (n === null || n === undefined || Number.isNaN(Number(n))) ? "—" : Number(n).toLocaleString("en-IN");

function setHealth(msg, ok = true) { healthText.textContent = ok ? msg : `⚠︎ ${msg}`; }

async function fetchJSON(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// Center to ATM within ±window*step
function centeredWindow(chain, spot, step, win) {
  if (!Array.isArray(chain) || !chain.length || !spot || !step) return chain || [];
  const strikes = chain.map((r) => r.strike);
  const atm = strikes.reduce((a, b) => (Math.abs(b - spot) < Math.abs(a - spot) ? b : a), strikes[0]);
  const lo = atm - win * step;
  const hi = atm + win * step;
  return chain.filter((r) => r.strike >= lo && r.strike <= hi);
}

// ====== Loaders ======
async function loadInstruments() {
  setHealth("Loading instruments…");
  const data = await fetchJSON(`${apiBase}/instruments`);
  instruments = data?.data ?? [];
  selInstrument.innerHTML =
    `<option value="">Select…</option>` +
    instruments
      .map((i) => `<option value="${i.id}" data-seg="${i.segment}" data-step="${i.step}">${i.name}</option>`)
      .join("");
  setHealth("Instruments ready.");
}

async function loadExpiries() {
  selExpiry.innerHTML = `<option>Loading…</option>`;
  const id = Number(selInstrument.value);
  const seg = selInstrument.selectedOptions[0]?.dataset.seg || "";
  const step = Number(selInstrument.selectedOptions[0]?.dataset.step || 0);
  current.under_security_id = id;
  current.under_exchange_segment = seg;
  current.step = step || 100;

  if (!id || !seg) {
    selExpiry.innerHTML = `<option value="">Select…</option>`;
    return;
  }

  const data = await fetchJSON(
    `${apiBase}/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${encodeURIComponent(seg)}`
  );
  const expiries = data?.data ?? [];
  selExpiry.innerHTML = expiries.map((e) => `<option value="${e}">${e}</option>`).join("");
  current.expiry = selExpiry.value || null;
}

async function loadChain() {
  if (!current.under_security_id || !current.expiry) {
    setHealth("Select instrument & expiry, then click Refresh", false);
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

  const data = await fetchJSON(`${apiBase}/optionchain?${qs.toString()}`);
  const spot = data?.spot ?? null;
  const step = current.step || 100;
  const pcr = data?.summary?.pcr ?? null;

  // rows selection
  let rows = Array.isArray(data?.chain) ? data.chain : [];
  if (!chkFull.checked) rows = centeredWindow(rows, spot, step, current.strikes_window);

  // meta
  pcrEl.textContent = fmt(pcr, 2);
  pcrRightEl.textContent = fmt(pcr, 2);
  metaLine.textContent = `Spot: ${fmt(spot, 2)} | Step: ${step} | PCR: ${fmt(pcr, 2)}`;

  // render
  bodyChain.innerHTML = rows
    .map(
      (r) => `
    <tr>
      <td>${fmt(r.call?.price)}</td>
      <td>${fmt(r.call?.iv)}</td>
      <td>${fmt(r.call?.delta, 4)}</td>
      <td>${fmt(r.call?.gamma, 6)}</td>
      <td>${fmt(r.call?.theta, 2)}</td>
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
    </tr>`
    )
    .join("");

  setHealth(`Loaded ${rows.length} rows${chkFull.checked ? " (full chain)" : ` (window ±${current.strikes_window})`}.`);
}

// ====== Events ======
selInstrument.addEventListener("change", async () => {
  try {
    await loadExpiries();
    bodyChain.innerHTML = ""; // clear table until refresh
    metaLine.textContent = "Spot: — | Step: — | PCR: —";
    setHealth("Select expiry, then click Refresh.");
  } catch (e) {
    setHealth(e.message || String(e), false);
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
  // just affects next refresh render
});

btnRefresh.addEventListener("click", async () => {
  try { await loadChain(); } catch (e) { setHealth(e.message || String(e), false); }
});

btnLoadMore.addEventListener("click", async () => {
  current.strikes_window += 5;
  inpWindow.value = String(current.strikes_window);
  try { await loadChain(); } catch (e) { setHealth(e.message || String(e), false); }
});

// (Optional) AI analyze current table with your /ai/analyze endpoint
aiBtn?.addEventListener("click", async () => {
  try {
    aiBtn.disabled = true;
    aiOut.textContent = "Analyzing…";
    const prompt = aiPrompt.value?.trim() || "Give a concise OI-based view and one idea with strike & SL.";
    // Compose a tiny summary from currently visible rows
    const rows = Array.from(bodyChain.querySelectorAll("tr")).slice(0, 30).map(tr =>
      Array.from(tr.children).map(td => td.textContent.trim())
    );
    const textTable = rows.map(r => r.join(" | ")).join("\n");
    const payload = { prompt: `${prompt}\n\nData (first rows):\n${textTable}` };

    const r = await fetch(`${apiBase}/ai/analyze`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    const j = await r.json();
    aiOut.textContent = j?.answer || JSON.stringify(j);
  } catch (e) {
    aiOut.textContent = `AI error: ${e.message || e}`;
  } finally {
    aiBtn.disabled = false;
  }
});

// ====== Init ======
(async function init() {
  try {
    await loadInstruments();
    // auto-select first if available to reduce clicks
    if (selInstrument.options.length > 1) {
      selInstrument.selectedIndex = 1;
      await loadExpiries();
    }
    setHealth("Ready.");
  } catch (e) {
    setHealth(e.message || String(e), false);
  }
})();
