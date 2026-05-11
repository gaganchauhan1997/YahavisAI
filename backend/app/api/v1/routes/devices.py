from fastapi import APIRouter

from app.api.websocket.agent_socket import manager

router = APIRouter()


@router.get("")
async def list_devices(user_id: str = "demo"):
    devices = manager.get_user_devices(user_id)
    return {"devices": devices, "count": len(devices)}
