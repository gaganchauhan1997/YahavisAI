"""
YAHAVIS — computer/mouse_keyboard.py
Mouse and keyboard control via pyautogui + pynput.
"""

import logging
import time
from typing import Optional, Tuple

log = logging.getLogger("yahavis.mouse_keyboard")


class MouseKeyboard:
    """Full mouse + keyboard control for the local machine."""

    def __init__(self):
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.1
            self._pag = pyautogui
            log.info("MouseKeyboard ready (pyautogui)")
        except ImportError:
            log.error("pyautogui not installed — mouse/keyboard control disabled")
            self._pag = None

    # ── Keyboard ──────────────────────────────────────

    def type_text(self, text: str, interval: float = 0.03):
        """Type text character by character."""
        if self._pag:
            self._pag.write(text, interval=interval)
            log.debug(f"Typed: {text[:30]}...")

    def hotkey(self, *keys: str):
        """Press a key combination, e.g. hotkey('ctrl', 'c')."""
        if self._pag:
            self._pag.hotkey(*keys)
            log.debug(f"Hotkey: {'+'.join(keys)}")

    def press(self, key: str):
        """Press a single key."""
        if self._pag:
            self._pag.press(key)

    def key_down(self, key: str):
        if self._pag:
            self._pag.keyDown(key)

    def key_up(self, key: str):
        if self._pag:
            self._pag.keyUp(key)

    # ── Mouse ─────────────────────────────────────────

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1):
        """Click at absolute screen coordinates."""
        if self._pag:
            self._pag.click(x, y, button=button, clicks=clicks)
            log.debug(f"Click {button} @ ({x}, {y})")

    def double_click(self, x: int, y: int):
        self.click(x, y, clicks=2)

    def right_click(self, x: int, y: int):
        self.click(x, y, button="right")

    def move_to(self, x: int, y: int, duration: float = 0.2):
        if self._pag:
            self._pag.moveTo(x, y, duration=duration)

    def drag_drop(self, start: Tuple[int, int], end: Tuple[int, int],
                  duration: float = 0.5):
        if self._pag:
            self._pag.drag(start[0], start[1], end[0], end[1],
                           duration=duration, button="left")
            log.debug(f"Drag from {start} to {end}")

    def scroll(self, direction: str = "down", amount: int = 3, x: int = None, y: int = None):
        """Scroll mouse wheel. direction: 'up' | 'down'."""
        if not self._pag:
            return
        clicks = amount if direction == "up" else -amount
        if x and y:
            self._pag.scroll(clicks, x=x, y=y)
        else:
            self._pag.scroll(clicks)

    def get_position(self) -> Tuple[int, int]:
        if self._pag:
            return self._pag.position()
        return (0, 0)

    def get_screen_size(self) -> Tuple[int, int]:
        if self._pag:
            return self._pag.size()
        return (1920, 1080)

    def click_image(self, image_path: str, confidence: float = 0.8) -> bool:
        """Find an image on screen and click it."""
        if not self._pag:
            return False
        try:
            loc = self._pag.locateCenterOnScreen(image_path,
                                                 confidence=confidence)
            if loc:
                self._pag.click(loc)
                log.info(f"Clicked image: {image_path}")
                return True
        except Exception as e:
            log.warning(f"Image click failed: {e}")
        return False

    def write_to_clipboard(self, text: str):
        try:
            import pyperclip
            pyperclip.copy(text)
        except Exception as e:
            log.warning(f"Clipboard write failed: {e}")

    def read_clipboard(self) -> str:
        try:
            import pyperclip
            return pyperclip.paste()
        except Exception:
            return ""

    def paste_from_clipboard(self):
        """Paste clipboard contents at current cursor position."""
        self.hotkey("ctrl", "v")
