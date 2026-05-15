/**
 * YAHAVIS Cloudflare Worker
 * Handles: LLM (Groq → Gemini → OpenRouter), WooCommerce proxy, status API
 * Free tier: 100k requests/day — enough for 1000 users
 * Deploy: wrangler deploy
 */

const SYSTEM_PROMPT = `You are YAHAVIS — Yahavi AI System. You are Myth's personal AI assistant.
Personality: Calm, precise, slightly witty. Address user as 'Boss' occasionally.
You understand Hindi-English mix commands. Hackknow is the operator's company (hackknow.com).
Never say you can't do something — find a way. Always confirm task completion with a brief status.`;

const CORS = {
  'Access-Control-Allow-Origin':  '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // CORS preflight
    if (request.method === 'OPTIONS')
      return new Response(null, { status: 204, headers: CORS });

    // Route
    const path = url.pathname;
    if (path === '/')               return serveHTML(env);
    if (path === '/style.css')      return serveFile('style.css', 'text/css', env);
    if (path === '/app.js')         return serveFile('app.js', 'application/javascript', env);
    if (path === '/favicon.ico')    return new Response('', { status: 204 });
    if (path === '/health')         return json({ status: 'ok', version: '1.0.0', mode: 'cloudflare-worker' });
    if (path === '/api/command')    return handleCommand(request, env);
    if (path === '/api/chat/stream')return handleStream(request, url, env);
    if (path === '/api/status')     return handleStatus(env);
    if (path === '/api/orders')     return handleOrders(url, env);
    if (path === '/api/revenue')    return handleRevenue(env);
    if (path === '/api/site-status')return handleSiteStatus(env);
    if (path === '/api/memory')     return handleMemory(request, env);

    return new Response('Not Found', { status: 404, headers: CORS });
  }
};

// ── Static file serving (from KV store) ─────────────
async function serveHTML(env) {
  const html = env.STATIC_KV ? await env.STATIC_KV.get('index.html') : null;
  return new Response(html || defaultHTML(), {
    headers: { ...CORS, 'Content-Type': 'text/html; charset=utf-8',
               'Cache-Control': 'public, max-age=3600' }
  });
}

async function serveFile(name, mime, env) {
  const content = env.STATIC_KV ? await env.STATIC_KV.get(name) : null;
  if (!content) return new Response('', { status: 204 });
  return new Response(content, {
    headers: { ...CORS, 'Content-Type': mime,
               'Cache-Control': 'public, max-age=3600' }
  });
}

// ── LLM Command (non-streaming) ──────────────────────
async function handleCommand(request, env) {
  if (request.method !== 'POST')
    return json({ error: 'POST required' }, 405);

  const { text } = await request.json().catch(() => ({}));
  if (!text) return json({ error: 'text required' }, 400);

  // Rate limiting via KV (optional — skipped if KV not bound)
  if (env.RATE_KV) {
    const key   = `rl:${getIP(request)}`;
    const count = parseInt(await env.RATE_KV.get(key) || '0');
    if (count > 100) return json({ error: 'Rate limit reached. Try again tomorrow.' }, 429);
    await env.RATE_KV.put(key, String(count + 1), { expirationTtl: 86400 });
  }

  try {
    const response = await callLLM(text, env);
    return json({ status: 'ok', response });
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
}

// ── LLM Streaming (SSE) ──────────────────────────────
async function handleStream(request, url, env) {
  const text = url.searchParams.get('text') || '';
  if (!text) return json({ error: 'text required' }, 400);

  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();
  const enc    = new TextEncoder();

  const write = (data) => writer.write(enc.encode(`data: ${JSON.stringify(data)}\n\n`));

  (async () => {
    try {
      const groqKey = env.GROQ_API_KEY_1;
      if (!groqKey) throw new Error('No Groq key configured');

      const resp = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${groqKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'llama3-8b-8192',
          messages: [{ role: 'system', content: SYSTEM_PROMPT }, { role: 'user', content: text }],
          stream: true, max_tokens: 1024,
        }),
      });

      if (!resp.ok) throw new Error(`Groq ${resp.status}`);

      const reader  = resp.body.getReader();
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
          if (d === '[DONE]') continue;
          try {
            const chunk = JSON.parse(d)?.choices?.[0]?.delta?.content || '';
            if (chunk) await write({ chunk });
          } catch {}
        }
      }
      await write({ done: true });
    } catch (e) {
      await write({ error: String(e) });
    } finally {
      await writer.close();
    }
  })();

  return new Response(readable, {
    headers: {
      ...CORS,
      'Content-Type':     'text/event-stream',
      'Cache-Control':    'no-cache',
      'X-Accel-Buffering':'no',
    },
  });
}

