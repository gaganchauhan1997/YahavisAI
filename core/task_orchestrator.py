"""
YAHAVIS — core/task_orchestrator.py
Multi-step task planning and execution engine.
Handles sequential and parallel task queues.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

log = logging.getLogger("yahavis.orchestrator")


class Priority(int, Enum):
    CRITICAL = 0   # Alarms, emergency stops
    HIGH     = 1   # Active user voice commands
    MEDIUM   = 2   # Content generation, research
    LOW      = 3   # Background, analytics, auto-drafts


class TaskStatus(str, Enum):
    QUEUED   = "queued"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"
    RETRYING = "retrying"


@dataclass
class Task:
    task_type: str
    intent: Any
    priority: Priority = Priority.HIGH
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: TaskStatus = TaskStatus.QUEUED
    result: Any = None
    error: str = ""
    retries: int = 0
    max_retries: int = 2

    def __lt__(self, other):
        return self.priority < other.priority


class TaskOrchestrator:
    """
    Receives parsed intents, routes them to the correct executor,
    manages the task queue, and reports back via voice + UI.
    """

    MAX_CONCURRENT = 3

    def __init__(self, brain=None, parser=None, speaker=None,
                 short_mem=None, long_mem=None):
        self.brain     = brain
        self.parser    = parser
        self.speaker   = speaker
        self.short_mem = short_mem
        self.long_mem  = long_mem
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running: dict[str, Task] = {}
        self._history: list[Task] = []
        self._executors: dict[str, Callable] = {}
        self._draining: bool = False   # Bug fix: prevent concurrent drain races
        self._register_executors()
        log.info("TaskOrchestrator ready.")

    def _register_executors(self):
        """Register intent → executor mapping lazily."""
        self._executors = {
            "FILE_OP":      self._exec_file_op,
            "APP_CONTROL":  self._exec_app_control,
            "BROWSER":      self._exec_browser,
            "SYSTEM":       self._exec_system,
            "CONTENT_GEN":  self._exec_content_gen,
            "HACKKNOW":     self._exec_hackknow,
            "MEMORY":       self._exec_memory,
            "CODE":         self._exec_code,
            "CHAT":         self._exec_chat,
        }

    async def handle(self, raw_input: str):
        """Entry point — parse input and queue the task."""
        log.info(f"Handling: {raw_input[:60]}...")
        intent = await self.parser.parse(raw_input)
        log.info(f"Intent: {intent.intent}.{intent.action} "
                 f"(conf={intent.confidence:.2f})")

        # Speak acknowledgement immediately
        if intent.voice_response and self.speaker:
            asyncio.create_task(self.speaker.say(intent.voice_response))

        if not intent.is_confident(0.55):
            # Bug fix: guard against speaker being None
            if self.speaker:
                await self.speaker.say(
                    "I'm not sure what you mean, Boss. Could you rephrase?"
                )
            return

        task = Task(
            task_type=intent.intent,
            intent=intent,
            priority=self._get_priority(intent.intent),
        )
        await self._queue.put((task.priority, task))
        asyncio.create_task(self._drain_queue())

    async def _drain_queue(self):
        # Bug fix: prevent concurrent drains from spawning excess tasks
        if self._draining:
            return
        self._draining = True
        try:
            while not self._queue.empty() and len(self._running) < self.MAX_CONCURRENT:
                try:
                    _, task = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                asyncio.create_task(self._execute(task))
        finally:
            self._draining = False

    async def _execute(self, task: Task):
        task.status = TaskStatus.RUNNING
        self._running[task.task_id] = task
        log.info(f"[{task.task_id}] Executing {task.task_type}")

        executor = self._executors.get(task.task_type, self._exec_chat)
        try:
            result = await executor(task.intent)
            task.result = result
            task.status = TaskStatus.DONE
            log.info(f"[{task.task_id}] Done.")
        except Exception as e:
            task.error = str(e)
            task.retries += 1
            log.warning(f"[{task.task_id}] Error: {e}")
            if task.retries <= task.max_retries:
                task.status = TaskStatus.RETRYING
                await asyncio.sleep(1.5 ** task.retries)
                await self._queue.put((task.priority, task))
            else:
                task.status = TaskStatus.FAILED
                if self.speaker:
                    await self.speaker.say(
                        f"Task failed, Boss. {str(e)[:80]}"
                    )
        finally:
            self._running.pop(task.task_id, None)
            self._history.append(task)
            if len(self._history) > 100:
                self._history = self._history[-100:]
            await self._drain_queue()

    # ── Executors ─────────────────────────────────────

    async def _exec_file_op(self, intent):
        from computer.file_ops import FileOps
        ops = FileOps()
        action = intent.action
        params = intent.params
        if action == "search":
            results = ops.search(
                folder=params.get("folder", "~/Downloads"),
                extension=params.get("extension"),
                query=params.get("query"),
            )
            summary = f"Found {len(results)} file(s)."
            if self.speaker:
                await self.speaker.say(summary)
            return results
        elif action == "open":
            ops.open_file(params.get("path", intent.target))
        elif action == "delete":
            ops.delete(params.get("path", intent.target))
        return f"File operation '{action}' complete."

    async def _exec_app_control(self, intent):
        from computer.app_manager import AppManager
        mgr = AppManager()
        action = intent.action
        params = intent.params
        if action == "open":
            mgr.open_app(params.get("app_name", intent.target))
        elif action == "close":
            mgr.close_app(params.get("app_name", intent.target))
        elif action == "switch":
            mgr.switch_to(params.get("app_name", intent.target))

    async def _exec_browser(self, intent):
        from computer.browser_control import BrowserControl
        browser = BrowserControl()
        action = intent.action
        params = intent.params
        if action == "navigate":
            await browser.open_url(params.get("url", intent.target))
        elif action == "search":
            await browser.search_google(intent.target)
        elif action == "extract":
            return await browser.extract_text(params.get("selector", "body"))

    async def _exec_system(self, intent):
        from computer.system_ops import SystemOps
        ops = SystemOps()
        action = intent.action
        params = intent.params
        if action == "screenshot":
            path = ops.screenshot()
            if self.speaker:
                await self.speaker.say(f"Screenshot saved, Boss.")
            return path
        elif action == "set_volume":
            ops.set_volume(params.get("level", 50))
        elif action == "shutdown":
            timer = params.get("timer", 0)
            ops.shutdown(timer)
        elif action == "lock":
            ops.lock_screen()

    async def _exec_content_gen(self, intent):
        from skills.content_engine import ContentEngine
        engine = ContentEngine(brain=self.brain)
        result = await engine.generate(
            title=intent.target,
            content_type=intent.params.get("type", "blog"),
            tone=intent.params.get("tone", "professional"),
        )
        if self.speaker:
            await self.speaker.say("Content generated, Boss. Opening in editor.")
        from skills.code_writer import CodeWriter
        CodeWriter().save_and_open(result, filename="yahavis_content.md")
        return result

    async def _exec_hackknow(self, intent):
        from skills.hackknow_ops import HackknowOps
        ops = HackknowOps()
        action = intent.action
        if action == "get_orders":
            orders = await ops.get_orders(filter_=intent.params.get("filter", "today"))
            # Bug fix: use summarize_orders() for proper currency + pluralization
            summary = ops.summarize_orders(orders)
            if self.speaker:
                await self.speaker.say(summary)
            return orders
        elif action == "create_product":
            return await ops.create_product(intent.params)

    async def _exec_memory(self, intent):
        if intent.action == "remember" and self.long_mem:
            self.long_mem.save_fact(intent.target, intent.params)
        elif intent.action == "recall" and self.long_mem:
            return self.long_mem.recall(intent.target)

    async def _exec_code(self, intent):
        from skills.code_writer import CodeWriter
        writer = CodeWriter()
        result = await writer.generate(
            description=intent.target,
            language=intent.params.get("language", "python"),
            brain=self.brain,
        )
        if self.speaker:
            await self.speaker.say("Code written and opened in editor, Boss.")
        return result

    async def _exec_chat(self, intent):
        response = await self.brain.think(intent.raw_input)
        if self.speaker:
            await self.speaker.say(response)
        return response

    def _get_priority(self, intent_type: str) -> Priority:
        priority_map = {
            "SYSTEM":   Priority.HIGH,
            "HACKKNOW": Priority.MEDIUM,
            "BROWSER":  Priority.MEDIUM,
            "APP_CONTROL": Priority.HIGH,
            "FILE_OP":  Priority.MEDIUM,
            "CONTENT_GEN": Priority.MEDIUM,
            "CODE":     Priority.MEDIUM,
            "MEMORY":   Priority.LOW,
            "CHAT":     Priority.LOW,
        }
        return priority_map.get(intent_type, Priority.MEDIUM)

    def queue_status(self) -> dict:
        return {
            "queued": self._queue.qsize(),
            "running": len(self._running),
            "completed": sum(1 for t in self._history if t.status == TaskStatus.DONE),
            "failed": sum(1 for t in self._history if t.status == TaskStatus.FAILED),
            "recent": [
                {"id": t.task_id, "type": t.task_type, "status": t.status}
                for t in self._history[-5:]
            ],
        }
