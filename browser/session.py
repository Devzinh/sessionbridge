import asyncio
import math
import time
from numbers import Real
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from browser.cdp import CDPConnection
from browser.state import inspect_page_state
from browser.launcher import DEFAULT_CDP_PORT


def validate_http_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be an absolute HTTP or HTTPS URL")
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in url):
        raise ValueError("URL must be an absolute HTTP or HTTPS URL")
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError as error:
        raise ValueError("URL must be an absolute HTTP or HTTPS URL") from error
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("URL must be an absolute HTTP or HTTPS URL")
    return url


class SessionBridge:
    """
    Central coordinator managing persistent Chrome browser sessions via CDP,
    state inspection, human-in-the-loop handoff, and workflow continuation.
    """

    def __init__(self, port: int = DEFAULT_CDP_PORT):
        self.port = port
        self.cdp = CDPConnection(port=port)
        self.page: Optional[Page] = None

    async def ensure_active(self, timeout_seconds: Optional[float] = None) -> Page:
        """Ensures CDP connection is alive and returns the current active page."""
        if not self.cdp.is_connected or not self.page or self.page.is_closed():
            deadline = (
                time.monotonic() + timeout_seconds
                if timeout_seconds is not None
                else None
            )
            await self.cdp.connect(auto_launch=True, timeout_sec=timeout_seconds)
            if deadline is None:
                self.page = await self.cdp.get_or_create_page()
            else:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise asyncio.TimeoutError("Page selection deadline exceeded")
                self.page = await asyncio.wait_for(
                    self.cdp.get_or_create_page(), timeout=remaining
                )
        return self.page

    async def open_url(self, url: str) -> Dict[str, Any]:
        """Navigates to a URL and immediately evaluates page state."""
        validate_http_url(url)
        page = await self.ensure_active()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        except PlaywrightTimeoutError:
            # Even if timeout happens (common with heavy Cloudflare challenge pages), check state
            pass
        except PlaywrightError as error:
            try:
                current_url = page.url
            except PlaywrightError:
                current_url = ""
            try:
                title = await page.title()
            except PlaywrightError:
                title = ""
            return {
                "connected": False,
                "url": current_url,
                "title": title,
                "manual_interaction_required": False,
                "reason": f"Navigation error: {error}",
                "ready": False,
            }

        # Give a small pause for scripts/challenge to mount
        await asyncio.sleep(1.0)
        return await self.get_status()

    async def get_status(self) -> Dict[str, Any]:
        """Inspects current page state, returning connected, ready, and manual_interaction_required."""
        try:
            page = await self.ensure_active()
            return await inspect_page_state(page)
        except Exception as e:
            return {
                "connected": False,
                "url": "",
                "title": "",
                "manual_interaction_required": False,
                "reason": f"Connection error: {str(e)}",
                "ready": False,
            }

    async def wait_for_human(
        self,
        timeout_seconds: float = 120,
        poll_interval: float = 1.5,
    ) -> Dict[str, Any]:
        """
        Monitors the page state until manual human interaction is resolved
        (e.g., Cloudflare challenge completed) or timeout occurs.
        """
        timing_values = (timeout_seconds, poll_interval)
        if any(
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(value)
            or value <= 0
            for value in timing_values
        ):
            raise ValueError(
                "timeout_seconds and poll_interval must be finite numbers greater than zero"
            )

        deadline = time.monotonic() + timeout_seconds
        last_status = None

        try:
            page = await self.ensure_active(timeout_seconds=timeout_seconds)
        except asyncio.TimeoutError:
            unit = "second" if timeout_seconds == 1 else "seconds"
            return {
                "connected": False,
                "url": "",
                "title": "",
                "manual_interaction_required": False,
                "reason": f"Timed out after {timeout_seconds} {unit} before page inspection",
                "ready": False,
                "success": False,
            }

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            try:
                status = await asyncio.wait_for(
                    inspect_page_state(page), timeout=remaining
                )
            except asyncio.TimeoutError:
                break

            last_status = status
            now = time.monotonic()
            if now >= deadline:
                break
            if not status.get("manual_interaction_required", False) and status.get(
                "ready", False
            ):
                return {**status, "success": True}

            await asyncio.sleep(min(poll_interval, deadline - now))

        final_status = last_status or {
            "connected": False,
            "url": "",
            "title": "",
            "manual_interaction_required": False,
            "reason": "No page state inspection completed",
            "ready": False,
        }
        final_reason = final_status.get("reason", "Unknown final page state")
        unit = "second" if timeout_seconds == 1 else "seconds"
        return {
            **final_status,
            "success": False,
            "reason": (
                f"Timed out after {timeout_seconds} {unit} waiting for manual resolution. "
                f"Final state: {final_reason}"
            ),
        }

    async def get_content(self, max_length: int = 4000) -> Dict[str, Any]:
        """Retrieves title, url, and readable text content from the current page."""
        if type(max_length) is not int or not 1 <= max_length <= 100000:
            raise ValueError("max_length must be between 1 and 100000")

        page = await self.ensure_active()
        title = await page.title()
        url = page.url

        try:
            text = await page.evaluate(
                """() => {
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    let node;
                    let text = '';
                    while (node = walker.nextNode()) {
                        const parent = node.parentElement;
                        if (parent && !['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(parent.tagName)) {
                            const trimmed = node.nodeValue.trim();
                            if (trimmed) text += trimmed + ' ';
                        }
                    }
                    return text.slice(0, 100000);
                }"""
            )
        except Exception:
            text = await page.content()
            text = text[:max_length]

        text = text[:max_length]
        return {
            "title": title,
            "url": url,
            "text": text,
            "length": len(text),
        }

    async def close(self):
        """Disconnects CDP."""
        await self.cdp.disconnect()
        self.page = None


# Singleton instance for consistent session state across tool calls
_global_session: Optional[SessionBridge] = None


def get_session(port: int = DEFAULT_CDP_PORT) -> SessionBridge:
    global _global_session
    if _global_session is None:
        _global_session = SessionBridge(port=port)
    return _global_session
