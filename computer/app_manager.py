"""
YAHAVIS — computer/app_manager.py
Open, close, switch, and list applications.
"""

import logging
import os
import subprocess
import sys
from typing import List, Optional

log = logging.getLogger("yahavis.app_manager")

# Common app name → executable mappings (Windows)
APP_MAP_WINDOWS = {
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "notepad": "notepad",
    "notepad++": "notepad++",
    "calculator": "calc",
    "explorer": "explorer",
    "task manager": "taskmgr",
    "cmd": "cmd",
    "powershell": "powershell",
    "terminal": "wt",
    "word": "winword",
    "excel": "excel",
    "teams": "Teams",
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
    "spotify": "Spotify",
    "vlc": "vlc",
    "obs": "obs64",
    "discord": "Discord",
    "postman": "Postman",
    "figma": "Figma",
}


class AppManager:
    """Manage desktop applications: open, close, switch, list."""

    def open_app(self, name: str, args: list = None):
        """Open an application by name."""
        exe = self._resolve_name(name)
        log.info(f"Opening app: {exe}")
        try:
            if sys.platform == "win32":
                cmd = [exe] + (args or [])
                subprocess.Popen(cmd, shell=True)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", exe] + (args or []))
            else:
                subprocess.Popen([exe] + (args or []))
        except Exception as e:
            log.warning(f"App open failed: {e} — trying os.startfile")
            try:
                os.startfile(exe)
            except Exception as e2:
                raise RuntimeError(f"Cannot open '{name}': {e2}")

    def close_app(self, name: str):
        """Kill an application by name using psutil."""
        try:
            import psutil
            name_lower = name.lower()
            killed = 0
            for proc in psutil.process_iter(["name", "pid"]):
                if name_lower in proc.info["name"].lower():
                    proc.kill()
                    killed += 1
                    log.info(f"Killed: {proc.info['name']} (PID {proc.info['pid']})")
            if killed == 0:
                log.warning(f"No process found matching: {name}")
            return killed
        except ImportError:
            log.error("psutil not installed")
            return 0

    def switch_to(self, name: str) -> bool:
        """Bring an application window to focus."""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(name)
            if not windows:
                # Try partial match
                all_wins = gw.getAllWindows()
                windows = [w for w in all_wins
                           if name.lower() in w.title.lower()]
            if windows:
                win = windows[0]
                win.restore()
                win.activate()
                log.info(f"Switched to: {win.title}")
                return True
            log.warning(f"No window found for: {name}")
            return False
        except Exception as e:
            log.warning(f"Window switch failed: {e}")
            return False

    def list_running(self, filter_name: str = None) -> List[dict]:
        """List all running processes."""
        try:
            import psutil
            procs = []
            for proc in psutil.process_iter(["name", "pid", "memory_percent", "cpu_percent"]):
                try:
                    info = proc.info
                    if filter_name and filter_name.lower() not in info["name"].lower():
                        continue
                    procs.append({
                        "name": info["name"],
                        "pid": info["pid"],
                        "memory_pct": round(info["memory_percent"] or 0, 2),
                        "cpu_pct": round(info["cpu_percent"] or 0, 2),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return sorted(procs, key=lambda p: p["memory_pct"], reverse=True)
        except ImportError:
            return []

    def is_running(self, name: str) -> bool:
        """Check if an app is currently running."""
        return len([p for p in self.list_running()
                    if name.lower() in p["name"].lower()]) > 0

    def _resolve_name(self, name: str) -> str:
        name_lower = name.lower().strip()
        if sys.platform == "win32":
            return APP_MAP_WINDOWS.get(name_lower, name_lower)
        return name_lower

    def get_active_window_title(self) -> str:
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            return win.title if win else ""
        except Exception:
            return ""
