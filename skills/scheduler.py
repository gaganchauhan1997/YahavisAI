"""
YAHAVIS — skills/scheduler.py
Schedule tasks, reminders, and cron-style recurring jobs.
Uses APScheduler for persistent scheduling.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

log = logging.getLogger("yahavis.scheduler")


class YahavisScheduler:
    """
    Task scheduler for YAHAVIS.
    Supports: one-shot timers, recurring cron jobs, reminders.
    """

    def __init__(self, speaker=None):
        self.speaker = speaker
        self._jobs: dict = {}
        self._scheduler = self._init_scheduler()

    def _init_scheduler(self):
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
            scheduler.start()
            log.info("APScheduler started (IST)")
            return scheduler
        except ImportError:
            log.warning("APScheduler not installed — using basic asyncio timers")
            return None

    def remind_in(self, message: str, seconds: int):
        """Set a reminder after `seconds` seconds."""
        async def _remind():
            await asyncio.sleep(seconds)
            log.info(f"Reminder: {message}")
            if self.speaker:
                await self.speaker.say(f"Reminder, Boss: {message}")

        task = asyncio.create_task(_remind())
        job_id = f"remind_{datetime.now().timestamp()}"
        self._jobs[job_id] = task
        mins = seconds // 60
        log.info(f"Reminder set: '{message}' in {mins}m {seconds%60}s")
        return job_id

    def remind_at(self, message: str, target_time: datetime):
        """Set a reminder at a specific datetime."""
        now = datetime.now()
        delta = (target_time - now).total_seconds()
        if delta <= 0:
            log.warning(f"Target time is in the past: {target_time}")
            return None
        return self.remind_in(message, int(delta))

    def schedule_daily(self, func: Callable, hour: int, minute: int = 0,
                       job_id: str = None) -> str:
        """Schedule a function to run daily at a specific time."""
        if not self._scheduler:
            log.warning("APScheduler unavailable — daily schedule skipped")
            return ""
        from apscheduler.triggers.cron import CronTrigger
        jid = job_id or f"daily_{hour:02d}{minute:02d}"
        self._scheduler.add_job(
            func,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=jid,
            replace_existing=True,
        )
        log.info(f"Daily job scheduled: {jid} at {hour:02d}:{minute:02d}")
        return jid

    def schedule_interval(self, func: Callable, minutes: int,
                          job_id: str = None) -> str:
        """Schedule a function to run every N minutes."""
        if not self._scheduler:
            return ""
        from apscheduler.triggers.interval import IntervalTrigger
        jid = job_id or f"interval_{minutes}m"
        self._scheduler.add_job(
            func,
            trigger=IntervalTrigger(minutes=minutes),
            id=jid,
            replace_existing=True,
        )
        log.info(f"Interval job scheduled: {jid} every {minutes}m")
        return jid

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a scheduled job."""
        if job_id in self._jobs:
            self._jobs[job_id].cancel()
            del self._jobs[job_id]
            return True
        if self._scheduler:
            try:
                self._scheduler.remove_job(job_id)
                return True
            except Exception:
                pass
        return False

    def list_jobs(self) -> list:
        """List all scheduled jobs."""
        jobs = []
        if self._scheduler:
            for job in self._scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "next_run": str(job.next_run_time),
                    "trigger": str(job.trigger),
                })
        # Add asyncio tasks
        for jid, task in self._jobs.items():
            jobs.append({"id": jid, "done": task.done()})
        return jobs

    async def daily_report(self, brain=None, speaker=None):
        """Generate and deliver the daily YAHAVIS report."""
        log.info("Generating daily report...")
        report = (
            f"YAHAVIS Daily Report — {datetime.now().strftime('%d %b %Y')}\n"
            f"All systems operational. Ready for tomorrow, Boss."
        )
        if speaker:
            await speaker.say("Daily report ready, Boss.")
        return report
