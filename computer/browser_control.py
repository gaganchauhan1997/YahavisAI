"""
YAHAVIS — computer/browser_control.py
Async browser automation via Playwright.
Install deps: pip install playwright && python -m playwright install chromium
"""

import asyncio
import logging
from typing import Optional

log = logging.getLogger("yahavis.browser")


class BrowserControl:
    """
    Async Playwright-based browser automation.
    Supports navigation, search, form filling, text extraction, scrolling.
    """

    def __init__(self, headless: bool = False, browser_type: str = "chromium"):
        self._headless = headless
        self._browser_type = browser_type
        self._playwright = None
        self._browser = None
        self._page = None

    async def _ensure_browser(self):
        """Lazily start the browser if not running."""
        if self._page and not self._page.is_closed():
            return
        try:
            from playwright.async_api import async_playwright
            if not self._playwright:
                self._playwright = await async_playwright().start()
            browser_launcher = getattr(self._playwright, self._browser_type)
            self._browser = await browser_launcher.launch(headless=self._headless)
            context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self._page = await context.new_page()
            log.info(f"Browser started: {self._browser_type} (headless={self._headless})")
        except ImportError:
            raise RuntimeError("playwright not installed. Run: pip install playwright && python -m playwright install chromium")

    async def open_url(self, url: str, wait_until: str = "domcontentloaded"):
        """Navigate to a URL."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        await self._ensure_browser()
        log.info(f"Navigating to: {url}")
        await self._page.goto(url, wait_until=wait_until)

    async def search_google(self, query: str):
        """Search Google for a query."""
        import urllib.parse
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        await self.open_url(url)
        log.info(f"Google search: {query}")

    async def search_duckduckgo(self, query: str):
        """Search DuckDuckGo (more privacy-friendly)."""
        import urllib.parse
        url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}"
        await self.open_url(url)

    async def click_element(self, selector: str, timeout: int = 5000):
        """Click an element by CSS selector."""
        await self._ensure_browser()
        await self._page.click(selector, timeout=timeout)
        log.debug(f"Clicked: {selector}")

    async def fill_form(self, selector: str, value: str):
        """Fill an input field."""
        await self._ensure_browser()
        await self._page.fill(selector, value)
        log.debug(f"Filled {selector}: {value[:30]}...")

    async def extract_text(self, selector: str = "body") -> str:
        """Extract text from a CSS selector."""
        await self._ensure_browser()
        try:
            element = await self._page.query_selector(selector)
            if element:
                return await element.inner_text()
        except Exception as e:
            log.warning(f"Text extraction failed: {e}")
        return ""

    async def extract_all_text(self) -> str:
        """Extract all visible text from the current page."""
        return await self.extract_text("body")

    async def scroll_page(self, direction: str = "down", amount: int = 500):
        """Scroll the page up or down."""
        await self._ensure_browser()
        delta = amount if direction == "down" else -amount
        await self._page.evaluate(f"window.scrollBy(0, {delta})")

    async def get_current_url(self) -> str:
        await self._ensure_browser()
        return self._page.url

    async def get_title(self) -> str:
        await self._ensure_browser()
        return await self._page.title()

    async def screenshot(self, path: str = "screenshot.png") -> str:
        await self._ensure_browser()
        await self._page.screenshot(path=path, full_page=False)
        return path

    async def press_key(self, key: str):
        await self._ensure_browser()
        await self._page.keyboard.press(key)

    async def type_text(self, text: str, delay: int = 50):
        await self._ensure_browser()
        await self._page.keyboard.type(text, delay=delay)

    async def wait_for_selector(self, selector: str, timeout: int = 10000):
        await self._ensure_browser()
        await self._page.wait_for_selector(selector, timeout=timeout)

    async def evaluate(self, js: str):
        """Run arbitrary JavaScript on the page."""
        await self._ensure_browser()
        return await self._page.evaluate(js)

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        log.info("Browser closed.")
