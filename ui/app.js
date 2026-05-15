/**
 * YAHAVIS app.js v2.0 — Full Jarvis Mode
 * Features: TTS voice output, streaming SSE, wake word, conversation history,
 *           direct Groq fallback, auto-detect backend
 */

// ── Config ───────────────────────────────────────────
const IS_DEV  = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
const API     = IS_DEV ? 'http://127.0.0.1:7070' : '';
const WAKE    = ['hey yahavi', 'yahavi', 'hey yahavis', 'yahavis'];
const GROQ_URL= 'https://api.groq.com/openai/v1/chat/completions';
const GROQ_MODEL = 'llama-3.3-70b-versatile';

const SYSTEM_PROMPT = `You are YAHAVIS — Yahavi AI System, a highly advanced AI assistant built by Myth for Hackknow.
Personality: Like J.A.R.V.I.S. from Iron Man — composed, witty, precise, dry humor. Never robotic.
Address the user as "Boss" or "Sir" alternating naturally.
You understand Hindi-English mix (Hinglish) perfectly. Always reply in the same language the user uses.
Be concise. Confirm task completion. Never refuse — find alternatives.`;

// ── State ─────────────────────────────────────────────
let backendMode  = 'detecting';
let isRecording  = false;
let isSpeaking   = false;
let ttsEnabled   = true;
let wakeEnabled  = true;
let recognition  = null;
let waveAnim     = null;
let sessionStart = Date.now();
let msgCount     = 0;
let history      = [];          // [{role, content}]
let currentEntry = null;

// ── Boot sequence ─────────────────────────────────────
const BOOT_STEPS = [
  'Initializing neural core...',
  'Loading LLM rotation engine...',
  'Calibrating voice interface...',
  'Connecting to memory matrix...',
  'Warming up Groq LLaMA-3.3-70B...',
  'Establishing Hackknow link...',
  'YAHAVIS online. At your service.',
];

async function boot() {
  const bar = document.getElementById('boot-bar');
  const msg = document.getElementById('boot-msg');
  for (let i = 0; i < BOOT_STEPS.length; i++) {
    msg.textContent = BOOT_STEPS[i];
    bar.style.width  = `${((i + 1) / BOOT_STEPS.length) * 100}%`;
    await sleep(i === BOOT_STEPS.length - 1 ? 700 : 380);
  }
  await sleep(500);
  const bootEl = document.getElementById('boot');
  bootEl.classList.add('fade-out');
  setTimeout(() => {
    bootEl.style.display = 'none';
    document.getElementById('hud').classList.remove('hidden');
    initApp();
  }, 1000);
}

async function initApp() {
  updateClock();
  setInterval(updateClock, 1000);
  setInterval(updateUptime, 60000);
  await detectBackend();
  fetchStatus();
  setInterval(fetchStatus, 15000);
  initVoice();
  setupInput();
  setArcState('standby');
  appendMsg('sys', 'SYSTEM', 'YAHAVIS online. All systems operational, Boss. How can I assist you today?');
  speak('YAHAVIS online. All systems operational, Boss. How can I assist you today?');
}

// ── Backend detection ─────────────────────────────────
async function detectBackend() {
  try {
    const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(4000) });
    if (r.ok) {
      backendMode = 'server';
      setEl('backend-mode', 'SERVER');
      setEl('mode-label', 'SERVER MODE');
      log('Backend: server');
      return;
    }
  } catch {}

  const key = localStorage.getItem('groq_key') || '';
  if (key) {
    backendMode = 'groq-direct';
    setEl('backend-mode', 'DIRECT');
    setEl('mode-label', 'DIRECT GROQ MODE');
    log('Backend: direct Groq');
  } else {
    backendMode = 'offline';
    setEl('backend-mode', 'OFFLINE');
    setEl('mode-label', 'OFFLINE');
    appendMsg('sys', 'WARNING', 'No backend. Set Groq key: click "Set Groq Key" button.');
  }
}

// ── Stats fetch ───────────────────────────────────────
async function fetchStatus() {
  if (backendMode !== 'server') {
    renderApiSlots({
      'Groq · LLaMA 3.3-70B': { healthy: !!localStorage.getItem('groq_key'), status: localStorage.getItem('groq_key') ? 'active' : 'inactive', usage_pct: 0 },
      'Gemini · Flash 1.5':   { healthy: false, status: 'inactive', usage_pct: 0 },
      'OpenRouter · Free':     { healthy: false, status: 'inactive', usage_pct: 0 },
    });
    return;
  }
  try {
    const r = await fetch(`${API}/api/status`, { signal: AbortSignal.timeout(5000) });
    const d = await r.json();
    if (d.api_slots) renderApiSlots(d.api_slots);
  } catch {}
}

