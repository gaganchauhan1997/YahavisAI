"""
YAHAVIS — core/intent_parser.py
Converts raw voice/text into structured intent objects.
Categories: FILE_OP, APP_CONTROL, BROWSER, SYSTEM,
            CONTENT_GEN, HACKKNOW, MEMORY, CHAT, CODE
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("yahavis.intent_parser")

INTENT_CATEGORIES = [
    "FILE_OP",       # Files, folders, search, move, delete
    "APP_CONTROL",   # Open, close, switch apps
    "BROWSER",       # Navigate, search, fill forms
    "SYSTEM",        # Volume, brightness, screenshot, shutdown
    "CONTENT_GEN",   # Write blog, email, social posts, rap verse
    "HACKKNOW",      # WC orders, products, site ops
    "MEMORY",        # Remember, recall, forget
    "CODE",          # Write, debug, explain code
    "CHAT",          # General conversation
]

INTENT_PROMPT = """You are YAHAVIS Intent Parser. Parse the user command into structured JSON.

Output ONLY valid JSON, nothing else:
{
  "intent": "<CATEGORY>",
  "action": "<specific action verb>",
  "target": "<what to act on>",
  "params": {<any relevant parameters>},
  "language": "<en|hi|hinglish>",
  "confidence": <0.0-1.0>,
  "voice_response": "<what YAHAVIS should say back>"
}

CATEGORIES: FILE_OP, APP_CONTROL, BROWSER, SYSTEM, CONTENT_GEN, HACKKNOW, MEMORY, CODE, CHAT

EXAMPLES:
Input: "Hey Yahavi, open VS Code"
Output: {"intent":"APP_CONTROL","action":"open","target":"vs code","params":{"app_name":"code"},"language":"en","confidence":0.98,"voice_response":"Opening VS Code, Boss."}

Input: "Chrome mein hackknow.com khol"
Output: {"intent":"BROWSER","action":"navigate","target":"hackknow.com","params":{"url":"https://hackknow.com","browser":"chrome"},"language":"hinglish","confidence":0.96,"voice_response":"Opening Hackknow in Chrome, Boss."}

Input: "volume 50 percent kar"
Output: {"intent":"SYSTEM","action":"set_volume","target":"volume","params":{"level":50},"language":"hinglish","confidence":0.99,"voice_response":"Setting volume to 50 percent."}

Input: "Downloads mein saari PDFs dhundh"
Output: {"intent":"FILE_OP","action":"search","target":"downloads folder","params":{"folder":"~/Downloads","extension":".pdf"},"language":"hinglish","confidence":0.97,"voice_response":"Searching Downloads folder for PDF files, Boss."}

Input: "Hackknow ke new orders check kar"
Output: {"intent":"HACKKNOW","action":"get_orders","target":"woocommerce","params":{"filter":"today"},"language":"hinglish","confidence":0.98,"voice_response":"Checking today's Hackknow orders, Boss."}

