#!/bin/bash
# YAHAVIS — One-click Cloudflare Worker deploy
# Run this on your PC: bash deploy.sh
# Requires: Node.js 18+ installed (nodejs.org)

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  YAHAVIS — Cloudflare Deploy Script      ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Install wrangler if not present
if ! command -v wrangler &> /dev/null; then
  echo "[1/5] Installing Wrangler..."
  npm install -g wrangler
else
  echo "[1/5] Wrangler already installed ✓"
fi

# Authenticate — opens browser for one-click login (no token needed!)
echo ""
echo "[2/5] Opening Cloudflare login in your browser..."
echo "      Sign in with the account that has hackknow.com"
echo ""
wrangler login

# Deploy the worker
echo ""
echo "[3/5] Deploying YAHAVIS Worker..."
wrangler deploy

# Set secrets from .env
echo ""
echo "[4/5] Setting API secrets..."

source .env 2>/dev/null || true

[ -n "$GROQ_API_KEY_1" ]     && echo "$GROQ_API_KEY_1"     | wrangler secret put GROQ_API_KEY_1
[ -n "$GEMINI_API_KEY_1" ]   && echo "$GEMINI_API_KEY_1"   | wrangler secret put GEMINI_API_KEY_1
[ -n "$OPENROUTER_API_KEY" ] && echo "$OPENROUTER_API_KEY" | wrangler secret put OPENROUTER_API_KEY
[ -n "$WC_SITE_URL" ]        && echo "$WC_SITE_URL"        | wrangler secret put WC_SITE_URL
[ -n "$WC_CONSUMER_KEY" ] && [[ "$WC_CONSUMER_KEY" != *xxxx* ]] && echo "$WC_CONSUMER_KEY" | wrangler secret put WC_CONSUMER_KEY
[ -n "$WC_CONSUMER_SECRET" ] && [[ "$WC_CONSUMER_SECRET" != *xxxx* ]] && echo "$WC_CONSUMER_SECRET" | wrangler secret put WC_CONSUMER_SECRET

# Set up DNS
echo ""
echo "[5/5] Setting up yahavis.hackknow.com DNS..."
WORKER_URL=$(wrangler deployments list 2>/dev/null | grep "yahavis" | head -1 | awk '{print $NF}')
echo ""
echo "══════════════════════════════════════════════"
echo "✅  YAHAVIS deployed!"
echo ""
echo "    Worker URL  : https://yahavis.workers.dev"
echo "    Custom domain: yahavis.hackknow.com"
echo ""
echo "    To complete custom domain setup:"
echo "    → wrangler routes add 'yahavis.hackknow.com/*' yahavis"
echo "══════════════════════════════════════════════"
