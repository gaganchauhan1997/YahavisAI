/* YAHAVIS HUD — app.js
   Auto-detects backend: Cloud Worker → localhost → direct Groq
*/

const IS_DEV    = location.hostname === '127.0.0.1' || location.hostname === 'localhost';
const API_URL   = IS_DEV ? 'http://127.0.0.1:7070' : '';
const WS_URL    = IS_DEV
  ? 'ws://127.0.0.1:7071'
  : (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';

// Direct Groq config (used when no backend available — static mode)
const GROQ_URL  = 'https://api.groq.com/openai/v1/chat/completions';
const GROQ_KEY  = '';   // Set via localStorage: localStorage.setItem('groq_key','gsk_...')
const GROQ_MODEL = 'llama3-8b-8192';

const SYSTEM_PROMPT = `You are YAHAVIS — Yahavi AI System. You are Myth's personal AI assistant.
Personality: Calm, precise, slightly witty. Address user as 'Boss' occasionally.
You understand Hindi-English mix commands. Hackknow is the operator's company.
Always confirm task completion with a brief status.`;

const BOOT_MSGS = [
  'Initializing neural core...',
  'Loading API rotation engine...',
  'Calibrating voice interface...',
  'Connecting to memory systems...',
  'Starting task orchestrator...',
  'YAHAVIS online.',
];

let ws = null, isRecording = false, recognition = null, waveInterval = null;
let backendMode = 'detecting'; // 'server' | 'groq-direct' | 'offline'

// ── Boot ────────────────────────────────────────────
async function boot() {
  const overlay  = document.getElementById('boot-overlay');
  const statusEl = document.getElementById('boot-status');
  const progress = document.getElementById('boot-progress-fill');
  for (let i = 0; i < BOOT_MSGS.length; i++) {
    statusEl.textContent = BOOT_MSGS[i];
    progress.style.width = `${((i+1)/BOOT_MSGS.length)*100}%`;
    await sleep(i === BOOT_MSGS.length-1 ? 600 : 350);
  }
  await sleep(400);
  overlay.classList.add('hidden');
  initApp();
}

async function initApp() {
  updateClock();
  setInterval(updateClock, 1000);
  await detectBackend();
  fetchStats();
  setInterval(fetchStats, 8000);
  initVoice();
  setupInput();
  logMessage('system', 'YAHAVIS online. Ready for your commands, Boss.');
  animateWave(false);
}

// ── Backend detection ────────────────────────────────
async function detectBackend() {
  try {
    const r = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      backendMode = 'server';
      connectWebSocket();
      log('Backend: server mode');
      return;
    }
  } catch {}

  // No server — try direct Groq
  const savedKey = localStorage.getItem('groq_key') || GROQ_KEY;
  if (savedKey) {
    backendMode = 'groq-direct';
    log('Backend: direct Groq mode');
    logMessage('system', '⚡ Running in direct mode — LLM calls go straight to Groq.');
  } else {
    backendMode = 'offline';
    log('Backend: offline');
    logMessage('system', '⚠ No backend & no Groq key. Set key: localStorage.setItem("groq_key","gsk_...")');
  }
}

// ── WebSocket ─────────────────────────────────────────
function connectWebSocket() {
  try {
    ws = new WebSocket(WS_URL);
    ws.onopen    = () => log('WS connected');
    ws.onmessage = (e) => handleServerMessage(JSON.parse(e.data));
    ws.onerror   = () => log('WS error');
    ws.onclose   = () => { if (backendMode==='server') setTimeout(connectWebSocket, 3000); };
  } catch(e) { log('WS unavailable'); }
}

function handleServerMessage(msg) {
  switch (msg.type) {
    case 'log':        logMessage(msg.role, msg.text);        break;
    case 'stats':      updateStats(msg.data);                 break;
    case 'task':       updateTaskBar(msg.task, msg.progress); break;
    case 'api_status': updateApiSlots(msg.slots);             break;
    case 'voice_start':animateWave(true);                     break;
    case 'voice_end':  animateWave(false);                    break;
  }
}

