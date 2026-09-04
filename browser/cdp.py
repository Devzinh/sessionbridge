import asyncio
import time
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page
from browser.launcher import ensure_chrome, DEFAULT_CDP_PORT


class CDPConnection:
    """Manages the low-level Playwright connection to Chrome via Chrome DevTools Protocol."""

    def __init__(self, port: int = DEFAULT_CDP_PORT):
        self.port = port
        self.endpoint = f"http://127.0.0.1:{port}"
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def connect(
        self,
        auto_launch: bool = True,
        timeout_sec: Optional[float] = None,
    ) -> Tuple[Browser, BrowserContext]:
        """
        Connects to Chrome via CDP. If auto_launch is True, automatically starts Chrome
        if it's not already listening on the CDP port.
        """
        deadline = time.monotonic() + timeout_sec if timeout_sec is not None else None

        def remaining() -> Optional[float]:
            if deadline is None:
                return None
            value = deadline - time.monotonic()
            if value <= 0:
                raise asyncio.TimeoutError("CDP connection deadline exceeded")
            return value

        try:
            if auto_launch:
                launch_timeout = remaining()
                kwargs = {"port": self.port}
                if launch_timeout is not None:
                    kwargs["timeout_sec"] = launch_timeout
                await asyncio.to_thread(ensure_chrome, **kwargs)

            if not self.playwright:
                start = async_playwright().start()
                start_timeout = remaining()
                self.playwright = (
                    await asyncio.wait_for(start, timeout=start_timeout)
                    if start_timeout is not None
                    else await start
                )

            connect = self.playwright.chromium.connect_over_cdp(self.endpoint)
            connect_timeout = remaining()
            self.browser = (
                await asyncio.wait_for(connect, timeout=connect_timeout)
                if connect_timeout is not None
                else await connect
            )

            if not self.browser.contexts:
                raise RuntimeError("Browser connected but has no active browser contexts.")

            self.context = self.browser.contexts[0]
            return self.browser, self.context
        except BaseException as connection_error:
            try:
                await self.disconnect()
            except Exception as cleanup_error:
                connection_error.add_note(f"Playwright cleanup failed: {cleanup_error}")
            raise

    async def get_or_create_page(self) -> Page:
        """Returns the primary active page, or creates a new one if none exists."""
        if not self.context or not self.browser or not self.browser.is_connected():
            await self.connect()

        assert self.context is not None

        pages = self.context.pages
        if pages:
            page = pages[-1]
            for candidate in reversed(pages):
                try:
                    if await candidate.evaluate("document.visibilityState") == "visible":
                        page = candidate
                        break
                except Exception:
                    continue
        else:
            page = await self.context.new_page()

        await page.bring_to_front()
        return page

    async def disconnect(self):
        """Disconnects the CDP session without killing the user's Chrome browser."""
        try:
            if self.playwright:
                await self.playwright.stop()
        finally:
            self.browser = None
            self.context = None
            self.playwright = None

    @property
    def is_connected(self) -> bool:
        return bool(self.browser and self.browser.is_connected())


async def test_connection():
    cdp = CDPConnection()
    try:
        print("Connecting to Chrome over CDP...")
        browser, context = await cdp.connect(auto_launch=True)
        page = await cdp.get_or_create_page()
        title = await page.title()
        url = page.url
        print(f"Connected successfully!")
        print(f"Active Page: {url} | Title: {title}")
    finally:
        await cdp.disconnect()


if __name__ == "__main__":
    asyncio.run(test_connection())