function renderApiSlots(slots) {
  const c = document.getElementById('api-slots');
  c.innerHTML = '';
  for (const [name, s] of Object.entries(slots)) {
    const pct = s.usage_pct || 0;
    const cls = !s.healthy ? 'dead' : pct > 80 ? 'warn' : '';
    const statusCls = s.healthy ? 'api-active' : 'api-down';
    const statusTxt = s.healthy ? '✓ ACTIVE' : '✗ DOWN';
    c.innerHTML += `<div class="api-slot">
      <div class="api-name">${name}</div>
      <div class="api-bar"><div class="api-fill ${cls}" style="width:${pct}%"></div></div>
      <div class="api-meta"><span class="${statusCls}">${statusTxt}</span><span>${pct.toFixed(0)}% used</span></div>
    </div>`;
  }
}

// ── MAIN COMMAND HANDLER ──────────────────────────────
async function sendCommand(text) {
  text = text.trim();
  if (!text) return;
  msgCount++;
  setEl('msg-count', msgCount);
  appendMsg('user', '▶ YOU', text);
  history.push({ role: 'user', content: text });
  if (history.length > 20) history = history.slice(-20);

  setArcState('thinking');

  if (backendMode === 'server') {
    await streamFromServer(text);
  } else if (backendMode === 'groq-direct') {
    await streamDirect(text);
  } else {
    appendMsg('sys', 'YAHAVIS', 'No backend available, Boss. Click "Set Groq Key" to go direct.');
    setArcState('standby');
  }
}

// ── Server streaming (SSE) ────────────────────────────
async function streamFromServer(text) {
  currentEntry = appendMsg('ai', '◆ YAHAVIS', '', true);
  let fullText = '';

  try {
    const resp = await fetch(`${API}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, history: history.slice(0, -1) }),
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

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
        const raw = line.slice(6).trim();
        try {
          const d = JSON.parse(raw);
          if (d.chunk) {
            fullText += d.chunk;
            updateStreamEntry(fullText);
          }
          if (d.done || d.error) break;
        } catch {}
      }
    }
  } catch (e) {
    // Fallback to POST
    try {
      const r = await fetch(`${API}/api/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, history: history.slice(0, -1) }),
      });
      const d = await r.json();
      fullText = d.response || d.error || 'No response.';
      updateStreamEntry(fullText);
    } catch (e2) {
      fullText = `Error: ${e2.message}`;
      updateStreamEntry(fullText);
    }
  }

  finalizeEntry(fullText);
  history.push({ role: 'assistant', content: fullText });
  speak(fullText);
  setArcState('standby');
}

// ── Direct Groq streaming ─────────────────────────────
async function streamDirect(text) {
  const key = localStorage.getItem('groq_key') || '';
  if (!key) { appendMsg('sys','YAHAVIS','No Groq key set, Boss. Use the Set Groq Key button.'); setArcState('standby'); return; }

  currentEntry = appendMsg('ai', '◆ YAHAVIS', '', true);
  let fullText = '';

  const msgs = [{ role: 'system', content: SYSTEM_PROMPT }];
  for (const h of history.slice(0, -1)) msgs.push(h);
  msgs.push({ role: 'user', content: text });

  try {
    const resp = await fetch(GROQ_URL, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: GROQ_MODEL, messages: msgs, stream: true, max_tokens: 1024, temperature: 0.7 }),
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
        const d = line.slice(6).trim();
        if (d === '[DONE]') break;
        try {
          const chunk = JSON.parse(d)?.choices?.[0]?.delta?.content || '';
          if (chunk) { fullText += chunk; updateStreamEntry(fullText); }
        } catch {}
      }
    }
  } catch (e) {
    fullText = `Connection error: ${e.message}. Check Groq key, Boss.`;
    updateStreamEntry(fullText);
  }

  finalizeEntry(fullText);
  history.push({ role: 'assistant', content: fullText });
  speak(fullText);
  setArcState('standby');
}

// ── Text-to-Speech ────────────────────────────────────
let speechQueue = [];
let speechBusy  = false;

