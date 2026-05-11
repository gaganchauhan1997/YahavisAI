import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import google.generativeai as genai

from app.core.config import settings
from app.services.memory.conversation_memory import get_conversation_memory

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    RESPOND = "respond"
    ASK_CLARIFICATION = "ask_clarification"
    SEND_WHATSAPP = "send_whatsapp"
    OPEN_BROWSER = "open_browser"
    SEARCH_WEB = "search_web"
    OPEN_APP = "open_app"
    TYPE_KEYBOARD = "type_keyboard"
    PRESS_KEY = "press_key"
    TAKE_SCREENSHOT = "take_screenshot"
    POST_INSTAGRAM = "post_instagram"
    EXECUTE_WORKFLOW = "execute_workflow"
    SCHEDULE_TASK = "schedule_task"


@dataclass
class AIAction:
    action: ActionType
    params: dict[str, Any] = field(default_factory=dict)
    device_target: Optional[str] = None
    requires_confirmation: bool = False
    reason: str = ""


@dataclass
class OrchestratorResponse:
    response_text: str
    actions: list[AIAction]
    confidence: float
    context_used: dict[str, Any] = field(default_factory=dict)
    follow_up_questions: Optional[list[str]] = None


class YahavisOrchestrator:
    def __init__(self) -> None:
        self.memory = get_conversation_memory()
        self.model = None
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                generation_config={
                    "temperature": settings.GEMINI_TEMPERATURE,
                    "max_output_tokens": settings.GEMINI_MAX_TOKENS,
                    "response_mime_type": "application/json",
                },
            )

    async def process_input(
        self,
        user_input: str,
        user_id: str,
        device_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> OrchestratorResponse:
        conversation_id = conversation_id or "default"
        await self.memory.add_message(conversation_id, user_id, "user", user_input)

        if not self.model:
            response = OrchestratorResponse(
                response_text="Gemini API key is not configured. I can connect devices and queue actions after the backend secret is set.",
                actions=[],
                confidence=0.0,
                context_used={"gemini_configured": False},
            )
            await self.memory.add_message(conversation_id, user_id, "assistant", response.response_text)
            return response

        prompt = self._prompt(user_input)
        try:
            result = await self.model.generate_content_async(prompt)
            payload = self._parse_payload(result.text)
            response = self._to_response(payload)
        except Exception:
            logger.exception("Gemini planning failed")
            response = OrchestratorResponse(
                response_text="AI planning failed. Please retry after checking backend logs.",
                actions=[],
                confidence=0.0,
                context_used={"error": "gemini_planning_failed"},
            )

        await self.memory.add_message(conversation_id, user_id, "assistant", response.response_text)
        return response

    def _prompt(self, user_input: str) -> str:
        allowed = ", ".join(action.value for action in ActionType)
        return f"""
You are YahavisAI. Gemini must only understand intent and return structured JSON.
Never execute device actions directly.

Allowed actions: {allowed}

Return exactly:
{{
  "response_text": "short user-facing reply in the user's language",
  "confidence": 0.0,
  "actions": [
    {{
      "action": "send_whatsapp",
      "params": {{}},
      "device_target": "mobile|desktop|browser",
      "requires_confirmation": true,
      "reason": "why this action is needed"
    }}
  ],
  "follow_up_questions": []
}}

Rules:
- Use actions only from the allowed list.
- Destructive, social posting, payment, system-level, and messaging actions require confirmation.
- If required details are missing, use ask_clarification and no executable action.
- Hindi, Hinglish, and English are supported.

User input: {user_input}
"""

    def _parse_payload(self, text: str) -> dict[str, Any]:
        return json.loads(text.strip())

    def _to_response(self, payload: dict[str, Any]) -> OrchestratorResponse:
        actions: list[AIAction] = []
        for item in payload.get("actions", []):
            action_name = item.get("action", "respond")
            try:
                action_type = ActionType(action_name)
            except ValueError:
                action_type = ActionType.ASK_CLARIFICATION
            actions.append(
                AIAction(
                    action=action_type,
                    params=item.get("params") or {},
                    device_target=item.get("device_target"),
                    requires_confirmation=bool(item.get("requires_confirmation", False)),
                    reason=item.get("reason", ""),
                )
            )
        return OrchestratorResponse(
            response_text=str(payload.get("response_text") or "Ready."),
            actions=actions,
            confidence=float(payload.get("confidence") or 0.0),
            context_used={"gemini_configured": True},
            follow_up_questions=payload.get("follow_up_questions") or None,
        )


_orchestrator: Optional[YahavisOrchestrator] = None


def get_orchestrator() -> YahavisOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = YahavisOrchestrator()
    return _orchestrator
