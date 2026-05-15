/**
 * YAHAVIS Cloudflare Worker v2.0 — Jarvis Mode
 * LLM: Groq LLaMA-3.3-70B → Gemini Flash → OpenRouter
 * Features: Streaming SSE, conversation history, WooCommerce, rate limiting
 */

const SYSTEM_PROMPT = `You are YAHAVIS — Yahavi AI System, a highly advanced AI assistant built by Myth for Hackknow.
Personality: Like J.A.R.V.I.S. from Iron Man — composed, witty, precise, dry humor. Never robotic or generic.
Address the user as "Boss" or "Sir" alternating naturally. First message always "At your service, Boss."
You understand Hindi-English mix (Hinglish) perfectly. Always reply in the same language the user uses.
You manage Hackknow's systems: shop.hackknow.com (WooCommerce), analytics, orders, revenue.
Be concise. No unnecessary bullet points. Confirm task done with a brief status. Never refuse — find alternatives.`;

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });
    const p = url.pathname;
    if (p === '/')                return serveHTML(env);
    if (p === '/style.css')       return serveFile('style.css', 'text/css', env);
    if (p === '/app.js')          return serveFile('app.js', 'application/javascript', env);
    if (p === '/favicon.ico')     return new Response('', { status: 204 });
    if (p === '/health')          return json({ status: 'ok', version: '2.0.0', mode: 'cloudflare-worker' });
    if (p === '/api/chat')        return handleChat(request, env);
    if (p === '/api/command')     return handleChat(request, env);
    if (p === '/api/chat/stream') return handleStream(request, url, env);
    if (p === '/api/status')      return handleStatus(env);
    if (p === '/api/orders')      return handleOrders(url, env);
    if (p === '/api/revenue')     return handleRevenue(env);
    if (p === '/api/site-status') return handleSiteStatus(env);
    if (p === '/api/memory')      return handleMemory(request, env);
    if (p === '/api/tts')         return handleTTS(request, env);
    return new Response('Not Found', { status: 404, headers: CORS });
  }
};

async function serveHTML(env) {
  const html = env.STATIC_KV ? await env.STATIC_KV.get('index.html') : null;
  return new Response(html || fallbackHTML(), { headers: { ...CORS, 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-cache' } });
}
async function serveFile(name, mime, env) {
  const content = env.STATIC_KV ? await env.STATIC_KV.get(name) : null;
  if (!content) return new Response('', { status: 204 });
  return new Response(content, { headers: { ...CORS, 'Content-Type': mime, 'Cache-Control': 'no-cache' } });
}

async function handleChat(request, env) {
  if (request.method !== 'POST') return json({ error: 'POST required' }, 405);
  const body = await request.json().catch(() => ({}));
  const text = body.text || body.message || '';
  const history = body.history || [];
  if (!text) return json({ error: 'text required' }, 400);
  if (env.RATE_KV) {
    const key = `rl:${getIP(request)}`;
    const count = parseInt(await env.RATE_KV.get(key) || '0');
    if (count > 200) return json({ error: 'Rate limit reached. Try again tomorrow, Boss.' }, 429);
    await env.RATE_KV.put(key, String(count + 1), { expirationTtl: 86400 });
  }
  try {
    const response = await callLLM(text, history, env);
    return json({ status: 'ok', response });
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
}

async function handleStream(request, url, env) {
  let text = url.searchParams.get('text') || '';
  let history = [];
  if (request.method === 'POST') {
    const body = await request.json().catch(() => ({}));
    text = body.text || body.message || text;
    history = body.history || [];
  }
  if (!text) return json({ error: 'text required' }, 400);

  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();
  const enc = new TextEncoder();
  const write = (d) => writer.write(enc.encode(`data: ${JSON.stringify(d)}\n\n`));

  (async () => {
    try {
      const msgs = buildMessages(text, history);
      const groqKey = env.GROQ_API_KEY_1;
      if (!groqKey) {
        const r = await callLLM(text, history, env);
        await write({ chunk: r });
        await write({ done: true });
        return;
      }
      const resp = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${groqKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'llama-3.3-70b-versatile', messages: msgs, stream: true, max_tokens: 1024, temperature: 0.7 }),
      });
      if (!resp.ok) {
        const r = await callLLM(text, history, env);
        await write({ chunk: r }); await write({ done: true }); return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n'); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const d = line.slice(6).trim();
          if (d === '[DONE]') continue;
          try { const chunk = JSON.parse(d)?.choices?.[0]?.delta?.content || ''; if (chunk) await write({ chunk }); } catch {}
        }
      }
      await write({ done: true });
    } catch (e) {
      await write({ error: String(e) });
    } finally {
      await writer.close();
    }
  })();

  return new Response(readable, { headers: { ...CORS, 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no' } });
}

async function callLLM(text, history, env) {
  const msgs = buildMessages(text, history);
  if (env.GROQ_API_KEY_1) { try { return await callGroq(msgs, env.GROQ_API_KEY_1); } catch {} }
  if (env.GEMINI_API_KEY_1) { try { return await callGemini(text, env.GEMINI_API_KEY_1); } catch {} }
  if (env.OPENROUTER_API_KEY) { try { return await callOpenRouter(msgs, env.OPENROUTER_API_KEY); } catch {} }
  throw new Error('All LLM providers exhausted. Please check API keys, Boss.');
}

function buildMessages(text, history) {
  const msgs = [{ role: 'system', content: SYSTEM_PROMPT }];
  for (const h of (history || [])) { if (h.role && h.content) msgs.push({ role: h.role, content: h.content }); }
  msgs.push({ role: 'user', content: text });
  return msgs;
}

async function callGroq(msgs, key) {
  const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST', headers: { 'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: 'llama-3.3-70b-versatile', messages: msgs, max_tokens: 1024, temperature: 0.7 }),
  });
  if (!r.ok) throw new Error(`Groq ${r.status}`);
  return (await r.json()).choices[0].message.content;
}