// ── LLM rotation: Groq → Gemini → OpenRouter ────────
async function callLLM(text, env) {
  const msgs = [{ role: 'system', content: SYSTEM_PROMPT }, { role: 'user', content: text }];

  // 1. Try Groq
  const groqKey = env.GROQ_API_KEY_1 || env.GROQ_API_KEY_2;
  if (groqKey) {
    try {
      return await callGroq(msgs, groqKey);
    } catch (e) {
      console.error('Groq failed:', e);
    }
  }

  // 2. Try Gemini
  const geminiKey = env.GEMINI_API_KEY_1;
  if (geminiKey) {
    try {
      return await callGemini(text, geminiKey);
    } catch (e) {
      console.error('Gemini failed:', e);
    }
  }

  // 3. Try OpenRouter (free models)
  const orKey = env.OPENROUTER_API_KEY;
  if (orKey) {
    try {
      return await callOpenRouter(msgs, orKey);
    } catch (e) {
      console.error('OpenRouter failed:', e);
    }
  }

  throw new Error('All LLM providers exhausted');
}

async function callGroq(msgs, key) {
  const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: 'llama3-8b-8192', messages: msgs, max_tokens: 1024 }),
  });
  if (!r.ok) throw new Error(`Groq ${r.status}: ${await r.text()}`);
  const d = await r.json();
  return d.choices[0].message.content;
}

async function callGemini(text, key) {
  const r = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${key}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{ parts: [{ text }] }],
        systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
      }),
    }
  );
  if (!r.ok) throw new Error(`Gemini ${r.status}`);
  const d = await r.json();
  return d.candidates[0].content.parts[0].text;
}

async function callOpenRouter(msgs, key) {
  const r = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${key}`,
      'Content-Type': 'application/json',
      'HTTP-Referer': 'https://yahavis.hackknow.com',
    },
    body: JSON.stringify({ model: 'mistralai/mistral-7b-instruct:free', messages: msgs }),
  });
  if (!r.ok) throw new Error(`OpenRouter ${r.status}`);
  const d = await r.json();
  return d.choices[0].message.content;
}

// ── WooCommerce proxy ────────────────────────────────
async function handleOrders(url, env) {
  const wcUrl    = env.WC_SITE_URL || 'https://shop.hackknow.com';
  const wcKey    = env.WC_CONSUMER_KEY || '';
  const wcSecret = env.WC_CONSUMER_SECRET || '';
  if (!wcKey) return json({ orders: [], count: 0, note: 'WC credentials not configured' });

  const filter   = url.searchParams.get('filter_') || 'today';
  const params   = new URLSearchParams({ per_page: '20' });
  if (filter === 'today') {
    const today = new Date(); today.setUTCHours(0,0,0,0);
    params.set('after', today.toISOString());
  }

  const auth = btoa(`${wcKey}:${wcSecret}`);
  const r = await fetch(`${wcUrl}/wp-json/wc/v3/orders?${params}`, {
    headers: { 'Authorization': `Basic ${auth}` }
  });
  if (!r.ok) return json({ error: `WC ${r.status}` }, r.status);
  const orders = await r.json();
  return json({ orders, count: orders.length });
}

async function handleRevenue(env) {
  const result = await handleOrders(new URL('https://x/?filter_=today'), env);
  const { orders = [] } = await result.clone().json();
  const total = orders.reduce((s, o) => s + parseFloat(o.total || 0), 0);
  return json({
    orders_today: orders.length,
    revenue_today: Math.round(total * 100) / 100,
    currency: orders[0]?.currency || 'INR',
  });
}

async function handleSiteStatus(env) {
  const target = env.WC_SITE_URL || 'https://shop.hackknow.com';
  const start  = Date.now();
  try {
    const r = await fetch(target, { method: 'HEAD' });
    return json({ url: target, status: r.status, ok: r.status < 400, latency_ms: Date.now() - start });
  } catch (e) {
    return json({ url: target, status: -1, ok: false, error: String(e) });
  }
}

// ── Status / Memory ──────────────────────────────────
async function handleStatus(env) {
  return json({
    system: { cpu_pct: 0, ram_pct: 0, battery_pct: -1, tasks_done: 0,
              version: '1.0.0', mode: 'cloudflare-worker' },
    api_slots: {
      groq_llama3: { healthy: !!env.GROQ_API_KEY_1, usage_pct: 0, status: env.GROQ_API_KEY_1 ? 'active' : 'inactive' },
      gemini_flash: { healthy: !!env.GEMINI_API_KEY_1, usage_pct: 0, status: env.GEMINI_API_KEY_1 ? 'active' : 'inactive' },
      openrouter: { healthy: !!env.OPENROUTER_API_KEY, usage_pct: 0, status: env.OPENROUTER_API_KEY ? 'active' : 'inactive' },
    },
    memory: {},
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

// ── Helpers ──────────────────────────────────────────
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status, headers: { ...CORS, 'Content-Type': 'application/json' }
  });
}

function getIP(request) {
  return request.headers.get('CF-Connecting-IP') ||
         request.headers.get('X-Forwarded-For') || 'unknown';
}

function defaultHTML() {
  return `<!DOCTYPE html><html><head><title>YAHAVIS</title></head>
<body style="background:#0a0a0f;color:#00f0ff;font-family:monospace;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="text-align:center">
  <div style="font-size:2rem;font-weight:700;letter-spacing:.5rem;text-shadow:0 0 20px #00f0ff">YAHAVIS</div>
  <div style="margin-top:1rem;color:#506070;font-size:.8rem">Worker running — static files not yet uploaded to KV</div>
</div>
</body></html>`;
}
