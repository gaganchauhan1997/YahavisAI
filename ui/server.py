"""
YAHAVIS — ui/server.py
FastAPI server for the local HUD dashboard.
Serves index.html + provides REST API + WebSocket push.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Set

log = logging.getLogger("yahavis.ui_server")

UI_DIR = Path(__file__).parent


class UIServer:
    """Local HTTP + WebSocket server for the YAHAVIS dashboard."""

    def __init__(self, port: int = 7070, orchestrator=None):
        self.port = port
        self.orchestrator = orchestrator
        self._clients: Set = set()
        self._app = None

    def _build_app(self):
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import HTMLResponse, FileResponse
        from fastapi.staticfiles import StaticFiles
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel

        app = FastAPI(title="YAHAVIS HUD", docs_url=None, redoc_url=None)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        # Serve static UI files
        app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

        class CommandRequest(BaseModel):
            text: str

        @app.get("/", response_class=HTMLResponse)
        async def index():
            return FileResponse(UI_DIR / "index.html")

        @app.get("/style.css")
        async def css():
            return FileResponse(UI_DIR / "style.css",
                                media_type="text/css")

        @app.get("/app.js")
        async def js():
            return FileResponse(UI_DIR / "app.js",
                                media_type="application/javascript")

        @app.post("/api/command")
        async def handle_command(req: CommandRequest):
            if self.orchestrator:
                asyncio.create_task(self.orchestrator.handle(req.text))
            return {"status": "queued", "command": req.text}

        @app.get("/api/status")
        async def status():
            from computer.system_ops import SystemOps
            sys_info = {}
            try:
                ops = SystemOps()
                info = ops.get_system_info()
                sys_info = {
                    "cpu_pct": info.get("cpu_percent", 0),
                    "ram_pct": info.get("ram_used_pct", 0),
                    "battery_pct": info.get("battery", {}).get("percent", -1),
                    "tasks_done": len([
                        t for t in getattr(self.orchestrator, '_history', [])
                        if t.status == "done"
                    ]) if self.orchestrator else 0,
                }
            except Exception:
                pass

            api_slots = {}
            if self.orchestrator and self.orchestrator.brain:
                api_slots = self.orchestrator.brain.router.status_report()

            memory = {}
            if self.orchestrator and self.orchestrator.long_mem:
                memory = self.orchestrator.long_mem.all_facts()

            return {"system": sys_info, "api_slots": api_slots, "memory": memory}

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self._clients.add(websocket)
            log.info("WS client connected")
            try:
                while True:
                    data = await websocket.receive_text()
                    msg = json.loads(data)
                    if msg.get("type") == "command" and self.orchestrator:
                        asyncio.create_task(
                            self.orchestrator.handle(msg.get("text", ""))
                        )
            except WebSocketDisconnect:
                self._clients.discard(websocket)
                log.info("WS client disconnected")

        return app

    async def broadcast(self, message: dict):
        """Push a message to all connected dashboard clients."""
        dead = set()
        for client in self._clients:
            try:
                await client.send_text(json.dumps(message))
            except Exception:
                dead.add(client)
        self._clients -= dead

    async def start(self):
        """Start the uvicorn server."""
        try:
            import uvicorn
            self._app = self._build_app()
            config = uvicorn.Config(
                self._app,
                host="127.0.0.1",
                port=self.port,
                log_level="warning",
                ws_ping_interval=20,
                ws_ping_timeout=20,
            )
            server = uvicorn.Server(config)
            log.info(f"UI server: http://127.0.0.1:{self.port}")

            # Auto-open browser
            try:
                import webbrowser
                await asyncio.sleep(1.5)
                webbrowser.open(f"http://127.0.0.1:{self.port}")
            except Exception:
                pass

            await server.serve()
        except ImportError:
            log.warning("uvicorn not installed — starting fallback http.server")
            await self._fallback_server()

    async def _fallback_server(self):
        """Minimal fallback using http.server."""
        import http.server
        import threading

        os.chdir(str(UI_DIR))
        handler = http.server.SimpleHTTPRequestHandler
        httpd = http.server.HTTPServer(("127.0.0.1", self.port), handler)
        log.info(f"Fallback server: http://127.0.0.1:{self.port}")
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        while True:
            await asyncio.sleep(10)