async function callGemini(text, key) {
  const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${key}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contents: [{ parts: [{ text }] }], systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] }, generationConfig: { temperature: 0.7, maxOutputTokens: 1024 } }),
  });
  if (!r.ok) throw new Error(`Gemini ${r.status}`);
  return (await r.json()).candidates[0].content.parts[0].text;
}

async function callOpenRouter(msgs, key) {
  const r = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json', 'HTTP-Referer': 'https://yahavis.hackknow.com' },
    body: JSON.stringify({ model: 'mistralai/mistral-7b-instruct:free', messages: msgs }),
  });
  if (!r.ok) throw new Error(`OpenRouter ${r.status}`);
  return (await r.json()).choices[0].message.content;
}

async function handleOrders(url, env) {
  const wcUrl = env.WC_SITE_URL || 'https://shop.hackknow.com';
  const wcKey = env.WC_CONSUMER_KEY || '';
  const wcSecret = env.WC_CONSUMER_SECRET || '';
  if (!wcKey || wcKey.includes('xxxx')) return json({ orders: [], count: 0, note: 'WC not configured' });
  const filter = url.searchParams.get('filter') || 'today';
  const params = new URLSearchParams({ per_page: '20' });
  if (filter === 'today') { const t = new Date(); t.setUTCHours(0,0,0,0); params.set('after', t.toISOString()); }
  const r = await fetch(`${wcUrl}/wp-json/wc/v3/orders?${params}`, { headers: { 'Authorization': `Basic ${btoa(`${wcKey}:${wcSecret}`)}` } });
  if (!r.ok) return json({ error: `WC ${r.status}` }, r.status);
  const orders = await r.json();
  return json({ orders, count: orders.length });
}

async function handleRevenue(env) {
  const result = await handleOrders(new URL('https://x/?filter=today'), env);
  const { orders = [] } = await result.clone().json();
  const total = orders.reduce((s, o) => s + parseFloat(o.total || 0), 0);
  return json({ orders_today: orders.length, revenue_today: Math.round(total * 100) / 100, currency: orders[0]?.currency || 'INR' });
}

