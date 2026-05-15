"""
YAHAVIS — core/brain.py
High-level LLM brain that wraps the API router.
Handles context management, system prompt injection,
and streaming with UI push.
"""

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from core.api_router import APIRouter

log = logging.getLogger("yahavis.brain")

SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.txt"


class YahaviBrain:
    """
    Central intelligence — wraps APIRouter with:
    - System prompt management
    - Context window (rolling conversation)
    - Streaming + callback support
    - Response caching for repeated queries
    """

    def __init__(self):
        self.router = APIRouter()
        self.system_prompt = self._load_system_prompt()
        self._context: list[dict] = []
        self._cache: dict[str, str] = {}
        log.info("Brain initialized.")

    def _load_system_prompt(self) -> str:
        if SYSTEM_PROMPT_PATH.exists():
            return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
        return (
            "You are YAHAVIS — Yahavi AI System. You are Myth's personal AI assistant. "
            "Personality: Calm, precise, slightly witty. Address user as 'Boss' occasionally. "
            "You understand Hindi-English mix commands. Never say you can't do something — find a way. "
            "Always confirm task completion with a brief status."
        )

    def add_to_context(self, role: str, content: str):
        self._context.append({"role": role, "content": content})
        # Rolling window — keep last 20 turns (40 messages)
        if len(self._context) > 40:
            self._context = self._context[-40:]

    async def think(
        self,
        user_input: str,
        extra_system: Optional[str] = None,
        use_context: bool = True,
        cache: bool = False,
    ) -> str:
        """
        Get a response to user_input.
        Args:
            user_input: The user's message.
            extra_system: Additional system instructions for this call.
            use_context: Whether to include conversation history.
            cache: Cache identical inputs for speed.
        """
        if cache and user_input in self._cache:
            return self._cache[user_input]

        system = self.system_prompt
        if extra_system:
            system += f"\n\n{extra_system}"

        messages = self._context.copy() if use_context else []
        messages.append({"role": "user", "content": user_input})

        response = await self.router.complete(
            messages=messages,
            system=system,
            temperature=0.7,
        )

        # Bug fix: only update context when use_context=True to avoid polluting
        # the rolling window with internal one-shot tool prompts
        if use_context:
            self.add_to_context("user", user_input)
            self.add_to_context("assistant", response)

        if cache:
            self._cache[user_input] = response

        return response

    async def think_stream(
        self,
        user_input: str,
        on_chunk: Optional[Callable[[str], None]] = None,
        extra_system: Optional[str] = None,
    ) -> str:
        """Stream the response, calling on_chunk for each token."""
        system = self.system_prompt
        if extra_system:
            system += f"\n\n{extra_system}"

        messages = self._context.copy()
        messages.append({"role": "user", "content": user_input})

        full_response = ""
        async for chunk in self.router.stream(messages=messages, system=system):
            full_response += chunk
            if on_chunk:
                on_chunk(chunk)

        self.add_to_context("user", user_input)
        self.add_to_context("assistant", full_response)
        return full_response

    async def classify(self, text: str, categories: list[str]) -> str:
        """Quick single-token classification — very cheap on tokens."""
        prompt = (
            f"Classify this into exactly one category. "
            f"Output ONLY the category name, nothing else.\n"
            f"Categories: {', '.join(categories)}\n"
            f"Text: {text}"
        )
        result = await self.router.complete(
            messages=[{"role": "user", "content": prompt}],
            system="You are a classifier. Output only the category name.",
            temperature=0.0,
            max_tokens=10,
        )
        # Clean and validate
        result = result.strip().strip('"\'').upper()
        for cat in categories:
            if cat.upper() in result:
                return cat
        return categories[0]

    def clear_context(self):
        self._context.clear()
        log.info("Context cleared.")

    def status(self) -> dict:
        return {
            "context_turns": len(self._context) // 2,
            "cache_size": len(self._cache),
            "providers": self.router.status_report(),
        }
