"""
YAHAVIS — skills/web_search.py
Free web search using DuckDuckGo — no API key required.
Falls back to Google scraping if DDG unavailable.
"""

import asyncio
import logging
from typing import List

log = logging.getLogger("yahavis.web_search")


class WebSearch:
    """
    Search the web for free using DuckDuckGo.
    No API key required — uses duckduckgo_search library.
    """

    async def search(
        self,
        query: str,
        max_results: int = 5,
        region: str = "in-en",
    ) -> List[dict]:
        """
        Search DuckDuckGo and return structured results.
        Returns: [{"title": ..., "url": ..., "snippet": ...}]
        """
        try:
            from duckduckgo_search import DDGS
            results = await asyncio.to_thread(
                self._ddg_search, query, max_results, region
            )
            return results
        except ImportError:
            log.warning("duckduckgo_search not installed — trying requests fallback")
            return await self._requests_fallback(query, max_results)
        except Exception as e:
            log.error(f"Search failed: {e}")
            return []

    def _ddg_search(self, query: str, max_results: int, region: str) -> List[dict]:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, region=region, max_results=max_results):
                results.append({
                    "title":   r.get("title", ""),
                    "url":     r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        log.info(f"DDG search '{query}': {len(results)} results")
        return results

    async def search_news(self, query: str, max_results: int = 5) -> List[dict]:
        """Search for recent news articles."""
        try:
            from duckduckgo_search import DDGS
            results = []
            def _search():
                with DDGS() as ddgs:
                    for r in ddgs.news(query, max_results=max_results):
                        results.append({
                            "title":   r.get("title", ""),
                            "url":     r.get("url", ""),
                            "snippet": r.get("body", ""),
                            "date":    r.get("date", ""),
                            "source":  r.get("source", ""),
                        })
                return results
            return await asyncio.to_thread(_search)
        except Exception as e:
            log.warning(f"News search failed: {e}")
            return []

    async def get_quick_answer(self, query: str) -> str:
        """Get an instant answer from DDG (no full search needed)."""
        try:
            from duckduckgo_search import DDGS
            def _get():
                with DDGS() as ddgs:
                    for r in ddgs.answers(query):
                        return r.get("text", "")
                return ""
            return await asyncio.to_thread(_get)
        except Exception:
            return ""

    async def summarize_results(self, query: str, brain=None) -> str:
        """Search and summarize results using the brain."""
        results = await self.search(query, max_results=5)
        if not results:
            return f"Couldn't find results for: {query}"

        if not brain:
            # Plain summary without LLM
            lines = [f"- {r['title']}: {r['snippet'][:100]}" for r in results[:3]]
            return f"Results for '{query}':\n" + "\n".join(lines)

        snippets = "\n".join(
            f"{i+1}. {r['title']}\n   {r['snippet']}"
            for i, r in enumerate(results)
        )
        prompt = (
            f"Based on these search results, answer this query concisely:\n"
            f"Query: {query}\n\nResults:\n{snippets}\n\n"
            f"Answer in 2-3 sentences, Boss-style (brief, confident):"
        )
        return await brain.think(prompt, use_context=False)

    async def _requests_fallback(self, query: str, max_results: int) -> List[dict]:
        """Simple Google search fallback using requests + BeautifulSoup."""
        try:
            import requests
            from bs4 import BeautifulSoup
            import urllib.parse

            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = await asyncio.to_thread(
                requests.get, url, headers=headers, timeout=10
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for result in soup.find_all("div", class_="result", limit=max_results):
                title_el = result.find("a", class_="result__a")
                snippet_el = result.find("a", class_="result__snippet")
                if title_el:
                    results.append({
                        "title":   title_el.get_text(strip=True),
                        "url":     title_el.get("href", ""),
                        "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                    })
            return results
        except Exception as e:
            log.error(f"Requests fallback also failed: {e}")
            return []
