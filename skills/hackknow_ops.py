"""
YAHAVIS — skills/hackknow_ops.py
Hackknow platform operations: WooCommerce, site health, GCP pings.
Credentials injected from .env — never hardcoded.
"""

import asyncio
import logging
import os
from typing import Optional

import aiohttp

log = logging.getLogger("yahavis.hackknow")

WC_SITE     = os.getenv("WC_SITE_URL", "https://shop.hackknow.com")
WC_KEY      = os.getenv("WC_CONSUMER_KEY", "")
WC_SECRET   = os.getenv("WC_CONSUMER_SECRET", "")
WC_API_BASE = f"{WC_SITE}/wp-json/wc/v3"
FRONTEND    = os.getenv("FRONTEND_URL", "https://hackknow.com")


class HackknowOps:
    """All Hackknow platform operations for YAHAVIS."""

    def _auth(self) -> tuple:
        return (WC_KEY, WC_SECRET)

    async def check_site_status(self, url: str = None) -> dict:
        """Ping site and return status code + latency."""
        target = url or WC_SITE
        import time
        try:
            start = time.time()
            async with aiohttp.ClientSession() as sess:
                async with sess.get(target, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    latency = round((time.time() - start) * 1000)
                    return {
                        "url": target,
                        "status": r.status,
                        "ok": r.status < 400,
                        "latency_ms": latency,
                    }
        except Exception as e:
            return {"url": target, "status": -1, "ok": False, "error": str(e)}

    async def get_orders(
        self,
        filter_: str = "today",
        status: str = "any",
        per_page: int = 20,
    ) -> list:
        """Fetch WooCommerce orders."""
        if not WC_KEY:
            log.warning("WC credentials not configured — returning mock data")
            return self._mock_orders()

        params = {"per_page": per_page, "status": status}
        if filter_ == "today":
            from datetime import datetime, timezone
            today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
            params["after"] = today

        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(
                    f"{WC_API_BASE}/orders",
                    params=params,
                    auth=aiohttp.BasicAuth(WC_KEY, WC_SECRET),
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as r:
                    r.raise_for_status()
                    orders = await r.json()
                    log.info(f"Fetched {len(orders)} orders (filter={filter_})")
                    return orders
        except Exception as e:
            log.error(f"WC orders fetch failed: {e}")
            return []

    async def create_product(self, data: dict) -> dict:
        """Create a new WooCommerce product."""
        if not WC_KEY:
            log.warning("WC credentials not configured")
            return {"error": "No WC credentials"}

        product = {
            "name": data.get("name", "New Product"),
            "type": "simple",
            "regular_price": str(data.get("price", "0")),
            "description": data.get("description", ""),
            "short_description": data.get("short_description", ""),
            "categories": [{"name": data.get("category", "Digital")}],
            "status": data.get("status", "draft"),
            "tags": [{"name": t} for t in data.get("tags", [])],
        }

        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    f"{WC_API_BASE}/products",
                    json=product,
                    auth=aiohttp.BasicAuth(WC_KEY, WC_SECRET),
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as r:
                    r.raise_for_status()
                    result = await r.json()
                    log.info(f"Product created: {result.get('id')} — {result.get('name')}")
                    return result
        except Exception as e:
            log.error(f"Product creation failed: {e}")
            return {"error": str(e)}

    async def update_product(self, product_id: int, data: dict) -> dict:
        """Update an existing WooCommerce product."""
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.put(
                    f"{WC_API_BASE}/products/{product_id}",
                    json=data,
                    auth=aiohttp.BasicAuth(WC_KEY, WC_SECRET),
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as r:
                    r.raise_for_status()
                    return await r.json()
        except Exception as e:
            log.error(f"Product update failed: {e}")
            return {"error": str(e)}

    async def get_revenue_summary(self) -> dict:
        """Get today's total revenue and order count."""
        orders = await self.get_orders(filter_="today", status="completed")
        total = sum(float(o.get("total", 0)) for o in orders)
        return {
            "orders_today": len(orders),
            "revenue_today": round(total, 2),
            "currency": orders[0].get("currency", "INR") if orders else "INR",
        }

    async def check_frontend_build(self) -> dict:
        """Check if the Hackknow frontend is live and responsive."""
        return await self.check_site_status(FRONTEND)

    async def generate_product_description(self, name: str, brain=None) -> str:
        """Use YAHAVIS brain to write a WooCommerce product description."""
        if not brain:
            return f"High-quality {name} — available exclusively on Hackknow."
        prompt = (
            f"Write a compelling WooCommerce product description for: '{name}'\n"
            f"Brand: Hackknow (Indian cybersecurity/tech tools platform)\n"
            f"Format: 2-3 paragraphs, professional but accessible tone.\n"
            f"Include benefits, features, and a clear call to action."
        )
        return await brain.think(prompt, use_context=False)

    def _mock_orders(self) -> list:
        return [
            {"id": 1001, "status": "completed", "total": "299.00",
             "currency": "INR", "billing": {"first_name": "Demo", "last_name": "User"}},
            {"id": 1002, "status": "processing", "total": "499.00",
             "currency": "INR", "billing": {"first_name": "Test", "last_name": "Buyer"}},
        ]

    def summarize_orders(self, orders: list) -> str:
        """Format orders into a voice-friendly summary."""
        if not orders:
            return "No orders found, Boss."
        count = len(orders)
        total = sum(float(o.get("total", 0)) for o in orders)
        currency = orders[0].get("currency", "INR") if orders else "INR"
        return (f"Found {count} order{'s' if count != 1 else ''}, Boss. "
                f"Total revenue: {currency} {total:,.2f}.")
