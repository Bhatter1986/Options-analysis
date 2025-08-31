/* Dashboard JS */
const selInstrument=document.getElementById('instrument');
const selExpiry=document.getElementById('expiry');
const inpWindow=document.getElementById('window');
const chkFull=document.getElementById('fullChain');
const btnRefresh=document.getElementById('refreshBtn');
const spotMeta=document.getElementById('spotMeta');
const bodyChain=document.querySelector('#chainTable tbody');
const pcrEl=document.getElementById('pcr');
const maxPainEl=document.getElementById('maxPain');
const healthText=document.getElementById('healthText');
const aiBtn=document.getElementById('aiBtn');
const aiPrompt=document.getElementById('aiPrompt');
const aiOut=document.getElementById('aiOut');

const API=(path)=>`${location.origin}${path}`;
let current={instrument:13,segment:'IDX_I',step:50};

async function getJSON(url){const r=await fetch(url);if(!r.ok)throw new Error(r.status);return r.json();}
function opt(v,t=v){const o=document.createElement('option');o.value=v;o.textContent=t;return o;}

async function loadInstruments(){
  const data=await getJSON(API('/instruments'));
  selInstrument.innerHTML='';
  for(const x of data.data) selInstrument.appendChild(opt(JSON.stringify({id:x.id,seg:x.segment,step:x.step}),x.name));
  const idx=Array.from(selInstrument.options).findIndex(o=>o.text.includes('NIFTY'));
  selInstrument.selectedIndex=idx>=0?idx:0;
  applyInstrument();
}
function applyInstrument(){const v=JSON.parse(selInstrument.value);current.instrument=v.id;current.segment=v.seg;current.step=v.step||50;loadExpiries();}
async function loadExpiries(){
  selExpiry.innerHTML='';
  const q=new URLSearchParams({under_security_id:current.instrument,under_exchange_segment:current.segment});
  const data=await getJSON(API(`/optionchain/expirylist?${q}`));
  for(const ex of data.data) selExpiry.appendChild(opt(ex));
  if(selExpiry.options.length)selExpiry.selectedIndex=0;
  renderChain();
}

function rowHTML(r){
  const ce=r.call,pe=r.put;
  return `<tr>
    <td>${ce.price?.toFixed?.(2)??'-'}</td>
    <td>${ce.iv?.toFixed?.(2)??'-'}</td>
    <td>${ce.oi}</td>
    <td>${ce.chgOi}</td>
    <td>${ce.delta?.toFixed?.(2)??'-'}</td>
    <td>${r.strike}</td>
    <td>${pe.delta?.toFixed?.(2)??'-'}</td>
    <td>${pe.chgOi}</td>
    <td>${pe.oi}</td>
    <td>${pe.iv?.toFixed?.(2)??'-'}</td>
    <td>${pe.price?.toFixed?.(2)??'-'}</td>
  </tr>`;
}

async function renderChain(){
  bodyChain.innerHTML=`<tr><td colspan="11">Loading…</td></tr>`;
  pcrEl.textContent='—';maxPainEl.textContent='—';aiOut.textContent='';
  const params=new URLSearchParams({
    under_security_id:String(current.instrument),
    under_exchange_segment:current.segment,
    expiry:selExpiry.value,
    show_all:chkFull.checked?'true':'false',
    strikes_window:String(inpWindow.value||15),
    step:String(current.step)
  });
  try{
    const data=await getJSON(API(`/optionchain?${params}`));
    spotMeta.textContent=`Spot: ${data.spot?.toFixed?.(2)??'—'} | Step: ${current.step}`;
    pcrEl.textContent=data.summary?.pcr??'—';
    maxPainEl.textContent=data.summary?.max_pain??'—';
    const rows=(data.chain||[]).map(rowHTML).join('');
    bodyChain.innerHTML=rows||`<tr><td colspan="11">No rows.</td></tr>`;
    healthText.textContent=`Health: OK • ${data.meta?.count_window} rows (full: ${data.meta?.count_full})`;
  }catch(e){
    bodyChain.innerHTML=`<tr><td colspan="11">Error: ${e.message}</td></tr>`;
    healthText.textContent=`Health: ERROR • ${e.message}`;
  }
}

async function runAI(){
  aiOut.textContent='Thinking…';aiBtn.disabled=true;
  try{
    const prompt=aiPrompt.value?.trim()||'Summarize the option chain with support/resistance + Greeks.';
    const r=await fetch(API('/ai/analyze'),{
      method:'POST',headers:{'content-type':'application/json'},
      body:JSON.stringify({prompt})
    });
    const j=await r.json();
    if(!r.ok)throw new Error(j.detail||'AI error');
    aiOut.textContent=j.answer||JSON.stringify(j);
  }catch(e){aiOut.textContent=`AI error: ${e.message}`;}
  finally{aiBtn.disabled=false;}
}

/* events */
selInstrument.addEventListener('change',applyInstrument);
selExpiry.addEventListener('change',renderChain);
inpWindow.addEventListener('change',renderChain);
chkFull.addEventListener('change',renderChain);
btnRefresh.addEventListener('click',renderChain);
aiBtn.addEventListener('click',runAI);

/* init */
loadInstruments();
