import asyncio

import pytest
from unittest.mock import AsyncMock, Mock

from browser import cdp
from browser.cdp import CDPConnection


class FakeBrowser:
    def __init__(self):
        self.close_called = False

    def is_connected(self):
        return True

    async def close(self):
        self.close_called = True


class FakePlaywright:
    def __init__(self):
        self.stop_called = False

    async def stop(self):
        self.stop_called = True


class BrokenPlaywright:
    async def stop(self):
        raise RuntimeError("stop failed")


@pytest.mark.asyncio
async def test_disconnect_stops_playwright_without_closing_browser():
    connection = CDPConnection()
    browser = FakeBrowser()
    playwright = FakePlaywright()
    connection.browser = browser
    connection.context = object()
    connection.playwright = playwright

    await connection.disconnect()

    assert playwright.stop_called is True
    assert browser.close_called is False
    assert connection.browser is None
    assert connection.context is None
    assert connection.playwright is None


@pytest.mark.asyncio
async def test_disconnect_propagates_stop_error_and_clears_references():
    connection = CDPConnection()
    connection.browser = FakeBrowser()
    connection.context = object()
    connection.playwright = BrokenPlaywright()

    with pytest.raises(RuntimeError, match="stop failed"):
        await connection.disconnect()

    assert connection.browser is None
    assert connection.context is None
    assert connection.playwright is None


@pytest.mark.asyncio
async def test_disconnect_is_safe_when_already_disconnected():
    connection = CDPConnection()

    await connection.disconnect()

    assert connection.is_connected is False


@pytest.mark.asyncio
async def test_connect_runs_ensure_chrome_in_a_worker_thread(monkeypatch):
    browser = Mock(contexts=[object()])
    playwright = Mock()
    playwright.chromium.connect_over_cdp = AsyncMock(return_value=browser)
    playwright_manager = Mock()
    playwright_manager.start = AsyncMock(return_value=playwright)
    to_thread = AsyncMock(return_value=True)
    monkeypatch.setattr(cdp, "async_playwright", Mock(return_value=playwright_manager))
    monkeypatch.setattr(cdp.asyncio, "to_thread", to_thread)

    connection = CDPConnection(port=9333)
    await connection.connect()

    to_thread.assert_awaited_once_with(cdp.ensure_chrome, port=9333)


@pytest.mark.asyncio
async def test_connect_passes_timeout_to_launcher_worker(monkeypatch):
    browser = Mock(contexts=[object()])
    playwright = Mock()
    playwright.chromium.connect_over_cdp = AsyncMock(return_value=browser)
    playwright_manager = Mock()
    playwright_manager.start = AsyncMock(return_value=playwright)
    to_thread = AsyncMock(return_value=True)
    monkeypatch.setattr(cdp, "async_playwright", Mock(return_value=playwright_manager))
    monkeypatch.setattr(cdp.asyncio, "to_thread", to_thread)

    connection = CDPConnection(port=9333)
    await connection.connect(timeout_sec=1.0)

    assert to_thread.await_args.kwargs["port"] == 9333
    assert 0 < to_thread.await_args.kwargs["timeout_sec"] <= 1.0


@pytest.mark.asyncio
async def test_connect_rolls_back_playwright_when_cancelled(monkeypatch):
    started = asyncio.Event()
    never_finishes = asyncio.Event()
    playwright = Mock()
    playwright.stop = AsyncMock()

    async def pending_connect(_endpoint):
        started.set()
        await never_finishes.wait()

    playwright.chromium.connect_over_cdp = pending_connect
    playwright_manager = Mock()
    playwright_manager.start = AsyncMock(return_value=playwright)
    monkeypatch.setattr(cdp, "async_playwright", Mock(return_value=playwright_manager))

    connection = CDPConnection()
    task = asyncio.create_task(connection.connect(auto_launch=False))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    playwright.stop.assert_awaited_once()
    assert connection.playwright is None


