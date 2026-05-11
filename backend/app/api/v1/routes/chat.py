"""
YahavisAI - Chat API Routes
Handles chat messages and returns AI orchestrated responses
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
import logging

from app.services.ai.orchestrator import get_orchestrator, OrchestratorResponse
from app.services.memory.conversation_memory import get_conversation_memory

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()


class ChatMessageRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    device_id: Optional[str] = None
    language: str = "auto"  # auto, hi, en


class ChatMessageResponse(BaseModel):
    response_text: str
    actions: List[dict]
    confidence: float
    conversation_id: str
    follow_up_questions: Optional[List[str]] = None


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    token: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Send a chat message and get AI orchestrated response
    Supports Hindi and English input
    """
    try:
        # TODO: Validate JWT and extract user_id
        user_id = "demo_user"  # Placeholder until auth is implemented
        
        # Get AI orchestrator
        orchestrator = get_orchestrator()
        
        # Process through AI orchestrator
        result: OrchestratorResponse = await orchestrator.process_input(
            user_input=request.message,
            user_id=user_id,
            device_id=request.device_id,
            conversation_id=request.conversation_id
        )
        
        return ChatMessageResponse(
            response_text=result.response_text,
            actions=[{
                "action": a.action.value,
                "params": a.params,
                "device_target": a.device_target,
                "requires_confirmation": a.requires_confirmation,
                "reason": a.reason
            } for a in result.actions],
            confidence=result.confidence,
            conversation_id=request.conversation_id or "new_conversation",
            follow_up_questions=result.follow_up_questions
        )
        
    except Exception as e:
        logger.error(f"Chat message error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message"
        )


@router.get("/history/{conversation_id}")
async def get_chat_history(
    conversation_id: str,
    limit: int = 50,
    token: HTTPAuthorizationCredentials = Depends(security)
):
    """Get chat history for a conversation"""
    try:
        user_id = "demo_user"  # TODO: Extract from JWT
        memory = get_conversation_memory()
        
        messages = await memory.get_context(
            conversation_id=conversation_id,
            user_id=user_id,
            limit=limit
        )
        
        return {
            "conversation_id": conversation_id,
            "messages": messages,
            "count": len(messages)
        }
        
    except Exception as e:
        logger.error(f"Get history error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve history"
        )


@router.delete("/history/{conversation_id}")
async def clear_chat_history(
    conversation_id: str,
    token: HTTPAuthorizationCredentials = Depends(security)
):
    """Clear chat history for a conversation"""
    try:
        memory = get_conversation_memory()
        await memory.clear_conversation(conversation_id)
        
        return {"message": "Conversation history cleared", "conversation_id": conversation_id}
        
    except Exception as e:
        logger.error(f"Clear history error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear history"
        )
