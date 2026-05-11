"""
YahavisAI - AI Orchestration Layer
The brain of the system: understands intent, reasons, plans, and returns structured actions
NEVER directly executes - only returns JSON action plans
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import google.generativeai as genai

from app.core.config import settings
from app.services.memory.conversation_memory import ConversationMemory
from app.services.memory.long_term_memory import LongTermMemory

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Valid action types that execution layer can perform"""
    # Communication
    SEND_WHATSAPP = "send_whatsapp"
    SEND_EMAIL = "send_email"
    SEND_SMS = "send_sms"
    MAKE_CALL = "make_call"
    
    # Browser
    OPEN_BROWSER = "open_browser"
    NAVIGATE_URL = "navigate_url"
    SEARCH_WEB = "search_web"
    SCROLL_PAGE = "scroll_page"
    CLICK_ELEMENT = "click_element"
    TYPE_TEXT = "type_text"
    TAKE_SCREENSHOT = "take_screenshot"
    
    # Instagram
    POST_INSTAGRAM = "post_instagram"
    STORY_INSTAGRAM = "story_instagram"
    DM_INSTAGRAM = "dm_instagram"
    LIKE_POST = "like_post"
    COMMENT_POST = "comment_post"
    
    # Desktop
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    TYPE_KEYBOARD = "type_keyboard"
    PRESS_KEY = "press_key"
    MOUSE_CLICK = "mouse_click"
    MOUSE_MOVE = "mouse_move"
    COPY_TEXT = "copy_text"
    PASTE_TEXT = "paste_text"
    
    # File System
    CREATE_FILE = "create_file"
    READ_FILE = "read_file"
    DELETE_FILE = "delete_file"
    MOVE_FILE = "move_file"
    CREATE_FOLDER = "create_folder"
    LIST_FILES = "list_files"
    
    # System
    SHUTDOWN = "shutdown"
    RESTART = "restart"
    SLEEP = "sleep"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    MUTE = "mute"
    BRIGHTNESS_UP = "brightness_up"
    BRIGHTNESS_DOWN = "brightness_down"
    
    # Workflow
    EXECUTE_WORKFLOW = "execute_workflow"
    SCHEDULE_TASK = "schedule_task"
    CANCEL_TASK = "cancel_task"
    
    # AI
    GENERATE_TEXT = "generate_text"
    GENERATE_IMAGE = "generate_image"
    TRANSLATE = "translate"
    SUMMARIZE = "summarize"
    
    # Information
    GET_WEATHER = "get_weather"
    GET_NEWS = "get_news"
    GET_TIME = "get_time"
    SET_REMINDER = "set_reminder"
    GET_CALENDAR = "get_calendar"
    
    # Response only (no execution needed)
    RESPOND = "respond"
    ASK_CLARIFICATION = "ask_clarification"


@dataclass
class AIAction:
    """Structured action for execution layer"""
    action: ActionType
    params: Dict[str, Any]
    device_target: Optional[str] = None  # "desktop", "mobile", "browser"
    requires_confirmation: bool = False
    reason: str = ""


@dataclass
class OrchestratorResponse:
    """Complete response from AI orchestrator"""
    response_text: str  # Natural language response to user
    actions: List[AIAction]  # List of actions to execute
    confidence: float
    context_used: Dict[str, Any]
    follow_up_questions: Optional[List[str]] = None


