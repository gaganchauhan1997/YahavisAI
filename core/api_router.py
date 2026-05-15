"""
YAHAVIS — core/api_router.py
Multi-provider LLM rotation engine.
Priority: Ollama (local) → Groq → Gemini → OpenRouter
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, AsyncIterator, Optional

log = logging.getLogger("yahavis.api_router")

CONFIG_PATH = Path(__file__).parent.parent / "yahavis.config.json"


@dataclass
class ProviderSlot:
    id: str
    provider: str
    model: str
    priority: int
    daily_limit: Optional[int]
    used: int = 0
    status: str = "active"
    last_error: str = ""
    last_used: float = 0.0
    local_only: bool = False

    @property
    def usage_pct(self) -> float:
        if not self.daily_limit:
            return 0.0
        return (self.used / self.daily_limit) * 100

    @property
    def is_healthy(self) -> bool:
        if self.status != "active":
            return False
        if self.daily_limit and self.usage_pct >= 90:
            return False
        return True


class APIRouter:
    """
    Rotates across providers with health checks and fallback.
    Usage:
        router = APIRouter()
        response = await router.complete(messages=[...])
        # or streaming:
        async for chunk in router.stream(messages=[...]): ...
    """

    def __init__(self):
        self.slots: list[ProviderSlot] = []
        self._load_config()
        self._reset_time = time.time()
        log.info(f"APIRouter ready — {len(self.slots)} providers loaded")

    def _load_config(self):
        try:
            cfg = json.loads(CONFIG_PATH.read_text())
            for p in cfg["llm"]["providers"]:
                self.slots.append(ProviderSlot(
                    id=p["id"],
                    provider=p["provider"],
                    model=p["model"],
                    priority=p["priority"],
                    daily_limit=p.get("dailyLimit"),
                    used=p.get("used", 0),
                    status=p.get("status", "active"),
                    local_only=p.get("localOnly", False),
                ))
        except Exception as e:
            log.warning(f"Config load failed: {e} — using defaults")
            self._load_defaults()

    def _load_defaults(self):
        defaults = [
            ("ollama_mistral", "ollama", "mistral", 1),
            ("groq_llama3_70b", "groq", "llama3-70b-8192", 2),
            ("gemini_flash", "gemini", "gemini-1.5-flash", 3),
        ]
        for id_, prov, model, prio in defaults:
            self.slots.append(ProviderSlot(id=id_, provider=prov,
                                           model=model, priority=prio,
                                           daily_limit=None))

    def _get_active_slot(self) -> Optional[ProviderSlot]:
        healthy = sorted([s for s in self.slots if s.is_healthy],
                         key=lambda s: s.priority)
        return healthy[0] if healthy else None

    async def complete(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        _attempt: int = 0,
    ) -> str:
        """Get a full completion from the best available provider."""
        # Bug fix: cap retries to number of slots to avoid infinite recursion
        if _attempt > len(self.slots):
            raise RuntimeError("All API providers exhausted.")
        slot = self._get_active_slot()
        if not slot:
            raise RuntimeError("All API providers exhausted.")
        try:
            result = await self._call(slot, messages, system,
                                      temperature, max_tokens, stream=False)
            slot.used += 1
            slot.last_used = time.time()
            return result
        except Exception as e:
            log.warning(f"[{slot.id}] Error: {e} — marking degraded, retrying")
            slot.status = "degraded"
            slot.last_error = str(e)
            return await self.complete(messages, system, temperature, max_tokens,
                                       _attempt=_attempt + 1)

    async def stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Stream completion tokens from the best available provider."""
        slot = self._get_active_slot()
        if not slot:
            raise RuntimeError("All API providers exhausted.")
        try:
            async for chunk in self._call_stream(slot, messages, system,
                                                 temperature, max_tokens):
                yield chunk
            slot.used += 1
        except Exception as e:
            log.warning(f"[{slot.id}] Stream error: {e}")
            slot.status = "degraded"

    async def _call(self, slot: ProviderSlot, messages, system,
                    temperature, max_tokens, stream=False) -> str:
        if slot.provider == "ollama":
            return await self._call_ollama(slot, messages, system, temperature)
        elif slot.provider == "groq":
            return await self._call_groq(slot, messages, system,
                                         temperature, max_tokens)
        elif slot.provider == "gemini":
            return await self._call_gemini(slot, messages, system,
                                           temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {slot.provider}")

    async def _call_stream(self, slot, messages, system,
                           temperature, max_tokens) -> AsyncGenerator[str, None]:
        if slot.provider == "ollama":
            async for chunk in self._stream_ollama(slot, messages, system,
                                                   temperature):
                yield chunk
        elif slot.provider == "groq":
            async for chunk in self._stream_groq(slot, messages, system,
                                                 temperature, max_tokens):
                yield chunk
        else:
            # Non-streaming fallback
            result = await self._call(slot, messages, system, temperature,
                                      max_tokens)
            yield result

    # ── Ollama ────────────────────────────────────────
    async def _call_ollama(self, slot, messages, system, temperature) -> str:
        import aiohttp
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        payload = {
            "model": slot.model,
            "messages": self._build_messages(messages, system),
            "stream": False,
            "options": {"temperature": temperature},
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.post(f"{base_url}/api/chat",
                                 json=payload, timeout=aiohttp.ClientTimeout(total=60)) as r:
                r.raise_for_status()
                data = await r.json()
                # Bug fix: guard against Ollama returning an error body
                msg = data.get("message")
                if not msg or "content" not in msg:
                    raise RuntimeError(f"Ollama unexpected response: {data}")
                return msg["content"]

    async def _stream_ollama(self, slot, messages, system,
                             temperature) -> AsyncIterator[str]:
        import aiohttp
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        payload = {
            "model": slot.model,
            "messages": self._build_messages(messages, system),
            "stream": True,
            "options": {"temperature": temperature},
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.post(f"{base_url}/api/chat", json=payload) as r:
                async for line in r.content:
                    # Bug fix: skip blank/keep-alive lines to avoid JSONDecodeError
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if chunk := data.get("message", {}).get("content", ""):
                        yield chunk

    # ── Groq ─────────────────────────────────────────
    async def _call_groq(self, slot, messages, system,
                         temperature, max_tokens) -> str:
        from groq import AsyncGroq
        key = self._get_key("GROQ_API_KEY")
        client = AsyncGroq(api_key=key)
        resp = await client.chat.completions.create(
            model=slot.model,
            messages=self._build_messages(messages, system),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    async def _stream_groq(self, slot, messages, system,
                           temperature, max_tokens) -> AsyncIterator[str]:
        from groq import AsyncGroq
        key = self._get_key("GROQ_API_KEY")
        client = AsyncGroq(api_key=key)
        async with client.chat.completions.stream(
            model=slot.model,
            messages=self._build_messages(messages, system),
            temperature=temperature,
            max_tokens=max_tokens,
        ) as stream:
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

    # ── Gemini ────────────────────────────────────────
    async def _call_gemini(self, slot, messages, system,
                           temperature, max_tokens) -> str:
        import google.generativeai as genai
        key = self._get_key("GEMINI_API_KEY")
        genai.configure(api_key=key)
        model = genai.GenerativeModel(
            slot.model,
            system_instruction=system or "",
        )
        history = [
            {"role": m["role"] if m["role"] != "system" else "user",
             "parts": [m["content"]]}
            for m in messages
        ]
        resp = await asyncio.to_thread(model.generate_content, history)
        return resp.text

    # ── Helpers ───────────────────────────────────────
    def _build_messages(self, messages, system):
        built = []
        if system:
            built.append({"role": "system", "content": system})
        built.extend(messages)
        return built

    def _get_key(self, prefix: str) -> str:
        for i in range(1, 6):
            key = os.getenv(f"{prefix}_{i}")
            if key:
                return key
        raise ValueError(f"No {prefix}_* found in environment")

    def status_report(self) -> dict:
        return {
            s.id: {
                "status": s.status,
                "used": s.used,
                "limit": s.daily_limit,
                "usage_pct": round(s.usage_pct, 1),
                "healthy": s.is_healthy,
            }
            for s in self.slots
        }

    def reset_daily_counts(self):
        for s in self.slots:
            s.used = 0
            if s.status == "degraded":
                s.status = "active"
        log.info("Daily API usage counts reset.")
