"""
YahavisAI - WebSocket Handler for Agent Communication
Real-time bidirectional communication with desktop and mobile agents
"""

import json
import logging
from typing import Dict, Set, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from starlette.websockets import WebSocketState

from app.core.config import settings
from app.services.ai.orchestrator import get_orchestrator, OrchestratorResponse, YahavisOrchestrator
from app.services.queue.task_queue import get_task_queue

logger = logging.getLogger(__name__)

# Router
websocket_router = APIRouter()

# Connection management
class ConnectionManager:
    """Manages WebSocket connections from all agents"""
    
    def __init__(self):
        # user_id -> {device_id -> websocket}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.device_info: Dict[str, Dict] = {}  # device_id -> metadata
        
    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        device_id: str,
        device_type: str  # "desktop", "mobile", "browser"
    ):
        """Accept and register new connection"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
        
        # Close existing connection for this device if any
        if device_id in self.active_connections[user_id]:
            old_ws = self.active_connections[user_id][device_id]
            try:
                await old_ws.close()
            except:
                pass
        
        self.active_connections[user_id][device_id] = websocket
        self.device_info[device_id] = {
            "type": device_type,
            "connected_at": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "last_ping": datetime.utcnow().timestamp()
        }
        
        logger.info(f"Agent connected: {device_type} {device_id} for user {user_id}")
        
        # Send connection acknowledgment
        await self.send_to_device(
            user_id,
            device_id,
            {
                "type": "connected",
                "message": "Connected to JarvisAI cloud",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def disconnect(self, user_id: str, device_id: str):
        """Remove disconnected agent"""
        if user_id in self.active_connections:
            self.active_connections[user_id].pop(device_id, None)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        self.device_info.pop(device_id, None)
        logger.info(f"Agent disconnected: {device_id}")
    
    async def send_to_device(
        self,
        user_id: str,
        device_id: str,
        message: Dict
    ) -> bool:
        """Send message to specific device"""
        try:
            if user_id not in self.active_connections:
                return False
            
            websocket = self.active_connections[user_id].get(device_id)
            if not websocket:
                return False
            
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
                return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to send to device {device_id}: {e}")
            return False
    
    async def send_to_user(
        self,
        user_id: str,
        message: Dict,
        exclude_device: Optional[str] = None
    ) -> int:
        """Broadcast message to all user's devices"""
        sent_count = 0
        
        if user_id not in self.active_connections:
            return 0
        
        for device_id, websocket in self.active_connections[user_id].items():
            if device_id == exclude_device:
                continue
            
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
                    sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {device_id}: {e}")
        
        return sent_count
    
    async def send_to_device_type(
        self,
        user_id: str,
        device_type: str,
        message: Dict
    ) -> int:
        """Send message to all devices of a specific type"""
        sent_count = 0
        
        if user_id not in self.active_connections:
            return 0
        
        for device_id, websocket in self.active_connections[user_id].items():
            info = self.device_info.get(device_id, {})
            if info.get("type") != device_type:
                continue
            
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
                    sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {device_id}: {e}")
        
        return sent_count
    
    def get_user_devices(self, user_id: str) -> Dict[str, Dict]:
        """Get all connected devices for a user"""
        devices = {}
        if user_id in self.active_connections:
            for device_id in self.active_connections[user_id].keys():
                if device_id in self.device_info:
                    devices[device_id] = self.device_info[device_id]
        return devices
    
    def get_online_users(self) -> Set[str]:
        """Get set of all online users"""
        return set(self.active_connections.keys())


# Global connection manager
manager = ConnectionManager()


