/* YAHAVIS HUD — app.js
   Live status, voice, WebSocket to Python backend.
*/

// Auto-detect: use relative URLs when deployed, fallback to localhost in dev
const IS_DEV   = location.hostname === '127.0.0.1' || location.hostname === 'localhost';
const API_URL  = IS_DEV ? 'http://127.0.0.1:7070' : '';
const WS_URL   = IS_DEV
  ? 'ws://127.0.0.1:7071'
  : (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
const BOOT_MSGS = [
  'Initializing neural core...',
  'Loading API rotation engine...',
  'Calibrating voice interface...',
  'Connecting to memory systems...',
  'Starting task orchestrator...',
  'YAHAVIS online.',
];

let ws = null;
let isRecording = false;
let recognition = null;
let waveInterval = null;

// ── Boot sequence ────────────────────────────────────
async function boot() {
  const overlay   = document.getElementById('boot-overlay');
  const statusEl  = document.getElementById('boot-status');
  const progress  = document.getElementById('boot-progress-fill');

  for (let i = 0; i < BOOT_MSGS.length; i++) {
    statusEl.textContent = BOOT_MSGS[i];
    progress.style.width = `${((i + 1) / BOOT_MSGS.length) * 100}%`;
    await sleep(i === BOOT_MSGS.length - 1 ? 600 : 350);
  }

  await sleep(400);
  overlay.classList.add('hidden');
  initApp();
}

// ── Init ─────────────────────────────────────────────
function initApp() {
  updateClock();
  setInterval(updateClock, 1000);
  connectWebSocket();
  fetchStats();
  setInterval(fetchStats, 5000);
  initVoice();
  setupInput();
  logMessage('system', 'YAHAVIS online. Ready for your commands, Boss.');
  animateWave(false);
}

// ── WebSocket ─────────────────────────────────────────
function connectWebSocket() {
  try {
    ws = new WebSocket(WS_URL);
    ws.onopen    = () => log('WS connected');
    ws.onmessage = (e) => handleServerMessage(JSON.parse(e.data));
    ws.onerror   = () => log('WS error — running in offline mode');
    ws.onclose   = () => setTimeout(connectWebSocket, 3000);
  } catch (e) {
    log('WS unavailable — offline mode active');
  }
}

function handleServerMessage(msg) {
  switch (msg.type) {
    case 'log':       logMessage(msg.role, msg.text);            break;
    case 'stats':     updateStats(msg.data);                     break;
    case 'task':      updateTaskBar(msg.task, msg.progress);     break;
    case 'api_status': updateApiSlots(msg.slots);                break;
    case 'voice_start': animateWave(true);                       break;
    case 'voice_end':   animateWave(false);                      break;
  }
}

function sendToServer(type, data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type, ...data }));
  }
}

// ── Command log ───────────────────────────────────────
function logMessage(role, text) {
  const log = document.getElementById('command-log');
  const entry = document.createElement('div');
  entry.className = `log-entry ${role}`;
  entry.innerHTML = `
    <div class="log-role">${role === 'user' ? '▶ YOU' : '◆ YAHAVIS'} · ${timestamp()}</div>
    <div>${escapeHtml(text)}</div>
  `;
  log.appendChild(entry);
  log.scrollTop = log.scrollHeight;

  // Limit log to 100 entries
  while (log.children.length > 100) {
    log.removeChild(log.firstChild);
  }
}

// ── Stats + API slots ─────────────────────────────────
async function fetchStats() {
  try {
    const res = await fetch(`${API_URL}/api/status`);
    if (!res.ok) throw new Error();
    const data = await res.json();
    updateStats(data.system);
    updateApiSlots(data.api_slots);
    updateMemoryTags(data.memory);
  } catch (e) {
    updateStatsOffline();
  }
}

function updateStats(stats) {
  if (!stats) return;
  setValue('stat-cpu', `${stats.cpu_pct || 0}%`,   stats.cpu_pct > 80 ? 'crit' : stats.cpu_pct > 60 ? 'warn' : '');
  setValue('stat-ram', `${stats.ram_pct || 0}%`,   stats.ram_pct > 85 ? 'crit' : stats.ram_pct > 70 ? 'warn' : '');
  setValue('stat-bat', `${stats.battery_pct || '?'}%`);
  setValue('stat-tasks', `${stats.tasks_done || 0} done`);
  setBar('bar-cpu', stats.cpu_pct || 0);
  setBar('bar-ram', stats.ram_pct || 0);
}

function updateStatsOffline() {
  setValue('stat-cpu', '—');
  setValue('stat-ram', '—');
}

function updateApiSlots(slots) {
  if (!slots) return;
  const container = document.getElementById('api-slots');
  container.innerHTML = '';
  Object.entries(slots).forEach(([id, slot]) => {
    const pct = slot.usage_pct || 0;
    const fillClass = pct > 80 ? 'crit' : pct > 60 ? 'warn' : '';
    container.innerHTML += `
      <div class="api-slot">
        <div class="api-slot-name">${id.replace(/_/g,' ').toUpperCase()}</div>
        <div class="api-slot-bar">
          <div class="api-slot-fill ${fillClass}" style="width:${pct}%"></div>
        </div>
        <div class="api-slot-meta">
          <span>${slot.healthy ? '✓ ACTIVE' : '✗ DOWN'}</span>
          <span>${pct.toFixed(0)}% used</span>
        </div>
      </div>
    `;
  });
}

