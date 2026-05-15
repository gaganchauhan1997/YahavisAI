"""
YAHAVIS — computer/screen_reader.py
Capture and interpret what's currently on screen.
Uses PIL screenshot + optional OCR (pytesseract) + vision LLM.
"""

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("yahavis.screen_reader")


class ScreenReader:
    """
    Takes screenshots and describes screen content via:
    1. OCR (pytesseract) for text extraction
    2. Vision LLM (Ollama llava / Gemini) for visual understanding
    """

    def __init__(self, brain=None):
        self.brain = brain

    def capture(self, region: Optional[tuple] = None) -> str:
        """
        Take a screenshot and save to temp file.
        region: (left, top, width, height) or None for full screen.
        Returns: path to saved PNG.
        """
        try:
            import mss
            import mss.tools
            path = tempfile.mktemp(suffix=".png")
            with mss.mss() as sct:
                monitor = sct.monitors[0] if not region else {
                    "left": region[0], "top": region[1],
                    "width": region[2], "height": region[3]
                }
                sct_img = sct.grab(monitor)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=path)
            log.info(f"Screen captured: {path}")
            return path
        except ImportError:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            if region:
                img = img.crop(region)
            path = tempfile.mktemp(suffix=".png")
            img.save(path)
            return path

    def read_text_ocr(self, image_path: str) -> str:
        """Extract text from image using pytesseract (offline OCR)."""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            return text.strip()
        except ImportError:
            log.warning("pytesseract not installed — OCR unavailable.")
            return ""
        except Exception as e:
            log.warning(f"OCR failed: {e}")
            return ""

    async def describe_screen(self, question: str = "What is on the screen?") -> str:
        """
        Capture screen and get a natural language description
        using a vision-capable LLM (Ollama llava or Gemini).
        """
        image_path = self.capture()
        description = await self._vision_describe(image_path, question)
        try:
            os.unlink(image_path)
        except Exception:
            pass
        return description

    async def _vision_describe(self, image_path: str, question: str) -> str:
        """Send image to vision LLM and get description."""
        # Try Ollama llava first (local)
        try:
            result = await self._ollama_vision(image_path, question)
            if result:
                return result
        except Exception as e:
            log.warning(f"Ollama vision failed: {e}")

        # Try Gemini vision (free tier)
        try:
            result = await self._gemini_vision(image_path, question)
            if result:
                return result
        except Exception as e:
            log.warning(f"Gemini vision failed: {e}")

        # Fall back to OCR
        ocr_text = self.read_text_ocr(image_path)
        if ocr_text:
            return f"Screen contains text: {ocr_text[:500]}"

        return "Unable to read screen content — vision module not available."

    async def _ollama_vision(self, image_path: str, question: str) -> str:
        import base64
        import aiohttp
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        payload = {
            "model": "llava",
            "messages": [
                {"role": "user", "content": question, "images": [img_b64]}
            ],
            "stream": False,
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.post(f"{base_url}/api/chat",
                                 json=payload,
                                 timeout=aiohttp.ClientTimeout(total=30)) as r:
                r.raise_for_status()
                data = await r.json()
                return data["message"]["content"]

    async def _gemini_vision(self, image_path: str, question: str) -> str:
        import google.generativeai as genai
        from PIL import Image
        api_key = os.getenv("GEMINI_API_KEY_1") or os.getenv("GEMINI_API_KEY_2")
        if not api_key:
            raise ValueError("No Gemini key configured")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        img = Image.open(image_path)
        resp = await asyncio.to_thread(model.generate_content, [question, img])
        return resp.text

    def find_element_on_screen(self, template_path: str,
                                confidence: float = 0.8) -> Optional[tuple]:
        """
        Find a UI element on screen by template image matching.
        Returns (x, y) center position or None.
        """
        try:
            import pyautogui
            loc = pyautogui.locateCenterOnScreen(template_path,
                                                 confidence=confidence)
            if loc:
                return (loc.x, loc.y)
        except Exception as e:
            log.warning(f"Template match failed: {e}")
        return None

    def get_active_window_screenshot(self) -> str:
        """Screenshot only the active window."""
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            if win:
                region = (win.left, win.top, win.width, win.height)
                return self.capture(region=region)
        except Exception:
            pass
        return self.capture()