@websocket_router.websocket("/agent")
async def agent_websocket(
    websocket: WebSocket,
    user_id: str,
    device_id: str,
    device_type: str = "desktop",
    token: str = None
):
    """
    Main WebSocket endpoint for agent connections
    Desktop and mobile agents connect here
    """
    # TODO: Validate token
    
    await manager.connect(websocket, user_id, device_id, device_type)
    orchestrator = get_orchestrator()
    task_queue = get_task_queue()
    
    try:
        while True:
            # Receive message from agent
            data = await websocket.receive_json()
            
            message_type = data.get("type", "unknown")
            
            if message_type == "ping":
                # Update last ping time
                if device_id in manager.device_info:
                    manager.device_info[device_id]["last_ping"] = datetime.utcnow().timestamp()
                await websocket.send_json({"type": "pong"})
                
            elif message_type == "user_input":
                # Process user message through AI orchestrator
                user_message = data.get("message", "")
                conversation_id = data.get("conversation_id")
                
                # Send "thinking" status
                await manager.send_to_device(user_id, device_id, {
                    "type": "status",
                    "status": "thinking",
                    "message": "Processing your request..."
                })
                
                # Process through AI orchestrator
                response: OrchestratorResponse = await orchestrator.process_input(
                    user_input=user_message,
                    user_id=user_id,
                    device_id=device_id,
                    conversation_id=conversation_id
                )
                
                # Send AI response text
                await manager.send_to_device(user_id, device_id, {
                    "type": "ai_response",
                    "message": response.response_text,
                    "confidence": response.confidence,
                    "follow_up_questions": response.follow_up_questions
                })
                
                # Queue actions for execution
                if response.actions:
                    action_results = []
                    
                    for action in response.actions:
                        # Add to task queue
                        task_id = await task_queue.add_task(
                            user_id=user_id,
                            action=action.action.value,
                            params=action.params,
                            device_target=action.device_target or device_type,
                            requires_confirmation=action.requires_confirmation,
                            priority=1 if action.requires_confirmation else 5
                        )
                        
                        # Send task to appropriate device
                        await manager.send_to_device_type(
                            user_id,
                            action.device_target or device_type,
                            {
                                "type": "execute_action",
                                "task_id": task_id,
                                "action": action.action.value,
                                "params": action.params,
                                "requires_confirmation": action.requires_confirmation,
                                "reason": action.reason
                            }
                        )
                        
                        action_results.append({
                            "task_id": task_id,
                            "action": action.action.value,
                            "status": "queued"
                        })
                    
                    # Send action summary
                    await manager.send_to_device(user_id, device_id, {
                        "type": "actions_queued",
                        "actions": action_results,
                        "count": len(action_results)
                    })
                
            elif message_type == "action_result":
                # Receive action execution result from agent
                task_id = data.get("task_id")
                success = data.get("success", False)
                result_data = data.get("result", {})
                error = data.get("error")
                
                # Update task status
                await task_queue.update_task(
                    task_id=task_id,
                    status="completed" if success else "failed",
                    result=result_data,
                    error=error
                )
                
                # Notify all devices of completion
                await manager.send_to_user(user_id, {
                    "type": "action_completed",
                    "task_id": task_id,
                    "success": success,
                    "result": result_data,
                    "error": error
                }, exclude_device=device_id)
                
                # Generate follow-up response if needed
                if success and result_data:
                    follow_up = await orchestrator.generate_follow_up_response(
                        action_results=[{
                            "action": data.get("action"),
                            "success": success,
                            "result": result_data
                        }],
                        original_response="Task completed"
                    )
                    
                    await manager.send_to_user(user_id, {
                        "type": "follow_up",
                        "message": follow_up
                    })
                
            elif message_type == "device_status":
                # Update device status
                status = data.get("status", {})
                if device_id in manager.device_info:
                    manager.device_info[device_id].update(status)
                
            elif message_type == "confirmation_response":
                # User confirmed/denied a pending action
                task_id = data.get("task_id")
                confirmed = data.get("confirmed", False)
                
                if confirmed:
                    # Execute the confirmed action
                    await task_queue.confirm_task(task_id)
                else:
                    await task_queue.cancel_task(task_id, reason="User denied")
                
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
    except WebSocketDisconnect:
        manager.disconnect(user_id, device_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(user_id, device_id)


@websocket_router.websocket("/dashboard")
async def dashboard_websocket(
    websocket: WebSocket,
    user_id: str,
    token: str = None
):
    """
    WebSocket for web dashboard
    Receives real-time updates about all devices and tasks
    """
    await manager.connect(websocket, user_id, "dashboard", "browser")
    
    try:
        # Send initial device list
        devices = manager.get_user_devices(user_id)
        await websocket.send_json({
            "type": "device_list",
            "devices": devices
        })
        
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                
            elif message_type == "broadcast":
                # Broadcast message to all user devices
                message = data.get("message", {})
                await manager.send_to_user(user_id, message)
                
            elif message_type == "get_devices":
                devices = manager.get_user_devices(user_id)
                await websocket.send_json({
                    "type": "device_list",
                    "devices": devices
                })
                
    except WebSocketDisconnect:
        manager.disconnect(user_id, "dashboard")
    except Exception as e:
        logger.error(f"Dashboard WebSocket error: {e}")
        manager.disconnect(user_id, "dashboard")


# HTTP endpoints for WebSocket-related operations
@websocket_router.get("/devices/{user_id}")
async def get_user_devices(user_id: str):
    """Get list of connected devices for a user"""
    devices = manager.get_user_devices(user_id)
    return {
        "user_id": user_id,
        "devices": devices,
        "count": len(devices),
        "online": len(devices) > 0
    }


@websocket_router.post("/send/{user_id}")
async def send_message_to_user(user_id: str, message: Dict):
    """Send a message to all user's devices via HTTP"""
    count = await manager.send_to_user(user_id, message)
    return {
        "sent": count,
        "user_id": user_id
    }