@pytest.mark.asyncio
async def test_connect_rolls_back_playwright_when_cdp_connection_fails(monkeypatch):
    playwright = Mock()
    playwright.stop = AsyncMock()
    playwright.chromium.connect_over_cdp = AsyncMock(
        side_effect=ConnectionError("CDP unavailable")
    )
    playwright_manager = Mock()
    playwright_manager.start = AsyncMock(return_value=playwright)
    monkeypatch.setattr(cdp, "async_playwright", Mock(return_value=playwright_manager))

    connection = CDPConnection()
    with pytest.raises(ConnectionError, match="CDP unavailable"):
        await connection.connect(auto_launch=False)

    playwright.stop.assert_awaited_once()
    assert connection.browser is None
    assert connection.context is None
    assert connection.playwright is None


@pytest.mark.asyncio
async def test_connect_rolls_back_playwright_when_browser_has_no_context(monkeypatch):
    browser = Mock(contexts=[])
    playwright = Mock()
    playwright.stop = AsyncMock()
    playwright.chromium.connect_over_cdp = AsyncMock(return_value=browser)
    playwright_manager = Mock()
    playwright_manager.start = AsyncMock(return_value=playwright)
    monkeypatch.setattr(cdp, "async_playwright", Mock(return_value=playwright_manager))

    connection = CDPConnection()
    with pytest.raises(RuntimeError, match="no active browser contexts"):
        await connection.connect(auto_launch=False)

    playwright.stop.assert_awaited_once()
    assert connection.browser is None
    assert connection.context is None
    assert connection.playwright is None


@pytest.mark.asyncio
async def test_connect_preserves_original_error_when_rollback_also_fails(monkeypatch):
    playwright = Mock()
    playwright.stop = AsyncMock(side_effect=RuntimeError("stop failed"))
    playwright.chromium.connect_over_cdp = AsyncMock(
        side_effect=ConnectionError("CDP unavailable")
    )
    playwright_manager = Mock()
    playwright_manager.start = AsyncMock(return_value=playwright)
    monkeypatch.setattr(cdp, "async_playwright", Mock(return_value=playwright_manager))

    connection = CDPConnection()
    with pytest.raises(ConnectionError, match="CDP unavailable") as caught:
        await connection.connect(auto_launch=False)

    assert caught.value.__notes__ == ["Playwright cleanup failed: stop failed"]
    assert connection.playwright is None


class FakePage:
    def __init__(self, visibility="hidden", evaluate_error=None):
        self.visibility = visibility
        self.evaluate_error = evaluate_error
        self.brought_to_front = False

    async def evaluate(self, _expression):
        if self.evaluate_error:
            raise self.evaluate_error
        return self.visibility

    async def bring_to_front(self):
        self.brought_to_front = True


@pytest.mark.asyncio
async def test_get_or_create_page_prefers_visible_page_and_brings_it_to_front():
    hidden = FakePage()
    visible = FakePage("visible")
    connection = CDPConnection()
    connection.browser = FakeBrowser()
    connection.context = Mock(pages=[hidden, visible])

    result = await connection.get_or_create_page()

    assert result is visible
    assert visible.brought_to_front is True


@pytest.mark.asyncio
async def test_get_or_create_page_falls_back_to_most_recent_page_on_evaluate_failure():
    first = FakePage(evaluate_error=RuntimeError("target closed"))
    latest = FakePage(evaluate_error=RuntimeError("target closed"))
    connection = CDPConnection()
    connection.browser = FakeBrowser()
    connection.context = Mock(pages=[first, latest])

    result = await connection.get_or_create_page()

    assert result is latest
    assert latest.brought_to_front is True


@pytest.mark.asyncio
async def test_get_or_create_page_creates_and_brings_new_page_to_front():
    page = FakePage()
    connection = CDPConnection()
    connection.browser = FakeBrowser()
    connection.context = Mock(pages=[])
    connection.context.new_page = AsyncMock(return_value=page)

    result = await connection.get_or_create_page()

    assert result is page
    assert page.brought_to_front is True