// ── Command routing ──────────────────────────────────
function sendCommand(text) {
  logMessage('user', text);
  if (backendMode === 'server') {
    sendToServerWS(text);
    // Also POST for reliability
    fetch(`${API_URL}/api/command`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({text})
    }).then(r=>r.json()).then(d=>{
      if (d.response) logMessage('system', d.response);
    }).catch(()=>{});
  } else if (backendMode === 'groq-direct') {
    callGroqDirect(text);
  } else {
    logMessage('system','No backend available. Deploy YAHAVIS or set your Groq key.');
  }
}

function sendToServerWS(text) {
  if (ws && ws.readyState === WebSocket.OPEN)
    ws.send(JSON.stringify({ type:'command', text }));
}

// ── Direct Groq call (no backend needed) ─────────────
async function callGroqDirect(text) {
  animateWave(true);
  const key = localStorage.getItem('groq_key') || GROQ_KEY;
  if (!key) { logMessage('system','No Groq key. Set: localStorage.setItem("groq_key","gsk_...")'); animateWave(false); return; }

  const entry = createStreamEntry();
  try {
    const resp = await fetch(GROQ_URL, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: GROQ_MODEL,
        messages: [{ role:'system', content: SYSTEM_PROMPT }, { role:'user', content: text }],
        stream: true, max_tokens: 1024
      })
    });
    if (!resp.ok) throw new Error(`Groq ${resp.status}`);
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (data === '[DONE]') continue;
        try {
          const chunk = JSON.parse(data)?.choices?.[0]?.delta?.content || '';
          if (chunk) appendToStreamEntry(entry, chunk);
        } catch {}
      }
    }
  } catch (e) {
    appendToStreamEntry(entry, `[Error: ${e.message}]`);
  }
  animateWave(false);
}

// ── Stats ────────────────────────────────────────────
async function fetchStats() {
  if (backendMode !== 'server') { updateStatsOffline(); return; }
  try {
    const res = await fetch(`${API_URL}/api/status`, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) throw new Error();
    const data = await res.json();
    updateStats(data.system);
    updateApiSlots(data.api_slots);
    updateMemoryTags(data.memory);
  } catch { updateStatsOffline(); }
}

function updateStats(stats) {
  if (!stats) return;
  setValue('stat-cpu',   `${stats.cpu_pct||0}%`,  stats.cpu_pct>80?'crit':stats.cpu_pct>60?'warn':'');
  setValue('stat-ram',   `${stats.ram_pct||0}%`,  stats.ram_pct>85?'crit':stats.ram_pct>70?'warn':'');
  setValue('stat-bat',   `${stats.battery_pct||'?'}%`);
  setValue('stat-tasks', `${stats.tasks_done||0} done`);
  setBar('bar-cpu', stats.cpu_pct||0);
  setBar('bar-ram', stats.ram_pct||0);
}

function updateStatsOffline() {
  setValue('stat-cpu','—'); setValue('stat-ram','—');
}

function updateApiSlots(slots) {
  if (!slots) return;
  const c = document.getElementById('api-slots');
  c.innerHTML = '';
  Object.entries(slots).forEach(([id,s])=>{
    const pct = s.usage_pct||0;
    const cls = pct>80?'crit':pct>60?'warn':'';
    c.innerHTML += `<div class="api-slot">
      <div class="api-slot-name">${id.replace(/_/g,' ').toUpperCase()}</div>
      <div class="api-slot-bar"><div class="api-slot-fill ${cls}" style="width:${pct}%"></div></div>
      <div class="api-slot-meta"><span>${s.healthy?'✓ ACTIVE':'✗ DOWN'}</span><span>${pct.toFixed(0)}% used</span></div>
    </div>`;
  });
}

function updateMemoryTags(memory) {
  if (!memory) return;
  const list = document.getElementById('memory-list');
  if (list) list.innerHTML = Object.keys(memory).map(k=>`<span class="memory-tag">${escapeHtml(k)}</span>`).join('');
}

function updateTaskBar(task,progress) {
  document.getElementById('task-label').textContent = task||'Idle';
  document.getElementById('task-progress').style.width = `${progress||0}%`;
}

