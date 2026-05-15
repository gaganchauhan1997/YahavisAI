/**
 * YAHAVIS app.js v2.1 — Mobile-First Jarvis
 * Works on: Chrome Android/iOS, Chrome Desktop, Edge
 * Features: TTS voice output, streaming SSE, wake word, conversation history
 */

const API   = '';   // same origin — worker handles everything
const WAKE  = ['hey yahavi','yahavi','hey yahavis','yahavis'];
const GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions';
const GROQ_MODEL = 'llama-3.3-70b-versatile';
const SYS = `You are YAHAVIS — Yahavi AI System built by Myth for Hackknow.
Personality: Like JARVIS from Iron Man — composed, witty, dry humor. Never robotic.
Address user as "Boss" or "Sir". Understand Hindi-English mix (Hinglish).
Reply in same language as user. Be concise. Confirm task done. Never refuse.`;

let mode    = 'detecting';
let rec     = null;
let recOn   = false;
let wakeOn  = true;
let ttsOn   = true;
let history = [];
let msgCount= 0;
let curEntry= null;
let waveInt = null;
let speaking= false;
let t0      = Date.now();

// ── BOOT ─────────────────────────────────────────────
const STEPS = [
  'Initializing neural core...',
  'Loading LLM engines...',
  'Calibrating voice systems...',
  'Connecting to Hackknow...',
  'Warming up LLaMA-3.3-70B...',
  'YAHAVIS online.',
];
async function boot() {
  const bar = $('boot-bar'), msg = $('boot-msg');
  for (let i = 0; i < STEPS.length; i++) {
    msg.textContent = STEPS[i];
    bar.style.width = ((i+1)/STEPS.length*100) + '%';
    await wait(i === STEPS.length-1 ? 600 : 400);
  }
  await wait(400);
  $('boot').classList.add('out');
  setTimeout(() => {
    $('boot').style.display = 'none';
    $('app').style.display  = 'flex';
    init();
  }, 900);
}

async function init() {
  clockTick();
  setInterval(clockTick, 1000);
  setInterval(uptickSession, 60000);
  await detectBackend();
  fetchStatus();
  setInterval(fetchStatus, 20000);
  setupVoice();
  setupInput();
  setArc('standby');
  addMsg('sys','◆ SYSTEM','YAHAVIS online. All systems operational. At your service, Boss.');
  speak('YAHAVIS online. At your service, Boss.');
}

// ── BACKEND ───────────────────────────────────────────
async function detectBackend() {
  try {
    const r = await fetch('/health', { signal: AbortSignal.timeout(5000) });
    if (r.ok) {
      mode = 'server';
      $('backend-info').textContent = '✓ Server: yahavis.hackknow.com';
      return;
    }
  } catch {}
  const key = localStorage.getItem('groq_key') || '';
  if (key) {
    mode = 'direct';
    $('backend-info').textContent = '⚡ Direct Groq mode';
  } else {
    mode = 'offline';
    $('backend-info').textContent = '✗ Offline — set Groq key';
    addMsg('sys','⚠ SYSTEM','No API key found. Tap ☰ → Set Groq Key to activate.');
  }
}

async function fetchStatus() {
  if (mode !== 'server') {
    renderSlots({
      'Groq · LLaMA 3.3-70B': { healthy: !!localStorage.getItem('groq_key'), usage_pct:0 },
    });
    return;
  }
  try {
    const r = await fetch('/api/status',{signal:AbortSignal.timeout(5000)});
    const d = await r.json();
    if (d.api_slots) renderSlots(d.api_slots);
  } catch {}
}

function renderSlots(slots) {
  const c = $('api-slots-menu'); c.innerHTML = '';
  for (const [name, s] of Object.entries(slots)) {
    const pct = s.usage_pct || 0;
    const cls = !s.healthy ? 'dead' : '';
    c.innerHTML += `<div class="api-slot">
      <div class="api-name">${name}</div>
      <div class="api-bar"><div class="api-fill ${cls}" style="width:${pct}%"></div></div>
      <div class="api-meta"><span class="${s.healthy?'api-up':'api-dn'}">${s.healthy?'✓ ACTIVE':'✗ DOWN'}</span></div>
    </div>`;
  }
}

// ── SEND COMMAND ──────────────────────────────────────
async function sendCmd(text) {
  text = text.trim();
  if (!text) return;
  msgCount++;
  addMsg('user','▶ YOU', text);
  history.push({ role:'user', content:text });
  if (history.length > 20) history = history.slice(-20);
  closeMenu();
  setArc('think');

  if (mode === 'server') await streamServer(text);
  else if (mode === 'direct') await streamDirect(text);
  else addMsg('sys','⚠ YAHAVIS','No backend. Tap ☰ → Set Groq Key.');
}

