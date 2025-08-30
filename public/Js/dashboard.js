async function loadInstruments() {
  const instrumentSelect = document.getElementById("instrument");
  instrumentSelect.innerHTML = `<option>Loading...</option>`;

  try {
    // Get indices
    const idxRes = await fetch("/instruments/indices");
    const idxJson = await idxRes.json();

    // Get stocks example (Reliance, HDFC etc.) via search API
    const stockRes = await fetch("/instruments/search?q=");
    const stockJson = await stockRes.json();

    instrumentSelect.innerHTML = "";

    // Add indices
    idxJson.data.forEach(inst => {
      let opt = document.createElement("option");
      opt.value = JSON.stringify({ id: inst.id, segment: inst.segment });
      opt.textContent = inst.name + " (Index)";
      instrumentSelect.appendChild(opt);
    });

    // Add stocks
    stockJson.data.forEach(inst => {
      let opt = document.createElement("option");
      opt.value = JSON.stringify({ id: inst.id, segment: inst.segment });
      opt.textContent = inst.name + " (Stock)";
      instrumentSelect.appendChild(opt);
    });

  } catch (err) {
    console.error("Failed to load instruments:", err);
    instrumentSelect.innerHTML = `<option>Error loading instruments</option>`;
  }
}

async function loadExpiries() {
  const expirySelect = document.getElementById("expiry");
  expirySelect.innerHTML = `<option>Loading...</option>`;

  try {
    const res = await fetch("/optionchain/auto/expirylist");
    const json = await res.json();
    expirySelect.innerHTML = "";

    json.data.forEach(date => {
      let opt = document.createElement("option");
      opt.value = date;
      opt.textContent = date;
      expirySelect.appendChild(opt);
    });

  } catch (err) {
    console.error("Failed to load expiries:", err);
    expirySelect.innerHTML = `<option>Error loading expiries</option>`;
  }
}

async function loadChain() {
  const instrument = JSON.parse(document.getElementById("instrument").value);
  const expiry = document.getElementById("expiry").value;
  const tableBody = document.getElementById("chain-body");

  tableBody.innerHTML = `<tr><td colspan="9">Loading...</td></tr>`;

  try {
    const res = await fetch("/optionchain/auto/fetch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        UnderlyingScrip: instrument.id,
        UnderlyingSeg: instrument.segment,
        Expiry: expiry
      })
    });

    const json = await res.json();
    tableBody.innerHTML = "";

    if (!json.data || !json.data.chain) {
      tableBody.innerHTML = `<tr><td colspan="9">No chain data</td></tr>`;
      return;
    }

    json.data.chain.forEach(row => {
      let tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${row.call?.price ?? "-"}</td>
        <td>${row.call?.iv?.toFixed(2) ?? "-"}</td>
        <td>${row.call?.oi ?? "-"}</td>
        <td>${row.call?.chgOi ?? "-"}</td>
        <td>${row.strike}</td>
        <td>${row.put?.chgOi ?? "-"}</td>
        <td>${row.put?.oi ?? "-"}</td>
        <td>${row.put?.iv?.toFixed(2) ?? "-"}</td>
        <td>${row.put?.price ?? "-"}</td>
      `;
      tableBody.appendChild(tr);
    });

  } catch (err) {
    console.error("Failed to load chain:", err);
    tableBody.innerHTML = `<tr><td colspan="9">Error loading chain</td></tr>`;
  }
}

// On page load
document.addEventListener("DOMContentLoaded", () => {
  loadInstruments().then(loadExpiries);

  document.getElementById("refresh").addEventListener("click", loadChain);
});