function speak(text) {
  if (!ttsEnabled || !('speechSynthesis' in window)) return;
  // Strip markdown and long pauses
  const clean = text.replace(/[#*`_~\[\]]/g, '').replace(/\n+/g, ' ').trim();
  if (!clean) return;
  speechQueue.push(clean);
  if (!speechBusy) drainSpeech();
}

function drainSpeech() {
  if (!speechQueue.length) { speechBusy = false; return; }
  speechBusy = true;
  const text = speechQueue.shift();
  const utter = new SpeechSynthesisUtterance(text);
  utter.rate  = 1.05;
  utter.pitch = 0.9;
  utter.volume = 1;
  utter.lang  = 'en-IN';

  // Pick a good voice
  const voices = speechSynthesis.getVoices();
  const preferred = voices.find(v => v.name.toLowerCase().includes('google uk english male'))
    || voices.find(v => v.name.toLowerCase().includes('daniel'))
    || voices.find(v => v.name.toLowerCase().includes('alex'))
    || voices.find(v => v.lang === 'en-IN')
    || voices.find(v => v.lang.startsWith('en'));
  if (preferred) utter.voice = preferred;

  utter.onend  = drainSpeech;
  utter.onerror = drainSpeech;
  isSpeaking = true;
  setEl('tts-status', 'Speaking...');
  speechSynthesis.speak(utter);
  utter.onend = () => { isSpeaking = false; setEl('tts-status', 'Ready'); drainSpeech(); };
}

function stopSpeaking() {
  speechSynthesis.cancel();
  speechQueue = [];
  isSpeaking = false;
  speechBusy = false;
  setEl('tts-status', 'Ready');
}

// ── Voice recognition ─────────────────────────────────
function initVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    setEl('voice-status', 'Not supported');
    setEl('wake-status', 'N/A');
    document.getElementById('voice-btn').disabled = true;
    return;
  }

  recognition = new SR();
  recognition.continuous  = false;
  recognition.interimResults = false;
  recognition.lang = 'hi-IN'; // Hindi-English bilingual

  recognition.onstart = () => {
    setEl('voice-status', 'Listening...');
    setArcState('listening');
    waveActive(true);
  };

  recognition.onresult = (e) => {
    const transcript = e.results[e.results.length - 1][0].transcript.trim();
    log(`Voice: "${transcript}"`);

    // Wake word check (only when not recording)
    if (!isRecording) {
      const lower = transcript.toLowerCase();
      const hasWake = WAKE.some(w => lower.includes(w));
      if (!hasWake) {
        stopRecording();
        return;
      }
      // Strip wake word
      let cmd = transcript;
      for (const w of WAKE) { cmd = cmd.replace(new RegExp(w, 'gi'), '').trim(); }
      if (cmd) sendCommand(cmd);
      else {
        // Just the wake word — prompt user
        speak('Yes Boss, I am listening.');
        appendMsg('sys', 'YAHAVIS', 'Yes Boss, I am listening.');
      }
    } else {
      // Manual push-to-talk — send directly
      if (transcript) sendCommand(transcript);
    }
    stopRecording();
  };

  recognition.onerror = (e) => {
    log(`Voice error: ${e.error}`);
    setEl('voice-status', e.error === 'no-speech' ? 'No speech' : e.error);
    stopRecording();
  };

  recognition.onend = () => {
    if (isRecording) {
      // Restart for continuous wake word
      try { recognition.start(); } catch {}
    } else {
      waveActive(false);
      setArcState('standby');
    }
  };

  // Start background wake word listening
  if (wakeEnabled) startWakeListening();
}

function startWakeListening() {
  if (!recognition || isRecording) return;
  try {
    recognition.lang = 'hi-IN';
    recognition.start();
    setEl('wake-status', 'Active');
  } catch {}
}

function stopWakeListening() {
  try { recognition.stop(); } catch {}
  setEl('wake-status', 'Off');
  waveActive(false);
}

function startRecording() {
  if (!recognition) return;
  isRecording = true;
  stopSpeaking();
  document.getElementById('voice-btn').classList.add('recording');
  document.getElementById('voice-icon').textContent = '⏹';
  try { recognition.stop(); } catch {}
  setTimeout(() => {
    try { recognition.lang = 'hi-IN'; recognition.start(); } catch {}
  }, 200);
}

function stopRecording() {
  isRecording = false;
  document.getElementById('voice-btn').classList.remove('recording');
  document.getElementById('voice-icon').textContent = '🎤';
  waveActive(false);
  setEl('voice-status', 'Ready');
  if (wakeEnabled) setTimeout(startWakeListening, 500);
}

// ── Waveform ──────────────────────────────────────────
function waveActive(on) {
  const bars = document.querySelectorAll('.wb');
  clearInterval(waveAnim);
  if (on) {
    bars.forEach(b => b.classList.add('active'));
    waveAnim = setInterval(() => bars.forEach(b => b.style.height = `${Math.random() * 26 + 4}px`), 80);
  } else {
    bars.forEach(b => { b.classList.remove('active'); b.style.height = ''; });
  }
}