Now parse this command: {USER_INPUT}"""


@dataclass
class ParsedIntent:
    intent: str
    action: str
    target: str
    params: dict = field(default_factory=dict)
    language: str = "en"
    confidence: float = 0.5
    voice_response: str = ""
    raw_input: str = ""

    def is_confident(self, threshold: float = 0.6) -> bool:
        return self.confidence >= threshold

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "action": self.action,
            "target": self.target,
            "params": self.params,
            "language": self.language,
            "confidence": self.confidence,
            "voice_response": self.voice_response,
        }


class IntentParser:
    """
    Parses natural language commands into structured intents.
    Uses LLM for NLU with regex fallbacks for common patterns.
    """

    def __init__(self, brain=None):
        self.brain = brain
        self._regex_rules = self._build_regex_rules()
        log.info("IntentParser ready.")

    def _build_regex_rules(self) -> list[tuple]:
        """Fast regex rules for common commands — no LLM needed."""
        return [
            # System controls
            (r"volume\s+(\d+)", "SYSTEM", "set_volume",
             lambda m: {"level": int(m.group(1))}),
            (r"screenshot\s*(le|lo|lelo|lijiye)?", "SYSTEM", "screenshot",
             lambda m: {}),
            (r"shutdown|band\s*kar|close\s*down", "SYSTEM", "shutdown",
             lambda m: {}),
            (r"(\d+)\s*minute\s*baad\s*shutdown", "SYSTEM", "shutdown",
             lambda m: {"timer": int(m.group(1)) * 60}),
            (r"lock\s*(screen|kar)", "SYSTEM", "lock", lambda m: {}),

            # App control
            (r"open\s+(.+)|(.+)\s+khol", "APP_CONTROL", "open",
             lambda m: {"app_name": (m.group(1) or m.group(2)).strip()}),

            # Browser
            (r"(?:chrome|browser)\s+mein\s+(.+)\s+khol|open\s+(.+)\s+in\s+(?:chrome|browser)",
             "BROWSER", "navigate",
             lambda m: {"url": m.group(1) or m.group(2)}),

            # File ops
            (r"(.+)\s+folder\s+mein\s+(.+)\s+dhundh|search\s+for\s+(.+)\s+in\s+(.+)",
             "FILE_OP", "search",
             lambda m: {"folder": m.group(1), "query": m.group(2)}),

            # Hackknow
            (r"(?:hackknow|wc|woocommerce)\s+(?:ke|ke)?(?:new\s+)?orders?\s+(?:check|dekh)",
             "HACKKNOW", "get_orders",
             lambda m: {"filter": "today"}),
        ]

    async def parse(self, text: str) -> ParsedIntent:
        """
        Parse a raw command string into a structured ParsedIntent.
        Tries regex first (fast), falls back to LLM (accurate).
        """
        text_lower = text.lower().strip()

        # 1. Try fast regex rules
        for pattern, intent, action, params_fn in self._regex_rules:
            m = re.search(pattern, text_lower)
            if m:
                try:
                    params = params_fn(m)
                except Exception:
                    params = {}
                parsed = ParsedIntent(
                    intent=intent,
                    action=action,
                    target=text,
                    params=params,
                    confidence=0.90,
                    voice_response=self._quick_response(action, params),
                    raw_input=text,
                )
                log.debug(f"Regex match: {intent}.{action}")
                return parsed

        # 2. LLM parse
        if self.brain:
            return await self._llm_parse(text)

        # 3. Fallback — treat as chat
        return ParsedIntent(
            intent="CHAT",
            action="converse",
            target=text,
            confidence=0.5,
            voice_response="",
            raw_input=text,
        )

    async def _llm_parse(self, text: str) -> ParsedIntent:
        prompt = INTENT_PROMPT.replace("{USER_INPUT}", text)
        try:
            raw = await self.brain.think(
                user_input=prompt,
                use_context=False,
                extra_system="Output ONLY valid JSON. No explanation.",
            )
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return ParsedIntent(
                    intent=data.get("intent", "CHAT"),
                    action=data.get("action", "converse"),
                    target=data.get("target", text),
                    params=data.get("params", {}),
                    language=data.get("language", "en"),
                    confidence=float(data.get("confidence", 0.7)),
                    voice_response=data.get("voice_response", ""),
                    raw_input=text,
                )
        except Exception as e:
            log.warning(f"LLM parse failed: {e}")

        return ParsedIntent(intent="CHAT", action="converse",
                            target=text, confidence=0.4, raw_input=text)

    def _quick_response(self, action: str, params: dict) -> str:
        responses = {
            "set_volume": f"Setting volume to {params.get('level', '?')} percent.",
            "screenshot": "Taking a screenshot, Boss.",
            "shutdown": "Shutting down" + (
                f" in {params['timer']//60} minutes." if "timer" in params else " now."
            ),
            "open": f"Opening {params.get('app_name', 'that')}, Boss.",
            "navigate": f"Opening {params.get('url', 'that')} in browser.",
            "search": f"Searching {params.get('folder', 'folder')} for files.",
            "get_orders": "Checking Hackknow orders, Boss.",
            "lock": "Locking screen.",
        }
        return responses.get(action, "On it, Boss.")
