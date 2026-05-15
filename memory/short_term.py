"""
YAHAVIS — memory/short_term.py
Session-scoped rolling conversation context.
Cleared on every restart.
"""

import logging
from collections import deque
from datetime import datetime
from typing import List, Optional

log = logging.getLogger("yahavis.short_term")


class ShortTermMemory:
    """
    Rolling window of recent turns for LLM context injection.
    Automatically trims oldest turns when max is exceeded.
    """

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self._turns: deque = deque(maxlen=max_turns)
        self._session_start = datetime.now()

    def add(self, role: str, content: str, metadata: dict = None):
        """Add a turn to short-term memory."""
        self._turns.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        })

    def add_user(self, content: str):
        self.add("user", content)

    def add_assistant(self, content: str):
        self.add("assistant", content)

    def get_context(self, last_n: int = None) -> List[dict]:
        """Return context in LLM-compatible message format."""
        turns = list(self._turns)
        if last_n:
            turns = turns[-last_n:]
        return [{"role": t["role"], "content": t["content"]} for t in turns]

    def get_recent_summary(self, n: int = 3) -> str:
        """Get a plain-text summary of recent interactions."""
        recent = list(self._turns)[-n*2:]
        lines = []
        for turn in recent:
            prefix = "You" if turn["role"] == "user" else "YAHAVIS"
            lines.append(f"{prefix}: {turn['content'][:100]}")
        return "\n".join(lines)

    def search(self, query: str) -> List[dict]:
        """Find turns containing a keyword."""
        query_lower = query.lower()
        return [t for t in self._turns if query_lower in t["content"].lower()]

    def clear(self):
        self._turns.clear()
        log.info("Short-term memory cleared.")

    def __len__(self):
        return len(self._turns)

    @property
    def session_duration(self) -> str:
        delta = datetime.now() - self._session_start
        mins = int(delta.total_seconds() // 60)
        return f"{mins}m"

    def stats(self) -> dict:
        return {
            "turns": len(self._turns),
            "max_turns": self.max_turns,
            "session_duration": self.session_duration,
        }
