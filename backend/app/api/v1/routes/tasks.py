from fastapi import APIRouter

from app.services.queue.task_queue import get_task_queue

router = APIRouter()


@router.get("")
async def list_tasks(user_id: str | None = None):
    return {"tasks": await get_task_queue().list_tasks(user_id)}


@router.patch("/{task_id}/status")
async def update_task_status(task_id: str, status: str):
    task = await get_task_queue().update_status(task_id, status)
    return {"task": task}