async function handleSiteStatus(env) {
  const target = env.WC_SITE_URL || 'https://shop.hackknow.com';
  const start = Date.now();
  try {
    const r = await fetch(target, { method: 'HEAD' });
    return json({ url: target, status: r.status, ok: r.status < 400, latency_ms: Date.now() - start });
  } catch (e) {
    return json({ url: target, status: -1, ok: false, error: String(e) });
  }
}

async function handleStatus(env) {
  return json({
    system: { version: '2.0.0', mode: 'cloudflare-worker' },
    api_slots: {
      'Groq · LLaMA 3.3-70B': { healthy: !!env.GROQ_API_KEY_1, status: env.GROQ_API_KEY_1 ? 'active' : 'inactive', usage_pct: 0 },
      'Gemini · Flash 1.5':   { healthy: !!env.GEMINI_API_KEY_1, status: env.GEMINI_API_KEY_1 ? 'active' : 'inactive', usage_pct: 0 },
      'OpenRouter · Free':     { healthy: !!env.OPENROUTER_API_KEY, status: env.OPENROUTER_API_KEY ? 'active' : 'inactive', usage_pct: 0 },
    },
  });
}

async function handleMemory(request, env) {
  if (!env.RATE_KV) return json({ note: 'KV not bound' });
  if (request.method === 'POST') {
    const { key, value } = await request.json().catch(() => ({}));
    if (key) await env.RATE_KV.put(`mem:${key}`, JSON.stringify(value), { expirationTtl: 86400 * 365 });
    return json({ saved: true });
  }
  return json({ memory: {} });
}


// ── ElevenLabs TTS (cloned voice) ────────────────────
async function handleTTS(request, env) {
  if (request.method !== 'POST') return json({ error: 'POST required' }, 405);
  const { text } = await request.json().catch(() => ({}));
  if (!text) return json({ error: 'text required' }, 400);

  const xiKey     = env.ELEVENLABS_API_KEY;
  const voiceId   = env.ELEVENLABS_VOICE_ID;

  // Fallback: no ElevenLabs key → tell frontend to use browser TTS
  if (!xiKey || !voiceId) {
    return json({ fallback: true, reason: 'ElevenLabs not configured' });
  }

  const clean = text.replace(/[*#`_~\[\]>]/g, '').replace(/\n+/g, ' ').slice(0, 400).trim();

  try {
    const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voiceId}/stream`, {
      method: 'POST',
      headers: {
        'xi-api-key': xiKey,
        'Content-Type': 'application/json',
        'Accept': 'audio/mpeg',
      },
      body: JSON.stringify({
        text: clean,
        model_id: 'eleven_multilingual_v2',
        voice_settings: { stability: 0.45, similarity_boost: 0.88, style: 0.3, use_speaker_boost: true },
      }),
    });

    if (!r.ok) {
      const err = await r.text();
      console.error('ElevenLabs TTS error:', r.status, err);
      return json({ fallback: true, reason: `ElevenLabs ${r.status}` });
    }

    return new Response(r.body, {
      headers: {
        ...CORS,
        'Content-Type': 'audio/mpeg',
        'Cache-Control': 'no-cache',
      },
    });
  } catch (e) {
    return json({ fallback: true, reason: String(e) });
  }
}

function json(d, s = 200) { return new Response(JSON.stringify(d), { status: s, headers: { ...CORS, 'Content-Type': 'application/json' } }); }
function getIP(r) { return r.headers.get('CF-Connecting-IP') || r.headers.get('X-Forwarded-For') || 'unknown'; }

function fallbackHTML() {
  return `<!DOCTYPE html><html><head><title>YAHAVIS</title></head>
<body style="background:#0a0a0f;color:#00f0ff;font-family:monospace;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column;gap:16px">
<div style="font-size:3rem;font-weight:700;letter-spacing:.6rem;text-shadow:0 0 30px #00f0ff;animation:p 2s infinite">YAHAVIS</div>
<div style="color:#506070">Online · Uploading interface...</div>
<style>@keyframes p{0%,100%{opacity:1}50%{opacity:.5}}</style>
</body></html>`;
}

// ── ElevenLabs TTS Proxy ─────────────────────────────
// Appended by YAHAVIS deploy — voice clone endpoint
export async function onRequestPost_tts(request, env) {
  // handled below
}