function updateMemoryTags(memory) {
  if (!memory) return;
  const list = document.getElementById('memory-list');
  if (!list) return;
  list.innerHTML = Object.keys(memory)
    .map(k => `<span class="memory-tag">${escapeHtml(k)}</span>`)
    .join('');
}

function updateTaskBar(task, progress) {
  document.getElementById('task-label').textContent = task || 'Idle';
  document.getElementById('task-progress').style.width = `${progress || 0}%`;
}

// ── Voice ──────────────────────────────────────────────
function initVoice() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    document.getElementById('voice-btn').title = 'Voice not supported in this browser';
    return;
  }
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'hi-IN'; // Hindi-English mix

  recognition.onresult = (e) => {
    const text = e.results[0][0].transcript;
    sendCommand(text);
  };
  recognition.onend    = () => stopRecording();
  recognition.onerror  = (e) => { log('Voice error: ' + e.error); stopRecording(); };
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('voice-btn')?.addEventListener('click', toggleVoice);
});

function toggleVoice() {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
}

function startRecording() {
  if (!recognition) return;
  isRecording = true;
  document.getElementById('voice-btn').classList.add('recording');
  document.getElementById('voice-btn').textContent = '⏹';
  animateWave(true);
  try { recognition.start(); } catch (e) { stopRecording(); }
}

function stopRecording() {
  isRecording = false;
  const btn = document.getElementById('voice-btn');
  if (btn) { btn.classList.remove('recording'); btn.textContent = '🎤'; }
  animateWave(false);
  try { recognition?.stop(); } catch (e) {}
}

// ── Waveform animation ────────────────────────────────
function animateWave(active) {
  const bars = document.querySelectorAll('.wave-bar');
  clearInterval(waveInterval);
  if (active) {
    bars.forEach(b => b.classList.add('active'));
    waveInterval = setInterval(() => {
      bars.forEach(b => {
        b.style.height = `${Math.random() * 28 + 4}px`;
      });
    }, 80);
  } else {
    bars.forEach(b => {
      b.classList.remove('active');
      b.style.height = '';
    });
  }
}

// ── Input handling ────────────────────────────────────
function setupInput() {
  const input = document.getElementById('text-input');
  const send  = document.getElementById('send-btn');

  input?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendFromInput();
    }
  });
  send?.addEventListener('click', sendFromInput);

  // Quick action buttons
  document.querySelectorAll('.quick-btn').forEach(btn => {
    btn.addEventListener('click', () => sendCommand(btn.dataset.cmd));
  });
}

function sendFromInput() {
  const input = document.getElementById('text-input');
  const text  = input?.value?.trim();
  if (!text) return;
  input.value = '';
  sendCommand(text);
}

function sendCommand(text) {
  logMessage('user', text);

  // Try SSE streaming first (cloud), fallback to WS (local)
  if (!IS_DEV) {
    streamCommand(text);
  } else {
    sendToServer('command', { text });
    fetch(`${API_URL}/api/command`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }).catch(() => {});
  }
}

function streamCommand(text) {
  const url = `${API_URL}/api/chat/stream?text=${encodeURIComponent(text)}`;
  const es  = new EventSource(url);
  let   responseEl = null;

  es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.chunk) {
      if (!responseEl) {
        responseEl = createStreamEntry();
      }
      appendToStreamEntry(responseEl, data.chunk);
    }
    if (data.done) {
      es.close();
      animateWave(false);
    }
    if (data.error) {
      logMessage('system', `Error: ${data.error}`);
      es.close();
      animateWave(false);
    }
  };
  es.onerror = () => {
    es.close();
    animateWave(false);
  };
  animateWave(true);
}

function createStreamEntry() {
  const logEl  = document.getElementById('command-log');
  const entry  = document.createElement('div');
  entry.className = 'log-entry system';
  entry.innerHTML = `
    <div class="log-role">◆ YAHAVIS · ${timestamp()}</div>
    <div class="stream-text"></div>
  `;
  logEl.appendChild(entry);
  logEl.scrollTop = logEl.scrollHeight;
  return entry;
}

function appendToStreamEntry(entry, chunk) {
  const textEl = entry.querySelector('.stream-text');
  if (textEl) textEl.textContent += chunk;
  const logEl = document.getElementById('command-log');
  logEl.scrollTop = logEl.scrollHeight;
}

// ── Utilities ─────────────────────────────────────────
function updateClock() {
  const now = new Date();
  document.getElementById('time-display').textContent =
    now.toLocaleTimeString('en-IN', { hour12: false });
}

function timestamp() {
  return new Date().toLocaleTimeString('en-IN', { hour12: false });
}

function setValue(id, val, cls = '') {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = val;
  el.className = `stat-value ${cls}`.trim();
}

function setBar(id, pct) {
  const el = document.getElementById(id);
  if (el) el.style.width = `${Math.min(100, pct)}%`;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function log(msg)  { console.log(`[YAHAVIS] ${msg}`); }

// ── Start boot ────────────────────────────────────────
window.addEventListener('load', boot);
