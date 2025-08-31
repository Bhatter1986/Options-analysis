/* public/Js/dashboard.js */
const api = (path) => `${path.startsWith('http') ? path : path}`;

const $ = (id) => document.getElementById(id);
const ddInstrument = $("instrument");
const ddExpiry = $("expiry");
const inpWindow = $("window");
const cbFull = $("fullchain");
const spotInfo = $("spotInfo");
const tbody = $("tbody");
const pcrSpan = $("pcr");
const aiBtn = $("analyze");
const aiOut = $("airesult");
const modeBadge = $("modeBadge");

async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function fmt(n, d = 2) {
  if (n === null || n === undefined) return "—";
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: d });
}

function rowHtml(row) {
  const ce = row.call || {};
  const pe = row.put || {};
  return `<tr>
    <td>${fmt(ce.price)}</td>
    <td>${fmt(ce.iv)}</td>
    <td>${fmt(ce.oi, 0)}</td>
    <td class="${(ce.chgOi||0) >= 0 ? 'up' : 'dn'}">${fmt(ce.chgOi, 0)}</td>
    <td><span class="pill">${fmt(row.strike, 0)}</span></td>
    <td class="${(pe.chgOi||0) >= 0 ? 'up' : 'dn'}">${fmt(pe.chgOi, 0)}</td>
    <td>${fmt(pe.oi, 0)}</td>
    <td>${fmt(pe.iv)}</td>
    <td>${fmt(pe.price)}</td>
  </tr>`;
}

async function loadSelfTest() {
  try {
    const j = await getJSON(api("/__selftest"));
    modeBadge.textContent = `${j.status.mode} • AI:${j.status.ai_present ? 'on' : 'off'}`;
  } catch {}
}

async function loadInstruments() {
  ddInstrument.innerHTML = `<option value="">Loading…</option>`;
  const j = await getJSON(api("/instruments"));
  const items = (j.data || []).slice();
  ddInstrument.innerHTML = items.map(x => `<option value="${x.id}|${x.segment}|${x.step}">${x.name}</option>`).join("");
  // default select first
  if (items.length) ddInstrument.value = `${items[0].id}|${items[0].segment}|${items[0].step}`;
}

async function loadExpiries() {
  const v = ddInstrument.value;
  if (!v) return;
  const [id, seg] = v.split("|");
  ddExpiry.innerHTML = `<option>Loading…</option>`;
  const j = await getJSON(api(`/optionchain/expirylist?under_security_id=${id}&under_exchange_segment=${seg}`));
  const exps = j.data || [];
  ddExpiry.innerHTML = exps.map(x => `<option value="${x}">${x}</option>`).join("");
}

async function loadChain() {
  tbody.innerHTML = `<tr><td class="muted" colspan="9">Loading…</td></tr>`;
  aiOut.textContent = "";
  const v = ddInstrument.value;
  if (!v || !ddExpiry.value) return;
  const [id, seg, step] = v.split("|");
  const win = Number(inpWindow.value || 15);
  const full = cbFull.checked ? "1" : "0";
  const url = api(`/optionchain?under_security_id=${id}&under_exchange_segment=${seg}&expiry=${encodeURIComponent(ddExpiry.value)}&window=${win}&show_full=${full}`);
  const j = await getJSON(url);
  // Header info
  const spot = j.spot ?? null;
  spotInfo.textContent = spot ? `Spot: ${fmt(spot, 2)} | Step: ${step}` : "—";
  pcrSpan.textContent = `PCR: ${j.summary?.pcr ?? "—"}`;

  const rows = j.data || j.rows || [];
  if (!rows.length) {
    tbody.innerHTML = `<tr><td class="muted" colspan="9">No rows.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(rowHtml).join("");
  return { meta: { id, seg, expiry: ddExpiry.value, spot, step }, rows, summary: j.summary || {} };
}

async function aiAnalyze() {
  const snapshot = await loadChain(); // ensure latest data
  if (!snapshot) return;
  const promptUser = ($("prompt").value || "").trim();
  const basePrompt = `You are an options analyst. Using the Indian market option chain snapshot (BANKNIFTY/NIFTY style), identify key support/resistance strikes from OI and ΔOI, notable IV skews, and give 2-3 trade ideas with entry, stop, and reasoning. Keep it crisp.`;
  const payload = {
    prompt: (promptUser ? (promptUser + "\n\n") : "") + basePrompt,
    // You can extend to send raw data later:
    // data: snapshot
  };
  aiOut.textContent = "Thinking…";
  try {
    const j = await getJSON(api("/ai/analyze"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload)
    });
    aiOut.textContent = j.answer || JSON.stringify(j, null, 2);
  } catch (e) {
    aiOut.textContent = `AI error: ${e.message}`;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await loadSelfTest();
  await loadInstruments();
  await loadExpiries();
  await loadChain();

  ddInstrument.addEventListener("change", async () => {
    await loadExpiries();
    await loadChain();
  });
  ddExpiry.addEventListener("change", loadChain);
  $("refresh").addEventListener("click", loadChain);
  aiBtn.addEventListener("click", aiAnalyze);
});
