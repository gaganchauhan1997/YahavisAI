from datetime import datetime, timezone
from typing import Any


class ConversationMemory:
    def __init__(self) -> None:
        self._messages: dict[str, list[dict[str, Any]]] = {}

    async def add_message(self, conversation_id: str, user_id: str, role: str, content: str) -> None:
        self._messages.setdefault(conversation_id, []).append(
            {
                "user_id": user_id,
                "role": role,
                "content": content,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def get_context(self, conversation_id: str, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        messages = self._messages.get(conversation_id, [])
        return [msg for msg in messages if msg["user_id"] == user_id][-limit:]

    async def clear_conversation(self, conversation_id: str) -> None:
        self._messages.pop(conversation_id, None)


_memory = ConversationMemory()


def get_conversation_memory() -> ConversationMemory:
    return _memory
