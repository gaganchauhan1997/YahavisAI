"""
YAHAVIS — web_main.py
Cloud deployment entry point.
Runs the FastAPI web dashboard + all hackknow/LLM APIs.
No voice, no system-level OS control (cloud-safe).

Start: uvicorn web_main:app --host 0.0.0.0 --port $PORT
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

load_dotenv(dotenv_path=ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [YAHAVIS] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("yahavis.web")

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import time
from typing import Set

# ── Boot subsystems ───────────────────────────────────
log.info("Booting YAHAVIS cloud subsystems...")

from core.brain import YahaviBrain
from core.intent_parser import IntentParser
from memory.long_term import LongTermMemory
from memory.short_term import ShortTermMemory
from skills.hackknow_ops import HackknowOps

brain      = YahaviBrain()
short_mem  = ShortTermMemory(max_turns=20)
long_mem   = LongTermMemory(db_path=ROOT / "memory" / "yahavis_memory.json")
parser     = IntentParser(brain=brain)
hackknow   = HackknowOps()

log.info("All subsystems online.")

# ── FastAPI app ───────────────────────────────────────
app = FastAPI(title="YAHAVIS Cloud", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UI_DIR = ROOT / "ui"
_ws_clients: Set[WebSocket] = set()

# ── Static files ──────────────────────────────────────
@app.get("/style.css")
async def css():
    return FileResponse(UI_DIR / "style.css", media_type="text/css")

@app.get("/app.js")
async def js():
    return FileResponse(UI_DIR / "app.js", media_type="application/javascript")

@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(status_code=204, content={})

# ── Main dashboard ────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(UI_DIR / "index.html")

# ── Health check ──────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "version": os.getenv("YAHAVIS_VERSION", "1.0.0")}

# ── Command endpoint ──────────────────────────────────
class CommandReq(BaseModel):
    text: str

@app.post("/api/command")
async def command(req: CommandReq):
    try:
        intent = await parser.parse(req.text)
        response = await brain.think(req.text)
        # Push to connected WS clients
        await _broadcast({"type": "log", "role": "system", "text": response})
        return {"status": "ok", "response": response, "intent": intent.intent}
    except Exception as e:
        log.error(f"Command error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── Streaming chat (SSE) ──────────────────────────────
@app.get("/api/chat/stream")
async def chat_stream(text: str):
    async def event_gen():
        full = ""
        try:
            async for chunk in brain.router.stream(
                messages=[{"role": "user", "content": text}],
                system=brain.system_prompt,
            ):
                full += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield f"data: {json.dumps({'done': True, 'full': full})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

# ── Status endpoint ───────────────────────────────────
@app.get("/api/status")
async def status():
    api_slots = brain.router.status_report()
    memory    = long_mem.all_facts()
    return {
        "system": {
            "cpu_pct": 0,
            "ram_pct": 0,
            "battery_pct": -1,
            "tasks_done": 0,
            "version": os.getenv("YAHAVIS_VERSION", "1.0.0"),
            "mode": "cloud",
        },
        "api_slots": api_slots,
        "memory": memory,
    }

# ── Hackknow / WooCommerce endpoints ─────────────────
@app.get("/api/orders")
async def get_orders(filter_: str = "today", status: str = "any"):
    orders = await hackknow.get_orders(filter_=filter_, status=status)
    return {"orders": orders, "count": len(orders)}

@app.get("/api/revenue")
async def get_revenue():
    return await hackknow.get_revenue_summary()

@app.get("/api/site-status")
async def site_status():
    return await hackknow.check_site_status()

@app.get("/api/frontend-status")
async def frontend_status():
    return await hackknow.check_frontend_build()

@app.post("/api/product")
async def create_product(data: dict):
    return await hackknow.create_product(data)

@app.post("/api/product/{product_id}")
async def update_product(product_id: int, data: dict):
    return await hackknow.update_product(product_id, data)

# ── Memory endpoints ──────────────────────────────────
@app.get("/api/memory")
async def get_memory():
    return {
        "facts": long_mem.all_facts("facts"),
        "preferences": long_mem.all_facts("preferences"),
        "stats": long_mem.stats(),
    }

@app.post("/api/memory")
async def save_memory(data: dict):
    key   = data.get("key")
    value = data.get("value")
    cat   = data.get("category", "facts")
    if not key:
        return JSONResponse(status_code=400, content={"error": "key required"})
    long_mem.save_fact(key, value, cat)
    return {"saved": True}

# ── WebSocket for real-time push ─────────────────────
@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        while True:
            raw  = await ws.receive_text()
            msg  = json.loads(raw)
            if msg.get("type") == "command":
                asyncio.create_task(_handle_ws_command(ws, msg.get("text", "")))
    except WebSocketDisconnect:
        _ws_clients.discard(ws)

async def _handle_ws_command(ws: WebSocket, text: str):
    try:
        response = await brain.think(text)
        await ws.send_text(json.dumps({"type": "log", "role": "system", "text": response}))
    except Exception as e:
        try:
            await ws.send_text(json.dumps({"type": "error", "text": str(e)}))
        except Exception:
            pass

async def _broadcast(msg: dict):
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)

# ── Entry point ───────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 7070))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
