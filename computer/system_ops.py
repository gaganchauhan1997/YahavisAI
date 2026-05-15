"""
YAHAVIS — computer/system_ops.py
System-level operations: volume, brightness, screenshots,
shutdown, lock, battery, system info.
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("yahavis.system_ops")

SCREENSHOT_DIR = Path(
    os.getenv("SCREENSHOT_DIR", "~/Pictures/YAHAVIS")
).expanduser()


class SystemOps:
    """System control operations for Windows 10/11."""

    def screenshot(self, save_path: Optional[str] = None) -> str:
        """Take a screenshot and save it."""
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        if not save_path:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = str(SCREENSHOT_DIR / f"yahavis_{timestamp}.png")
        try:
            import mss
            import mss.tools
            with mss.mss() as sct:
                sct_img = sct.grab(sct.monitors[0])
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=save_path)
        except ImportError:
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                img.save(save_path)
            except Exception as e:
                raise RuntimeError(f"Screenshot failed: {e}")
        log.info(f"Screenshot saved: {save_path}")
        return save_path

    def set_volume(self, level: int):
        """Set system volume 0–100."""
        level = max(0, min(100, level))
        log.info(f"Setting volume: {level}%")
        if sys.platform == "win32":
            try:
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                from comtypes import CLSCTX_ALL
                import ctypes
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_,
                                             CLSCTX_ALL, None)
                volume = ctypes.cast(interface,
                                     ctypes.POINTER(IAudioEndpointVolume))
                # Convert 0-100 to 0.0-1.0 scalar
                scalar = level / 100.0
                volume.SetMasterVolumeLevelScalar(scalar, None)
            except Exception as e:
                log.warning(f"pycaw volume failed: {e} — trying nircmd")
                try:
                    # nircmd fallback
                    nircmd_level = int(level / 100 * 65535)
                    subprocess.run(["nircmd.exe", "setsysvolume",
                                    str(nircmd_level)], check=True)
                except Exception as e2:
                    log.error(f"Volume control failed: {e2}")
        elif sys.platform == "darwin":
            subprocess.run(["osascript", "-e",
                            f"set volume output volume {level}"])
        else:
            subprocess.run(["amixer", "sset", "Master", f"{level}%"])

    def get_volume(self) -> int:
        """Get current system volume (0–100)."""
        if sys.platform == "win32":
            try:
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                from comtypes import CLSCTX_ALL
                import ctypes
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_,
                                             CLSCTX_ALL, None)
                volume = ctypes.cast(interface,
                                     ctypes.POINTER(IAudioEndpointVolume))
                return int(volume.GetMasterVolumeLevelScalar() * 100)
            except Exception:
                pass
        return -1

    def set_brightness(self, level: int):
        """Set screen brightness 0–100."""
        level = max(0, min(100, level))
        log.info(f"Setting brightness: {level}%")
        try:
            import screen_brightness_control as sbc
            sbc.set_brightness(level)
        except Exception as e:
            log.warning(f"Brightness control failed: {e}")

    def get_brightness(self) -> int:
        try:
            import screen_brightness_control as sbc
            result = sbc.get_brightness()
            return result[0] if isinstance(result, list) else result
        except Exception:
            return -1

    def lock_screen(self):
        """Lock the screen."""
        log.info("Locking screen")
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        elif sys.platform == "darwin":
            subprocess.run(["pmset", "displaysleepnow"])
        else:
            subprocess.run(["xdg-screensaver", "lock"])

    def shutdown(self, timer: int = 0):
        """Schedule system shutdown. timer=0 means immediate."""
        log.info(f"Shutdown scheduled (timer={timer}s)")
        if sys.platform == "win32":
            subprocess.run(["shutdown", "/s", "/t", str(timer)])
        elif sys.platform == "darwin":
            # Bug fix: timers < 60s would produce "+0" which macOS rejects.
            # Use "now" for anything under 60 seconds.
            timer_arg = f"+{timer // 60}" if timer >= 60 else "now"
            subprocess.run(["sudo", "shutdown", "-h", timer_arg])
        else:
            timer_arg = f"+{timer // 60}" if timer >= 60 else "now"
            subprocess.run(["shutdown", "-h", timer_arg])

    def cancel_shutdown(self):
        if sys.platform == "win32":
            subprocess.run(["shutdown", "/a"])
        else:
            subprocess.run(["shutdown", "-c"])

    def restart(self, timer: int = 0):
        if sys.platform == "win32":
            subprocess.run(["shutdown", "/r", "/t", str(timer)])

    def get_battery_status(self) -> dict:
        try:
            import psutil
            bat = psutil.sensors_battery()
            if bat:
                return {
                    "percent": round(bat.percent, 1),
                    "plugged": bat.power_plugged,
                    "seconds_left": bat.secsleft,
                    "time_left": self._format_time(bat.secsleft),
                }
        except Exception:
            pass
        return {"percent": -1, "plugged": None, "seconds_left": -1}

    def get_system_info(self) -> dict:
        try:
            import psutil
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "cpu_cores": psutil.cpu_count(),
                "ram_total_gb": round(psutil.virtual_memory().total / 1e9, 1),
                "ram_used_pct": round(psutil.virtual_memory().percent, 1),
                "ram_available_gb": round(psutil.virtual_memory().available / 1e9, 1),
                "disk_total_gb": round(psutil.disk_usage("/").total / 1e9, 1),
                "disk_used_pct": round(psutil.disk_usage("/").percent, 1),
                "boot_time": psutil.boot_time(),
                "platform": sys.platform,
                "battery": self.get_battery_status(),
            }
        except ImportError:
            return {"error": "psutil not installed"}

    def _format_time(self, seconds: int) -> str:
        if seconds < 0:
            return "N/A"
        h, m = divmod(seconds // 60, 60)
        return f"{h}h {m}m" if h else f"{m}m"

    def open_settings(self):
        """Open Windows Settings."""
        if sys.platform == "win32":
            subprocess.Popen(["ms-settings:"])

    def empty_recycle_bin(self):
        if sys.platform == "win32":
            import winshell
            winshell.recycle_bin().empty(confirm=False, show_progress=False)