// ── Arc reactor state ─────────────────────────────────
function setArcState(state) {
  const core = document.getElementById('arc-core');
  const icon = document.getElementById('arc-icon');
  const stat = document.getElementById('arc-status');
  core.className = '';
  const STATES = {
    standby:   { cls: '',          icon: '◈', label: 'STANDBY'  },
    listening: { cls: 'listening', icon: '◉', label: 'LISTENING'},
    thinking:  { cls: 'thinking',  icon: '◌', label: 'THINKING' },
  };
  const s = STATES[state] || STATES.standby;
  if (s.cls) core.classList.add(s.cls);
  icon.textContent = s.icon;
  stat.textContent = s.label;
}

// ── Chat log ─────────────────────────────────────────
function appendMsg(type, role, text, streaming = false) {
  const log = document.getElementById('chat-log');
  const el  = document.createElement('div');
  el.className = `msg ${type}`;
  const ts = new Date().toLocaleTimeString('en-IN', { hour12: false });
  el.innerHTML = `<div class="msg-header"><span>${role}</span><span style="color:var(--dim);font-size:8px">${ts}</span></div>
<div class="msg-body">${esc(text)}${streaming ? '<span class="stream-cursor"></span>' : ''}</div>`;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  while (log.children.length > 150) log.removeChild(log.firstChild);
  currentEntry = el;
  return el;
}

function updateStreamEntry(text) {
  if (!currentEntry) return;
  const body = currentEntry.querySelector('.msg-body');
  if (body) {
    body.innerHTML = esc(text) + '<span class="stream-cursor"></span>';
  }
  document.getElementById('chat-log').scrollTop = 99999;
}

function finalizeEntry(text) {
  if (!currentEntry) return;
  const body = currentEntry.querySelector('.msg-body');
  if (body) body.innerHTML = esc(text);
  currentEntry = null;
}

// ── Input setup ───────────────────────────────────────
function setupInput() {
  const input = document.getElementById('text-input');
  const send  = document.getElementById('send-btn');
  const vBtn  = document.getElementById('voice-btn');

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitInput(); }
  });
  send.addEventListener('click', submitInput);
  vBtn.addEventListener('click', () => {
    if (isRecording) stopRecording();
    else startRecording();
  });

  document.querySelectorAll('.qb').forEach(b =>
    b.addEventListener('click', () => sendCommand(b.dataset.cmd))
  );
}

function submitInput() {
  const input = document.getElementById('text-input');
  const text  = input.value.trim();
  if (!text) return;
  input.value = '';
  sendCommand(text);
}

// ── Toggles ───────────────────────────────────────────
function toggleTTS() {
  ttsEnabled = !ttsEnabled;
  const el = document.getElementById('tts-toggle');
  el.classList.toggle('active', ttsEnabled);
  setEl('tts-status', ttsEnabled ? 'Enabled' : 'Off');
  if (!ttsEnabled) stopSpeaking();
}

function toggleWake() {
  wakeEnabled = !wakeEnabled;
  const el = document.getElementById('wake-toggle');
  el.classList.toggle('active', wakeEnabled);
  if (wakeEnabled) startWakeListening();
  else stopWakeListening();
}

function clearChat() {
  document.getElementById('chat-log').innerHTML = '';
  history = [];
  appendMsg('sys', 'SYSTEM', 'Chat cleared. Ready for new session, Boss.');
}

function setGroqKey() {
  const key = prompt('Enter your Groq API key (gsk_...):\n\nGet free key at: console.groq.com');
  if (!key) return;
  localStorage.setItem('groq_key', key.trim());
  backendMode = 'groq-direct';
  setEl('backend-mode', 'DIRECT');
  setEl('mode-label', 'DIRECT GROQ MODE');
  appendMsg('sys', 'SYSTEM', 'Groq key saved. Direct mode activated, Boss.');
  fetchStatus();
}

// ── Clock / uptime ────────────────────────────────────
function updateClock() {
  const now = new Date();
  setEl('clock', now.toLocaleTimeString('en-IN', { hour12: false }));
  setEl('date-display', now.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }));
}

function updateUptime() {
  const mins = Math.round((Date.now() - sessionStart) / 60000);
  setEl('uptime', mins < 60 ? `${mins}m` : `${Math.floor(mins / 60)}h ${mins % 60}m`);
}

// ── Utilities ─────────────────────────────────────────
function setEl(id, val) { const e = document.getElementById(id); if (e) e.textContent = val; }
function esc(t) { return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>'); }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function log(m) { console.log(`[YAHAVIS] ${m}`); }

// ── Start ─────────────────────────────────────────────
window.addEventListener('load', boot);

// Load voices async (Chrome needs this)
if ('speechSynthesis' in window) {
  speechSynthesis.onvoiceschanged = () => {};
}
