"""
JarvisAI - Conversation Memory System
Short-term context for active conversations
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Individual message in conversation"""
    id: str
    conversation_id: str
    user_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    device_id: Optional[str] = None


class ConversationMemory:
    """
    Short-term conversation memory using Redis
    Stores recent conversation context for AI context awareness
    """
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.ttl_seconds = 86400  # 24 hours retention
        self.max_messages_per_conversation = 100
        
    async def _get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection"""
        if self.redis is None:
            self.redis = await aioredis.from_url(
                settings.REDIS_URL,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
        return self.redis
    
    async def add_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
        device_id: Optional[str] = None
    ) -> Message:
        """Add a message to conversation memory"""
        try:
            redis = await self._get_redis()
            
            message = Message(
                id=f"{conversation_id}_{datetime.utcnow().timestamp()}",
                conversation_id=conversation_id,
                user_id=user_id,
                role=role,
                content=content,
                timestamp=datetime.utcnow(),
                metadata=metadata,
                device_id=device_id
            )
            
            # Store message
            key = f"conversation:{conversation_id}:messages"
            message_json = json.dumps(asdict(message), default=str)
            
            # Add to Redis list with timestamp score
            await redis.zadd(key, {message_json: message.timestamp.timestamp()})
            
            # Trim to max messages
            await redis.zremrangebyrank(key, 0, -self.max_messages_per_conversation - 1)
            
            # Set expiration
            await redis.expire(key, self.ttl_seconds)
            
            # Update conversation metadata
            await self._update_conversation_meta(redis, conversation_id, user_id)
            
            logger.debug(f"Added message to conversation {conversation_id}")
            return message
            
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            raise
    
    async def get_context(
        self,
        conversation_id: Optional[str],
        user_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """Get recent conversation context"""
        try:
            if not conversation_id:
                return []
                
            redis = await self._get_redis()
            key = f"conversation:{conversation_id}:messages"
            
            # Get recent messages
            messages_json = await redis.zrevrange(key, 0, limit - 1)
            
            messages = []
            for msg_json in reversed(messages_json):  # Oldest first
                try:
                    msg = json.loads(msg_json)
                    messages.append(msg)
                except json.JSONDecodeError:
                    continue
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get context: {e}")
            return []
    
    async def get_conversation_summary(
        self,
        conversation_id: str
    ) -> Dict[str, Any]:
        """Get summary of a conversation"""
        try:
            redis = await self._get_redis()
            key = f"conversation:{conversation_id}:messages"
            
            # Get all messages
            messages_json = await redis.zrange(key, 0, -1)
            
            user_messages = 0
            assistant_messages = 0
            topics = []
            
            for msg_json in messages_json:
                try:
                    msg = json.loads(msg_json)
                    if msg["role"] == "user":
                        user_messages += 1
                    else:
                        assistant_messages += 1
                except:
                    continue
            
            return {
                "conversation_id": conversation_id,
                "total_messages": len(messages_json),
                "user_messages": user_messages,
                "assistant_messages": assistant_messages,
                "topics": topics
            }
            
        except Exception as e:
            logger.error(f"Failed to get summary: {e}")
            return {}
    
    async def clear_conversation(self, conversation_id: str):
        """Clear a conversation from memory"""
        try:
            redis = await self._get_redis()
            key = f"conversation:{conversation_id}:messages"
            await redis.delete(key)
            logger.info(f"Cleared conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Failed to clear conversation: {e}")
    
    async def _update_conversation_meta(
        self,
        redis: aioredis.Redis,
        conversation_id: str,
        user_id: str
    ):
        """Update conversation metadata"""
        meta_key = f"conversation:{conversation_id}:meta"
        await redis.hset(meta_key, mapping={
            "user_id": user_id,
            "last_activity": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().timestamp()
        })
        await redis.expire(meta_key, self.ttl_seconds)
    
    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict]:
        """Get list of user's recent conversations"""
        try:
            redis = await self._get_redis()
            
            # Scan for user's conversations
            pattern = "conversation:*:meta"
            conversations = []
            
            async for key in redis.scan_iter(match=pattern):
                meta = await redis.hgetall(key)
                if meta.get("user_id") == user_id:
                    conv_id = key.decode().split(":")[1]
                    conversations.append({
                        "conversation_id": conv_id,
                        "last_activity": meta.get("last_activity"),
                        "updated_at": meta.get("updated_at")
                    })
            
            # Sort by last activity
            conversations.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
            return conversations[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get user conversations: {e}")
            return []


# Singleton instance
_memory: Optional[ConversationMemory] = None


def get_conversation_memory() -> ConversationMemory:
    """Get conversation memory instance"""
    global _memory
    if _memory is None:
        _memory = ConversationMemory()
    return _memory