// ── STREAM FROM SERVER ────────────────────────────────
async function streamServer(text) {
  curEntry = addMsg('ai','◆ YAHAVIS','',true);
  let full = '';
  try {
    const resp = await fetch('/api/chat/stream', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ text, history: history.slice(0,-1) }),
    });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const {done,value} = await reader.read();
      if (done) break;
      buf += dec.decode(value,{stream:true});
      const lines = buf.split('\n'); buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const d = JSON.parse(line.slice(6));
          if (d.chunk) { full += d.chunk; updateEntry(full); }
          if (d.done || d.error) break;
        } catch {}
      }
    }
  } catch (e) {
    // fallback to POST
    try {
      const r = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({text,history:history.slice(0,-1)})});
      const d = await r.json();
      full = d.response || d.error || 'Error';
      updateEntry(full);
    } catch(e2){ full='Connection error: '+e2.message; updateEntry(full); }
  }
  finalEntry(full);
  history.push({role:'assistant',content:full});
  speak(full);
  setArc('standby');
}

// ── STREAM DIRECT GROQ ────────────────────────────────
async function streamDirect(text) {
  const key = localStorage.getItem('groq_key')||'';
  if (!key) { addMsg('sys','⚠','No Groq key. Tap ☰ → Set Groq Key.'); setArc('standby'); return; }
  curEntry = addMsg('ai','◆ YAHAVIS','',true);
  let full = '';
  const msgs = [{role:'system',content:SYS},...history.slice(0,-1),{role:'user',content:text}];
  try {
    const resp = await fetch(GROQ_URL,{
      method:'POST',
      headers:{'Authorization':'Bearer '+key,'Content-Type':'application/json'},
      body:JSON.stringify({model:GROQ_MODEL,messages:msgs,stream:true,max_tokens:1024,temperature:0.7}),
    });
    if (!resp.ok) throw new Error('Groq '+resp.status);
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const {done,value} = await reader.read();
      if (done) break;
      buf += dec.decode(value,{stream:true});
      const lines = buf.split('\n'); buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const d = line.slice(6).trim();
        if (d==='[DONE]') break;
        try {
          const chunk = JSON.parse(d)?.choices?.[0]?.delta?.content||'';
          if (chunk){ full+=chunk; updateEntry(full); }
        } catch {}
      }
    }
  } catch(e){ full='Error: '+e.message; updateEntry(full); }
  finalEntry(full);
  history.push({role:'assistant',content:full});
  speak(full);
  setArc('standby');
}

// ── TTS ────────────────────────────────────────────────
let spQ = [], spBusy = false;
function speak(text) {
  if (!ttsOn || !window.speechSynthesis) return;
  const clean = text.replace(/[*#`_~\[\]>]/g,'').replace(/\n+/g,' ').trim();
  if (!clean) return;
  spQ.push(clean); if (!spBusy) drainSpeak();
}
function drainSpeak() {
  if (!spQ.length) { spBusy=false; return; }
  spBusy = true;
  const u = new SpeechSynthesisUtterance(spQ.shift());
  u.rate=1.0; u.pitch=0.88; u.volume=1; u.lang='en-IN';
  const vs = speechSynthesis.getVoices();
  const v = vs.find(v=>v.name.toLowerCase().includes('male')&&v.lang.startsWith('en'))
    || vs.find(v=>v.lang==='en-IN')
    || vs.find(v=>v.lang.startsWith('en')&&!v.name.toLowerCase().includes('female'));
  if (v) u.voice = v;
  u.onend = u.onerror = drainSpeak;
  speechSynthesis.speak(u);
}
function stopSpeak(){ speechSynthesis.cancel(); spQ=[]; spBusy=false; }

// ── VOICE RECOGNITION ─────────────────────────────────
function setupVoice() {
  const SR = window.SpeechRecognition||window.webkitSpeechRecognition;
  if (!SR) return;
  rec = new SR();
  rec.continuous = false;
  rec.interimResults = false;
  rec.lang = 'hi-IN';

  rec.onstart  = ()=>{ setArc('listen'); waveSet(true); };
  rec.onresult = (e)=>{
    const t = e.results[e.results.length-1][0].transcript.trim();
    if (!recOn) {
      // Wake word mode
      const lo = t.toLowerCase();
      if (!WAKE.some(w=>lo.includes(w))) { stopRec(); return; }
      let cmd = t;
      WAKE.forEach(w=>{ cmd = cmd.replace(new RegExp(w,'gi'),'').trim(); });
      if (cmd) sendCmd(cmd);
      else { speak('Yes Boss, listening.'); addMsg('sys','◆','Yes Boss, I am listening.'); }
    } else {
      if (t) sendCmd(t);
    }
    stopRec();
  };
  rec.onerror = ()=> stopRec();
  rec.onend   = ()=>{
    waveSet(false);
    if (recOn) { stopRec(); return; }
    if (wakeOn) setTimeout(startWake, 600);
  };
  if (wakeOn) startWake();
}

function startWake() {
  if (!rec||recOn) return;
  try { rec.lang='hi-IN'; rec.start(); } catch {}
}
function startRec() {
  if (!rec) { addMsg('sys','⚠','Mic not available in this browser.'); return; }
  recOn = true; stopSpeak();
  $('mic-btn').classList.add('rec');
  $('mic-btn').textContent = '⏹';
  try { rec.stop(); } catch {}
  setTimeout(()=>{ try { rec.lang='hi-IN'; rec.start(); } catch {} }, 250);
}
function stopRec() {
  recOn = false;
  $('mic-btn').classList.remove('rec');
  $('mic-btn').textContent = '🎤';
  waveSet(false);
  if (wakeOn) setTimeout(startWake, 500);
}
function toggleVoice() { recOn ? stopRec() : startRec(); }
function waveSet(on) {
  clearInterval(waveInt);
  const bars = document.querySelectorAll('.wb');
  if (on) {
    bars.forEach(b=>b.classList.add('on'));
    waveInt = setInterval(()=>bars.forEach(b=>b.style.height=(Math.random()*24+4)+'px'),80);
  } else {
    bars.forEach(b=>{ b.classList.remove('on'); b.style.height=''; });
  }
}

// ── ARC STATE ─────────────────────────────────────────
function setArc(state) {
  const c=$('arc-core'), icon=$('arc-icon'), lbl=$('arc-lbl');
  c.className='';
  const S={standby:{cls:'',icon:'◈',lbl:'STANDBY'},
            listen:{cls:'listen',icon:'◉',lbl:'LISTENING'},
            think:{cls:'think',icon:'◌',lbl:'THINKING'}};
  const s=S[state]||S.standby;
  if(s.cls) c.classList.add(s.cls);
  icon.textContent=s.icon; lbl.textContent=s.lbl;
}

// ── CHAT LOG ──────────────────────────────────────────
function addMsg(type, role, text, streaming=false) {
  const log=$('chat-log'), el=document.createElement('div');
  el.className='msg '+type;
  const ts=new Date().toLocaleTimeString('en-IN',{hour12:false,hour:'2-digit',minute:'2-digit'});
  el.innerHTML=`<div class="msg-hdr"><span>${role}</span><span style="color:var(--dim);font-size:8px">${ts}</span></div>
<div class="body">${esc(text)}${streaming?'<span class="cur"></span>':''}</div>`;
  log.appendChild(el);
  el.scrollIntoView({behavior:'smooth',block:'end'});
  while(log.children.length>200) log.removeChild(log.firstChild);
  curEntry=el; return el;
}
function updateEntry(text) {
  if(!curEntry) return;
  curEntry.querySelector('.body').innerHTML=esc(text)+'<span class="cur"></span>';
  curEntry.scrollIntoView({behavior:'smooth',block:'end'});
}
function finalEntry(text) {
  if(!curEntry) return;
  curEntry.querySelector('.body').innerHTML=esc(text);
  curEntry=null;
}

// ── INPUT ─────────────────────────────────────────────
function setupInput() {
  const inp=$('inp');
  inp.addEventListener('keydown',e=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submitText();} });
  // Also handle quick buttons in menu
  document.querySelectorAll('.qb[data-cmd]').forEach(b=>
    b.addEventListener('click',()=>sendCmd(b.dataset.cmd)));
}
function submitText() {
  const inp=$('inp'), t=inp.value.trim();
  if(!t) return; inp.value=''; sendCmd(t);
}

