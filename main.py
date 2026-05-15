"""
╔══════════════════════════════════════════════════════╗
║  YAHAVIS — Yahavi AI System v1.0                     ║
║  by Hackknow | Operator: Myth                        ║
║  "Free intelligence, infinite capability."           ║
╚══════════════════════════════════════════════════════╝
Entry point — boots all subsystems and starts the loop.
Run: python main.py
"""

import asyncio
import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ── Project root on path ──────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

load_dotenv()

# ── Logging ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s \033[36m[YAHAVIS]\033[0m %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("yahavis")

BANNER = """
\033[36m
 ██╗   ██╗ █████╗ ██╗  ██╗ █████╗ ██╗   ██╗██╗███████╗
  ╚██╗ ██╔╝██╔══██╗██║  ██║██╔══██╗██║   ██║██║██╔════╝
   ╚████╔╝ ███████║███████║███████║██║   ██║██║███████╗
    ╚██╔╝  ██╔══██║██╔══██║██╔══██║╚██╗ ██╔╝██║╚════██║
     ██║   ██║  ██║██║  ██║██║  ██║ ╚████╔╝ ██║███████║
     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
\033[0m
\033[35m        Yahavi AI System v1.0  ·  by Hackknow\033[0m
\033[90m        "Free intelligence, infinite capability."\033[0m
"""


async def main():
    print(BANNER)

    # ── Import subsystems ─────────────────────────────
    from core.brain import YahaviBrain
    from core.task_orchestrator import TaskOrchestrator
    from core.intent_parser import IntentParser
    from voice.listener import VoiceListener
    from voice.speaker import VoiceSpeaker
    from memory.short_term import ShortTermMemory
    from memory.long_term import LongTermMemory

    # ── Boot sequence ─────────────────────────────────
    log.info("[1/6] Loading memory systems ...")
    short_mem = ShortTermMemory(max_turns=20)
    long_mem  = LongTermMemory(db_path=ROOT / "memory" / "yahavis_memory.json")

    log.info("[2/6] Initializing brain (LLM router) ...")
    brain = YahaviBrain()

    log.info("[3/6] Loading intent parser ...")
    parser = IntentParser(brain=brain)

    log.info("[4/6] Starting voice systems ...")
    speaker  = VoiceSpeaker()
    listener = VoiceListener()

    log.info("[5/6] Loading task orchestrator ...")
    orchestrator = TaskOrchestrator(
        brain=brain,
        parser=parser,
        speaker=speaker,
        short_mem=short_mem,
        long_mem=long_mem,
    )

    log.info("[6/6] Starting UI dashboard on http://localhost:7070 ...")
    # Lazy import so UI is optional if dependencies missing
    try:
        from ui.server import UIServer
        ui = UIServer(port=7070, orchestrator=orchestrator)
        ui_task = asyncio.create_task(ui.start())
    except ImportError:
        log.warning("UI server dependencies missing — running headless.")
        ui_task = asyncio.sleep(0)  # no-op

    await speaker.say("YAHAVIS online. Ready for your commands, Boss.")
    print("\n\033[36m[INFO]\033[0m Dashboard  → http://localhost:7070")
    print("\033[36m[INFO]\033[0m Hotword    → 'Hey Yahavi'")
    print("\033[36m[INFO]\033[0m Shortcut   → Ctrl+Space")
    print("\033[36m[INFO]\033[0m Shutdown   → Ctrl+C\n")

    try:
        await asyncio.gather(
            listener.start(orchestrator),
            ui_task,
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        log.info("Shutting down YAHAVIS ...")
        await speaker.say("Shutting down. Goodbye, Boss.")
        long_mem.save()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\033[90m[YAHAVIS] Offline.\033[0m")