class YahavisOrchestrator:
    """
    Main AI Orchestrator class
    Processes user input through Gemini and returns structured action plans
    """
    
    def __init__(self):
        self.memory = ConversationMemory()
        self.long_term_memory = LongTermMemory()
        self._init_gemini()
        
    def _init_gemini(self):
        """Initialize Gemini AI client"""
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Main orchestration model
        self.orchestrator_model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config={
                "temperature": settings.GEMINI_TEMPERATURE,
                "max_output_tokens": settings.GEMINI_MAX_TOKENS,
                "response_mime_type": "application/json"
            },
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
            ]
        )
        
        # Response generation model (for natural language)
        self.response_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.8,
                "max_output_tokens": 2048
            }
        )
    
    def _get_system_prompt(self) -> str:
        """
        System prompt that defines YahavisAI's behavior
        CRITICAL: Gemini NEVER executes - only plans and returns JSON
        """
        return """You are YahavisAI, an advanced AI Operating System assistant.

## YOUR ROLE
1. UNDERSTAND user intent from their message (Hindi or English)
2. REASON about what needs to be done
3. PLAN the sequence of actions
4. RETURN structured JSON - NEVER execute directly

## CRITICAL RULES
1. ⚠️ NEVER execute actions yourself - only return JSON action plans
2. ⚠️ Safety first: flag destructive actions with requires_confirmation=true
3. ⚠️ If intent is unclear, ask for clarification
4. ⚠️ Respect user preferences from memory
5. ✅ Always respond in user's language (Hindi/English mix is fine)

## ACTION TYPES AVAILABLE

### Communication
- send_whatsapp: {contact: str, message: str}
- send_email: {to: str, subject: str, body: str}
- send_sms: {phone: str, message: str}
- make_call: {contact: str}

### Browser
- open_browser: {url: str, browser: str}
- navigate_url: {url: str}
- search_web: {query: str, engine: str}
- scroll_page: {direction: str, amount: int}
- click_element: {selector: str, description: str}
- type_text: {text: str, selector: str}
- take_screenshot: {save_path: str}

### Instagram
- post_instagram: {image_path: str, caption: str}
- story_instagram: {image_path: str}
- dm_instagram: {username: str, message: str}
- like_post: {post_url: str}
- comment_post: {post_url: str, comment: str}

### Desktop
- open_app: {app_name: str}
- close_app: {app_name: str}
- type_keyboard: {text: str}
- press_key: {key: str, modifiers: list}
- mouse_click: {x: int, y: int, button: str}
- copy_text: {text: str}
- paste_text: {}

### File System
- create_file: {path: str, content: str}
- read_file: {path: str}
- delete_file: {path: str}
- move_file: {source: str, destination: str}
- create_folder: {path: str}
- list_files: {path: str}

### System
- shutdown: {delay: int}
- restart: {}
- sleep: {duration: int}
- volume_up: {amount: int}
- volume_down: {amount: int}
- mute: {}

### AI Features
- generate_text: {prompt: str, style: str}
- generate_image: {prompt: str, size: str}
- translate: {text: str, target_language: str}
- summarize: {text: str, length: str}

### Workflow
- execute_workflow: {workflow_id: str, inputs: dict}
- schedule_task: {task: str, datetime: str, recurrence: str}
- set_reminder: {message: str, datetime: str}

### Information
- get_weather: {location: str, days: int}
- get_news: {topic: str, count: int}
- get_time: {timezone: str}
- get_calendar: {date: str}

### Response Only
- respond: {message: str}
- ask_clarification: {question: str}

## OUTPUT FORMAT
```json
{
  "response_text": "Natural language response to user",
  "confidence": 0.95,
  "actions": [
    {
      "action": "action_name",
      "params": {...},
      "device_target": "desktop|mobile|browser",
      "requires_confirmation": false,
      "reason": "Why this action"
    }
  ],
  "follow_up_questions": ["optional question if clarification needed"]
}
```

## EXAMPLES

### Example 1: Simple WhatsApp
User: "Rahul ko message bhejo ke meeting 3 baje hai"
Output:
{
  "response_text": "Main Rahul ko message bhej raha hoon ki meeting 3 baje hai.",
  "confidence": 0.95,
  "actions": [
    {
      "action": "send_whatsapp",
      "params": {"contact": "Rahul", "message": "Meeting 3 baje hai"},
      "device_target": "mobile",
      "requires_confirmation": false,
      "reason": "User requested to send WhatsApp message"
    }
  ]
}

### Example 2: Instagram Post with AI Caption
User: "Post my photo on Instagram with a creative caption"
Output:
{
  "response_text": "Main aapki photo Instagram par AI-generated caption ke saath post kar raha hoon.",
  "confidence": 0.88,
  "actions": [
    {
      "action": "generate_text",
      "params": {"prompt": "Creative Instagram caption for a photo", "style": "casual, engaging"},
      "device_target": "cloud",
      "requires_confirmation": false
    },
    {
      "action": "post_instagram",
      "params": {"image_path": "last_photo", "caption": "{{generated_text}}"},
      "device_target": "mobile",
      "requires_confirmation": true,
      "reason": "Posting to social media requires confirmation"
    }
  ]
}

### Example 3: Multi-step Desktop Task
User: "Open Chrome and search for Python tutorials"
Output:
{
  "response_text": "Main Chrome open karke Python tutorials search kar raha hoon.",
  "confidence": 0.92,
  "actions": [
    {
      "action": "open_app",
      "params": {"app_name": "chrome"},
      "device_target": "desktop",
      "requires_confirmation": false
    },
    {
      "action": "search_web",
      "params": {"query": "Python tutorials for beginners", "engine": "google"},
      "device_target": "browser",
      "requires_confirmation": false
    }
  ]
}

### Example 4: Unclear Intent
User: "Kuch karo"
Output:
{
  "response_text": "Main samajh nahi paya. Aap kya karwana chahte hain?",
  "confidence": 0.3,
  "actions": [
    {
      "action": "ask_clarification",
      "params": {"question": "Kya karwana hai aapko? WhatsApp, Instagram, ya koi aur kaam?"},
      "device_target": null,
      "requires_confirmation": false
    }
  ],
  "follow_up_questions": ["WhatsApp message bhejna hai?", "Instagram post karna hai?", "Koi app open karna hai?"]
}

### Example 5: Hindi Mixed Command
User: "Bhai file copy karo Documents se Desktop pe"
Output:
{
  "response_text": "Main file copy kar raha hoon Documents se Desktop pe.",
  "confidence": 0.90,
  "actions": [
    {
      "action": "move_file",
      "params": {"source": "Documents", "destination": "Desktop"},
      "device_target": "desktop",
      "requires_confirmation": false,
      "reason": "User requested file copy operation"
    }
  ]
}

## SAFETY RULES
1. Shutdown/restart/delete: requires_confirmation = true
2. Financial actions: requires_confirmation = true
3. Social media posts: requires_confirmation = true
4. Bulk operations: requires_confirmation = true
5. System-level changes: requires_confirmation = true

## MEMORY USAGE
Use context from conversation to:
- Resolve "us", "him", "woh" references
- Remember user preferences
- Follow ongoing task context
- Use previously shared information

Process the user's input and return ONLY the JSON output."""
    
    async def process_input(
        self,
        user_input: str,
        user_id: str,
        device_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> OrchestratorResponse:
        """
        Main entry point: Process user input and return orchestrated response
        
        Args:
            user_input: Raw user message (Hindi or English)
            user_id: Unique user identifier
            device_id: Device that sent the message
            conversation_id: Conversation thread ID
            
        Returns:
            OrchestratorResponse with actions and natural language response
        """
        try:
            logger.info(f"Processing input from user {user_id}: {user_input}")
            
            # 1. Retrieve conversation context
            context = await self.memory.get_context(
                conversation_id=conversation_id,
                user_id=user_id,
                limit=10
            )
            
            # 2. Retrieve user preferences from long-term memory
            preferences = await self.long_term_memory.get_preferences(user_id)
            
            # 3. Build enriched prompt
            enriched_prompt = self._build_prompt(
                user_input=user_input,
                context=context,
                preferences=preferences,
                device_id=device_id
            )
            
            # 4. Call Gemini for orchestration
            response = await self._call_gemini(enriched_prompt)
            
            # 5. Parse and validate response
            parsed = self._parse_response(response.text)
            
            # 6. Store in memory
            await self.memory.add_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=user_input
            )
            
            await self.memory.add_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=parsed["response_text"],
                metadata={"actions": parsed["actions"]}
            )
            
            # 7. Build final response
            actions = [AIAction(**action) for action in parsed["actions"]]
            
            return OrchestratorResponse(
                response_text=parsed["response_text"],
                actions=actions,
                confidence=parsed.get("confidence", 0.5),
                context_used={"conversation_length": len(context), "preferences": preferences},
                follow_up_questions=parsed.get("follow_up_questions")
            )
            
        except Exception as e:
            logger.error(f"Orchestration error: {e}", exc_info=True)
            return OrchestratorResponse(
                response_text="Maaf kijiye, main samajh nahi paya. Kya aap dobara bol sakte hain?",
                actions=[AIAction(
                    action=ActionType.RESPOND,
                    params={"message": "Error occurred"},
                    reason="Failed to process input"
                )],
                confidence=0.0,
                context_used={}
            )
    
    def _build_prompt(
        self,
        user_input: str,
        context: List[Dict],
        preferences: Dict,
        device_id: Optional[str]
    ) -> str:
        """Build enriched prompt with context"""
        
        # Format conversation history
        history_text = ""
        if context:
            history_text = "\nRecent conversation:\n"
            for msg in context[-5:]:  # Last 5 messages
                role = "User" if msg["role"] == "user" else "Jarvis"
                history_text += f"{role}: {msg['content']}\n"
        
        # Format preferences
        prefs_text = ""
        if preferences:
            prefs_text = f"\nUser preferences: {json.dumps(preferences, indent=2)}\n"
        
        # Device context
        device_text = f"\nCurrent device: {device_id or 'unknown'}\n"
        
        return f"""{self._get_system_prompt()}

{history_text}
{prefs_text}
{device_text}

CURRENT USER INPUT:
"{user_input}"

Process this input and return the JSON response."""
    
    async def _call_gemini(self, prompt: str) -> Any:
        """Call Gemini API with retry logic"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                response = self.orchestrator_model.generate_content(prompt)
                return response
            except Exception as e:
                logger.warning(f"Gemini API attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
        
        raise Exception("Failed to get response from Gemini after all retries")
    
    def _parse_response(self, response_text: str) -> Dict:
        """Parse and validate Gemini response"""
        try:
            # Extract JSON from response (handle markdown code blocks)
            text = response_text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            parsed = json.loads(text)
            
            # Validate required fields
            if "response_text" not in parsed:
                parsed["response_text"] = "Main yeh kaam kar raha hoon."
            
            if "actions" not in parsed:
                parsed["actions"] = []
            
            # Validate actions
            valid_actions = []
            for action in parsed["actions"]:
                try:
                    # Ensure action type is valid
                    action_type = ActionType(action["action"])
                    valid_actions.append(action)
                except ValueError:
                    logger.warning(f"Invalid action type: {action.get('action')}")
                    continue
            
            parsed["actions"] = valid_actions
            
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            # Fallback: treat as text response
            return {
                "response_text": response_text,
                "confidence": 0.5,
                "actions": [{
                    "action": "respond",
                    "params": {"message": response_text},
                    "device_target": None,
                    "requires_confirmation": False,
                    "reason": "Fallback text response"
                }]
            }
    
    async def generate_follow_up_response(
        self,
        action_results: List[Dict],
        original_response: str
    ) -> str:
        """
        Generate natural language response after actions are executed
        
        Args:
            action_results: Results from executed actions
            original_response: Original AI response before execution
            
        Returns:
            Updated natural language response
        """
        # Build result summary
        result_summary = "\n".join([
            f"- {r.get('action', 'unknown')}: {'success' if r.get('success') else 'failed'}"
            for r in action_results
        ])
        
        prompt = f"""Original response: {original_response}

Action execution results:
{result_summary}

Generate a natural follow-up message in the same language (Hindi/English) acknowledging the completed actions. Be conversational and friendly."""
        
        try:
            response = self.response_model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Failed to generate follow-up: {e}")
            return original_response


# Global orchestrator instance
_orchestrator: Optional[YahavisOrchestrator] = None


def get_orchestrator() -> YahavisOrchestrator:
    """Get or create orchestrator instance (singleton)"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = YahavisOrchestrator()
    return _orchestrator
