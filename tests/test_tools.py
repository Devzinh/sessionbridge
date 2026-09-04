from unittest.mock import AsyncMock

import pytest

from tools import browser


@pytest.mark.parametrize(
    ("session_status", "expected_status"),
    [
        (
            {
                "connected": True,
                "url": "https://example.com/challenge",
                "title": "Challenge",
                "manual_interaction_required": True,
                "reason": "CAPTCHA",
                "ready": False,
            },
            "blocked",
        ),
        (
            {
                "connected": True,
                "url": "https://example.com",
                "title": "Example",
                "manual_interaction_required": False,
                "reason": "Normal page state",
                "ready": True,
            },
            "ready",
        ),
        (
            {
                "connected": False,
                "url": "",
                "title": "",
                "manual_interaction_required": False,
                "reason": "Browser disconnected",
                "ready": False,
            },
            "unavailable",
        ),
    ],
)
async def test_continue_session_preserves_status_fields(
    monkeypatch, session_status, expected_status
):
    session = AsyncMock()
    session.get_status.return_value = session_status
    monkeypatch.setattr(browser, "get_session", lambda: session)

    result = await browser.continue_session()

    assert result == {**session_status, "status": expected_status}


async def test_browser_adapters_delegate_arguments(monkeypatch):
    session = AsyncMock()
    session.open_url.return_value = {"operation": "open"}
    session.get_status.return_value = {"operation": "status"}
    session.wait_for_human.return_value = {"operation": "wait"}
    session.get_content.return_value = {"operation": "content"}
    monkeypatch.setattr(browser, "get_session", lambda: session)

    assert await browser.open_browser("https://example.com") == {"operation": "open"}
    assert await browser.get_browser_status() == {"operation": "status"}
    assert await browser.wait_for_human(timeout_seconds=2.5) == {"operation": "wait"}
    assert await browser.get_current_page(max_length=123) == {"operation": "content"}

    session.open_url.assert_awaited_once_with("https://example.com")
    session.get_status.assert_awaited_once_with()
    session.wait_for_human.assert_awaited_once_with(timeout_seconds=2.5)
    session.get_content.assert_awaited_once_with(max_length=123)


async def test_close_browser_delegates_and_reports_disconnected(monkeypatch):
    session = AsyncMock()
    monkeypatch.setattr(browser, "get_session", lambda: session)

    result = await browser.close_browser()

    session.close.assert_awaited_once_with()
    assert result == {"status": "disconnected"}

