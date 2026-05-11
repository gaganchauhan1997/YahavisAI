from datetime import datetime, timezone
from uuid import uuid4


class TaskQueue:
    def __init__(self) -> None:
        self._tasks: dict[str, dict] = {}

    async def add_task(
        self,
        user_id: str,
        action: str,
        params: dict,
        device_target: str,
        requires_confirmation: bool,
        priority: int = 5,
    ) -> str:
        task_id = str(uuid4())
        self._tasks[task_id] = {
            "id": task_id,
            "user_id": user_id,
            "action": action,
            "params": params,
            "device_target": device_target,
            "requires_confirmation": requires_confirmation,
            "priority": priority,
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return task_id

    async def list_tasks(self, user_id: str | None = None) -> list[dict]:
        tasks = list(self._tasks.values())
        if user_id:
            tasks = [task for task in tasks if task["user_id"] == user_id]
        return sorted(tasks, key=lambda task: task["created_at"], reverse=True)

    async def update_status(self, task_id: str, status: str) -> dict | None:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task["status"] = status
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        return task

    async def update_task(
        self,
        task_id: str,
        status: str,
        result: dict | None = None,
        error: str | None = None,
    ) -> dict | None:
        task = await self.update_status(task_id, status)
        if not task:
            return None
        task["result"] = result or {}
        task["error"] = error
        return task

    async def confirm_task(self, task_id: str) -> dict | None:
        return await self.update_status(task_id, "confirmed")

    async def cancel_task(self, task_id: str, reason: str = "") -> dict | None:
        task = await self.update_status(task_id, "cancelled")
        if task:
            task["error"] = reason
        return task


_queue = TaskQueue()


def get_task_queue() -> TaskQueue:
    return _queue