// ── Voice ─────────────────────────────────────────────
function initVoice() {
  const SR = window.SpeechRecognition||window.webkitSpeechRecognition;
  if (!SR) { document.getElementById('voice-btn').title='Voice not supported'; return; }
  recognition = new SR();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'hi-IN';
  recognition.onresult = (e)=>sendCommand(e.results[0][0].transcript);
  recognition.onend    = ()=>stopRecording();
  recognition.onerror  = (e)=>{ log('Voice:'+e.error); stopRecording(); };
}

document.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('voice-btn')?.addEventListener('click', toggleVoice);
});

function toggleVoice() { isRecording ? stopRecording() : startRecording(); }
function startRecording() {
  if (!recognition) return;
  isRecording = true;
  document.getElementById('voice-btn').classList.add('recording');
  document.getElementById('voice-btn').textContent = '⏹';
  animateWave(true);
  try { recognition.start(); } catch(e) { stopRecording(); }
}
function stopRecording() {
  isRecording = false;
  const btn = document.getElementById('voice-btn');
  if (btn) { btn.classList.remove('recording'); btn.textContent='🎤'; }
  animateWave(false);
  try { recognition?.stop(); } catch(e) {}
}

// ── Waveform ──────────────────────────────────────────
function animateWave(active) {
  const bars = document.querySelectorAll('.wave-bar');
  clearInterval(waveInterval);
  if (active) {
    bars.forEach(b=>b.classList.add('active'));
    waveInterval = setInterval(()=>bars.forEach(b=>b.style.height=`${Math.random()*28+4}px`),80);
  } else {
    bars.forEach(b=>{ b.classList.remove('active'); b.style.height=''; });
  }
}

// ── Input ─────────────────────────────────────────────
function setupInput() {
  const input = document.getElementById('text-input');
  const send  = document.getElementById('send-btn');
  input?.addEventListener('keydown',(e)=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendFromInput();} });
  send?.addEventListener('click', sendFromInput);
  document.querySelectorAll('.quick-btn').forEach(btn=>btn.addEventListener('click',()=>sendCommand(btn.dataset.cmd)));
}

function sendFromInput() {
  const input = document.getElementById('text-input');
  const text  = input?.value?.trim();
  if (!text) return;
  input.value = '';
  sendCommand(text);
}

// ── Log helpers ───────────────────────────────────────
function logMessage(role, text) {
  const logEl = document.getElementById('command-log');
  const entry = document.createElement('div');
  entry.className = `log-entry ${role}`;
  entry.innerHTML = `<div class="log-role">${role==='user'?'▶ YOU':'◆ YAHAVIS'} · ${timestamp()}</div><div>${escapeHtml(text)}</div>`;
  logEl.appendChild(entry);
  logEl.scrollTop = logEl.scrollHeight;
  while (logEl.children.length > 100) logEl.removeChild(logEl.firstChild);
}

function createStreamEntry() {
  const logEl = document.getElementById('command-log');
  const entry = document.createElement('div');
  entry.className = 'log-entry system';
  entry.innerHTML = `<div class="log-role">◆ YAHAVIS · ${timestamp()}</div><div class="stream-text"></div>`;
  logEl.appendChild(entry);
  logEl.scrollTop = logEl.scrollHeight;
  return entry;
}

function appendToStreamEntry(entry, chunk) {
  const t = entry.querySelector('.stream-text');
  if (t) t.textContent += chunk;
  document.getElementById('command-log').scrollTop = 99999;
}

// ── Utilities ─────────────────────────────────────────
function updateClock() {
  document.getElementById('time-display').textContent =
    new Date().toLocaleTimeString('en-IN',{hour12:false});
}
function timestamp() { return new Date().toLocaleTimeString('en-IN',{hour12:false}); }
function setValue(id,val,cls='') {
  const el=document.getElementById(id);
  if(!el)return; el.textContent=val; el.className=`stat-value ${cls}`.trim();
}
function setBar(id,pct) { const el=document.getElementById(id); if(el) el.style.width=`${Math.min(100,pct)}%`; }
function escapeHtml(t) { return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function sleep(ms) { return new Promise(r=>setTimeout(r,ms)); }
function log(msg)  { console.log(`[YAHAVIS] ${msg}`); }

window.addEventListener('load', boot);