// ── MENU ──────────────────────────────────────────────
function toggleMenu() {
  const m=$('side-menu'), o=$('menu-overlay');
  const open=m.classList.contains('open');
  m.classList.toggle('open',!open); m.classList.toggle('closed',open);
  o.classList.toggle('show',!open);
}
function closeMenu() {
  $('side-menu').classList.remove('open'); $('side-menu').classList.add('closed');
  $('menu-overlay').classList.remove('show');
}

// ── TOGGLES ───────────────────────────────────────────
function toggleTTS() {
  ttsOn=!ttsOn;
  $('tts-tog').classList.toggle('active',ttsOn);
  if(!ttsOn) stopSpeak();
}
function toggleWake() {
  wakeOn=!wakeOn;
  $('wake-tog').classList.toggle('active',wakeOn);
  if(wakeOn) startWake(); else { try{rec.stop();}catch{} }
}
function clearChat() {
  $('chat-log').innerHTML=''; history=[];
  addMsg('sys','◆','Chat cleared. Ready, Boss.');
  closeMenu();
}
function setGroqKey() {
  const k=prompt('Enter Groq API key (gsk_...):\nGet free key: console.groq.com');
  if(!k||!k.trim()) return;
  localStorage.setItem('groq_key',k.trim());
  mode='direct'; $('backend-info').textContent='⚡ Direct Groq active';
  addMsg('sys','◆','Groq key saved. Direct mode active, Boss.');
  fetchStatus(); closeMenu();
}

// ── CLOCK ─────────────────────────────────────────────
function clockTick() {
  $('hdr-time').textContent=new Date().toLocaleTimeString('en-IN',{hour12:false,hour:'2-digit',minute:'2-digit'});
}
function uptickSession() {
  const m=Math.round((Date.now()-t0)/60000);
  // Could display somewhere if needed
}

// ── UTILS ─────────────────────────────────────────────
const $ = id => document.getElementById(id);
const esc = t => String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
const wait = ms => new Promise(r=>setTimeout(r,ms));

window.addEventListener('load', boot);
if ('speechSynthesis' in window) speechSynthesis.onvoiceschanged = ()=>{};
